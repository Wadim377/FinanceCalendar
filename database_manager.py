import sqlite3
import json
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QDate


class DatabaseManager:
    def __init__(self, db_path="finance_calendar.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        # Инициализация БД и создание необходимых таблиц
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Таблица для фактических ежедневных сумм (пополнений)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    amount REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для месячных планов (устаревшая/ручная, не используется в текущем расчете)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS monthly_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    month_key TEXT UNIQUE NOT NULL,
                    plan_amount REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для глобальных настроек договора (главный источник данных для расчетов)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contract_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    initial_rate REAL NOT NULL,
                    rate_history TEXT NOT NULL,
                    contract_amount REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()

    # Методы для работы с ежедневными данными
    def save_daily_amount(self, date: QDate, amount: float):
        # Сохраняет/обновляет/удаляет ежедневную сумму. Удаление происходит, если amount == 0.
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if amount == 0:
                cursor.execute('DELETE FROM daily_data WHERE date = ?', (date.toString('yyyy-MM-dd'),))
            else:
                # Используем INSERT OR REPLACE для атомарного обновления или вставки
                cursor.execute('''
                    INSERT OR REPLACE INTO daily_data (date, amount, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (date.toString('yyyy-MM-dd'), amount))
            
            conn.commit()

    def get_daily_amount(self, date: QDate) -> float:
        # Получает фактическую сумму пополнения для конкретного дня
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT amount FROM daily_data WHERE date = ?', (date.toString('yyyy-MM-dd'),))
            result = cursor.fetchone()
            return result[0] if result else 0.0

    def get_all_daily_data(self) -> dict:
        # Получает все ежедневные пополнения
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT date, amount FROM daily_data')
            return {row[0]: row[1] for row in cursor.fetchall()}

    # Методы для работы с месячными планами
    def save_monthly_plan(self, month_key: str, plan_amount: float):
        # Сохраняет/обновляет ручной месячный план
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO monthly_plans (month_key, plan_amount, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (month_key, plan_amount))
            conn.commit()

    def get_monthly_plan(self, month_key: str) -> float:
        # Получает ручной месячный план
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT plan_amount FROM monthly_plans WHERE month_key = ?', (month_key,))
            result = cursor.fetchone()
            return result[0] if result else 0.0

    def get_all_monthly_plans(self) -> dict:
        # Получает все ручные месячные планы
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT month_key, plan_amount FROM monthly_plans')
            return {row[0]: row[1] for row in cursor.fetchall()}

    # Методы для работы с настройками договора
    def save_contract_settings(self, contract_data: dict):
        # Сохраняет настройки договора. Удаляет предыдущие записи, оставляя только одну актуальную.
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            start_date = contract_data['start_date'].toString('yyyy-MM-dd')
            end_date = contract_data['end_date'].toString('yyyy-MM-dd')
            
            # Конвертируем историю ставок (список dict) в строку JSON для хранения в TEXT поле
            rate_history_json = json.dumps(contract_data['rate_history'])
            
            cursor.execute('DELETE FROM contract_settings')
            cursor.execute('''
                INSERT INTO contract_settings 
                (start_date, end_date, initial_rate, rate_history, contract_amount)
                VALUES (?, ?, ?, ?, ?)
            ''', (start_date, end_date, contract_data['initial_rate'], 
                  rate_history_json, contract_data['contract_amount']))
            
            conn.commit()

    def get_contract_settings(self) -> dict:
        # Получает актуальные настройки договора (последнюю запись)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM contract_settings ORDER BY id DESC LIMIT 1')
            result = cursor.fetchone()
            
            if result:
                # Десериализация: JSON-строка rate_history обратно в список dict
                return {
                    'start_date': QDate.fromString(result[1], 'yyyy-MM-dd'),
                    'end_date': QDate.fromString(result[2], 'yyyy-MM-dd'),
                    'initial_rate': result[3],
                    'rate_history': json.loads(result[4]),
                    'contract_amount': result[5]
                }
            else:
                # Возвращаем настройки по умолчанию, если записи в БД нет
                return {
                    'start_date': QDate.currentDate(),
                    'end_date': QDate.currentDate().addYears(1),
                    'initial_rate': 0.0,
                    'rate_history': [],
                    'contract_amount': 0.0
                }

    # Методы для расчета помесячного плана
    def calculate_monthly_plans(self) -> dict:
        """Рассчитывает план погашения основного долга по месяцам, включая месяц заключения, но исключая месяц закрытия"""
        contract_settings = self.get_contract_settings()
        start_date = contract_settings['start_date']
        end_date = contract_settings['end_date']
        total_amount = contract_settings['contract_amount']
        
        if total_amount == 0:
            return {}
        
        # Считаем количество месяцев для равномерного распределения, ВКЛЮЧАЯ месяц заключения, ИСКЛЮЧАЯ месяц закрытия
        months_count = self._get_months_between_dates_including_start_excluding_end(start_date, end_date)
        
        if months_count == 0:
            return {}
        
        base_monthly_amount = total_amount / months_count
        daily_data = self.get_all_daily_data()
        
        monthly_plans = {}
        cumulative_fact = 0.0
        
        # Итерация по месяцам договора (включая месяц заключения, исключая месяц закрытия)
        current_date = QDate(start_date.year(), start_date.month(), 1)
        month_index = 0
        
        while current_date < end_date:
            # Проверяем, что это не месяц закрытия
            if current_date.year() == end_date.year() and current_date.month() == end_date.month():
                current_date = current_date.addMonths(1)
                continue
                
            month_key = current_date.toString('yyyy-MM')
            month_index += 1
            
            # Суммируем фактические пополнения за текущий месяц
            monthly_fact = 0.0
            for date_key, amount in daily_data.items():
                if date_key.startswith(month_key):
                    monthly_fact += amount
            
            cumulative_fact += monthly_fact
            
            # Расчет скорректированного плана
            target_cumulative_plan = base_monthly_amount * month_index
            
            if cumulative_fact > target_cumulative_plan:
                # Если переплата, уменьшаем план текущего месяца
                previous_cumulative_plan = base_monthly_amount * (month_index - 1)
                adjusted_plan = max(0, base_monthly_amount - (cumulative_fact - target_cumulative_plan))
            else:
                adjusted_plan = base_monthly_amount
            
            monthly_plans[month_key] = adjusted_plan
            
            current_date = current_date.addMonths(1)
        
        return monthly_plans

    def _get_months_between_dates_including_start_excluding_end(self, start_date: QDate, end_date: QDate) -> int:
        """Вспомогательный: Вычисляет количество месяцев ВКЛЮЧАЯ месяц начала, ИСКЛЮЧАЯ месяц конца"""
        total_months = (end_date.year() - start_date.year()) * 12 + end_date.month() - start_date.month()
        return max(1, total_months)  # Минимум 1 месяц

    def _get_months_between_dates_excluding_end(self, start_date: QDate, end_date: QDate) -> int:
        # Вспомогательный: Вычисляет количество месяцев для равномерного распределения
        total_months = (end_date.year() - start_date.year()) * 12 + end_date.month() - start_date.month()
        return max(0, total_months)

    def _get_month_index(self, current_date: QDate, start_date: QDate) -> int:
        # Вспомогательный: Возвращает порядковый номер месяца с начала договора (начиная с 1)
        return (current_date.year() - start_date.year()) * 12 + current_date.month() - start_date.month() + 1

    def get_remaining_contract_amount(self) -> float:
        """Возвращает оставшуюся сумму по договору (задолженность) БЕЗ учета процентов"""
        contract_settings = self.get_contract_settings()
        
        # Общая сумма договора
        total_contract_amount = contract_settings['contract_amount']
        
        # Общая сумма фактических пополнений (внесенных средств)
        daily_data = self.get_all_daily_data()
        total_fact = sum(daily_data.values())
        
        # Оставшаяся сумма (Задолженность) = Общая сумма договора - Внесенные средства
        remaining = max(0, total_contract_amount - total_fact)
        return remaining

    def get_adjusted_monthly_plan(self, year: int, month: int) -> float:
        # Получает расчетный скорректированный план на месяц
        contract_settings = self.get_contract_settings()
        end_date = contract_settings['end_date']
        month_key = f"{year}-{month:02d}"
        
        monthly_plans = self.calculate_monthly_plans()
        
        # Если это месяц закрытия договора, возвращаем оставшуюся сумму (в текущей реализации всегда 0.0)
        # TODO: Добавить логику для месяца закрытия, если end_date не совпадает с последним месяцем распределения
        if year == end_date.year() and month == end_date.month():
            return monthly_plans.get(month_key, 0.0)
        else:
            return monthly_plans.get(month_key, 0.0)

    def calculate_monthly_interest(self, year: int, month: int) -> float:
        """Рассчитывает проценты за месяц с учетом ЕЖЕДНЕВНОЙ КАПИТАЛИЗАЦИИ на ВНЕСЕННЫЕ средства."""
        contract_settings = self.get_contract_settings()
        start_date = contract_settings['start_date']
        contract_day = start_date.day()
        current_date_real = QDate.currentDate()
    
        # Определяем дату начисления процентов (например, 15-е число месяца)
        try:
            accrual_date = QDate(year, month, contract_day)
            if not accrual_date.isValid():
                last_day = QDate(year, month, 1).daysInMonth()
                accrual_date = QDate(year, month, last_day)
        except:
            last_day = QDate(year, month, 1).daysInMonth()
            accrual_date = QDate(year, month, last_day)
    
        if accrual_date <= start_date:
            return 0.0
    
        # Период начисления: с (Дата начисления - 1 месяц) по (Дата начисления - 1 день)
        target_period_start = accrual_date.addMonths(-1)
        if target_period_start < start_date:
            target_period_start = start_date
            
        simulation_end_date = min(accrual_date, current_date_real)
        
        if target_period_start >= simulation_end_date:
            return 0.0
    
        all_payments = self.get_all_daily_data()
        
        # НАЧИНАЕМ С НУЛЕВОГО БАЛАНСА - проценты начисляются только на внесенные средства
        current_balance = 0.0
        interest_for_target_period = 0.0
        
        # Симуляция с ПЕРВОГО дня договора
        iter_date = start_date
        
        while iter_date < simulation_end_date:
            day_str = iter_date.toString('yyyy-MM-dd')
            
            # А) Начисляем проценты на накопленный баланс на начало дня (КАПИТАЛИЗАЦИЯ)
            if current_balance > 0:
                rate = self.get_effective_rate_on_date(iter_date, contract_settings)
                days_in_year = iter_date.daysInYear()
                
                # Формула ежедневного процента: (Баланс * Ставка / 100) / Дней в году
                daily_interest = (current_balance * rate / 100.0) / days_in_year
                
                current_balance += daily_interest
                
                # Сохраняем проценты, если день входит в целевой месяц
                if iter_date >= target_period_start:
                    interest_for_target_period += daily_interest
            
            # Б) Учитываем пополнение: добавляем внесенные средства к балансу
            if day_str in all_payments:
                current_balance += all_payments[day_str]  # ДОБАВЛЯЕМ пополнение к балансу
            
            iter_date = iter_date.addDays(1)
    
        return interest_for_target_period

    def _get_total_balance_on_date(self, date: QDate) -> float:
        """Возвращает общий баланс (Внесенные средства + накопленные проценты) на указанную дату"""
        contract_settings = self.get_contract_settings()
        start_date = contract_settings['start_date']
        
        if date < start_date:
            return 0.0  # До начала договора баланс нулевой
        
        # Начинаем с нулевого баланса
        current_balance = 0.0
        current_date = start_date
        daily_data = self.get_all_daily_data()
        
        # Симуляция накопления процентов и добавления платежей
        while current_date <= date:
            # Начисление процентов на существующий баланс
            if current_balance > 0:
                daily_rate = self.get_effective_rate_on_date(current_date, contract_settings) / 365.0
                interest_today = current_balance * daily_rate / 100
                current_balance += interest_today
            
            # Учет платежей в этот день (увеличение баланса)
            day_key = current_date.toString('yyyy-MM-dd')
            if day_key in daily_data and daily_data[day_key] > 0:
                current_balance += daily_data[day_key]
            
            current_date = current_date.addDays(1)
        
        return current_balance

    def get_effective_rate_on_date(self, date: QDate, contract_settings: dict = None) -> float:
        # Получает действующую ставку на указанную дату (с учетом истории изменений)
        if contract_settings is None:
            contract_settings = self.get_contract_settings()
        
        effective_rate = contract_settings['initial_rate']
        
        rate_history = sorted(contract_settings['rate_history'], 
                            key=lambda x: QDate.fromString(x['date'], 'dd.MM.yyyy'))
        
        # Ищем последнее изменение ставки, которое произошло ДО или В указанную дату
        for rate_change in rate_history:
            change_date = QDate.fromString(rate_change['date'], 'dd.MM.yyyy')
            if change_date <= date:
                effective_rate = rate_change['rate']
            else:
                break
        
        return effective_rate

    # Вспомогательные методы
    def get_monthly_summary(self, year: int, month: int) -> dict:
        # Получает сводку (план, факт, остаток, проценты) за месяц
        month_key = f"{year}-{month:02d}"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Расчетный план
            monthly_plans = self.calculate_monthly_plans()
            plan = monthly_plans.get(month_key, 0.0)
            
            # Фактические пополнения за месяц
            start_date_str = f"{year}-{month:02d}-01"
            end_date = QDate(year, month, 1).addMonths(1).addDays(-1)
            end_date_str = end_date.toString('yyyy-MM-dd')
            
            cursor.execute('''
                SELECT SUM(amount) FROM daily_data 
                WHERE date BETWEEN ? AND ?
            ''', (start_date_str, end_date_str))
            
            fact_result = cursor.fetchone()
            fact = fact_result[0] if fact_result[0] is not None else 0.0
            
            # Расчет процентов за месяц
            interest = self.calculate_monthly_interest(year, month)
            
            return {
                'plan': plan,
                'fact': fact,
                'remaining': plan - fact,
                'interest': interest
            }

    def get_total_accumulated_interest(self, up_to_date: QDate = None) -> float:
        # Общая сумма накопленных процентов (суммирование по месяцам)
        if up_to_date is None:
            up_to_date = QDate.currentDate()
            
        contract_settings = self.get_contract_settings()
        start_date = contract_settings['start_date']
        
        if up_to_date <= start_date:
            return 0.0
            
        total_interest = 0.0
        
        # Начинаем с месяца, следующего за месяцем начала договора
        current_check_date = start_date.addMonths(1)
        
        # Итерация по месяцам
        while current_check_date <= up_to_date.addMonths(1): 
            
            year = current_check_date.year()
            month = current_check_date.month()
            
            # Ограничение итерации текущей датой
            if QDate(year, month, 1) > up_to_date and current_check_date > up_to_date:
                break

            interest = self.calculate_monthly_interest(year, month)
            total_interest += interest
            
            current_check_date = current_check_date.addMonths(1)
            
        return total_interest

    def get_half_year_summary(self, year: int, half: int) -> dict:
        # Получает сводку (план, факт, остаток) за полугодие
        start_month = 1 if half == 1 else 7
        total_plan = 0.0
        total_fact = 0.0
        
        for month in range(start_month, start_month + 6):
            monthly_summary = self.get_monthly_summary(year, month)
            total_plan += monthly_summary['plan']
            total_fact += monthly_summary['fact']
        
        return {
            'total_plan': total_plan,
            'total_fact': total_fact,
            'total_remaining': total_plan - total_fact
        }
