import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QGroupBox, QLineEdit, QDialog,
    QMessageBox
)
from PySide6.QtCore import Qt, QDate, QLocale
from PySide6.QtGui import QDoubleValidator, QIcon
# Импорт кастомных диалогов и менеджера БД
from settings_dialog import SettingsDialog
from database_manager import DatabaseManager

def resource_path(relative_path):
    """Получает абсолютный путь к ресурсу, работает для dev и для PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Устанавливаем русскую локаль для корректного отображения месяцев и дат
QLocale.setDefault(QLocale(QLocale.Language.Russian, QLocale.Country.Russia))

class InputDialog(QDialog):
    """Диалог для ввода суммы для конкретного дня, с проверкой лимита."""
    def __init__(self, date: QDate, parent=None, max_amount: float = 0.0):
        super().__init__(parent)
        self.date = date
        self.max_amount = max_amount
        self.setWindowTitle(f"Ввод суммы на {self._format_date_with_locale(date, 'dd.MM.yyyy')}")

        self.amount = 0.0

        layout = QVBoxLayout(self)

        # Метка с датой
        date_label = QLabel(f"Дата: <b>{self._format_date_with_locale(date, 'dd MMMM yyyy')}</b>")
        date_label.setStyleSheet("color: #e0e0e0; font-size: 14px;")
        layout.addWidget(date_label)

        # Поле ввода суммы с валидатором
        amount_layout = QHBoxLayout()
        amount_label = QLabel("Сумма:")
        amount_label.setStyleSheet("color: #e0e0e0;")
        amount_layout.addWidget(amount_label)
        
        self.amount_input = QLineEdit()
        if self.max_amount > 0:
            self.amount_input.setPlaceholderText(f"Макс. остаток: {self.max_amount:.2f} ₽")
        else:
            self.amount_input.setPlaceholderText("Введите сумму")
        
        validator = QDoubleValidator(0.00, 1000000000.00, 2)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.amount_input.setValidator(validator)
        
        amount_layout.addWidget(self.amount_input)
        layout.addLayout(amount_layout)

        # Информация о лимите (если есть)
        if self.max_amount > 0:
            limit_label = QLabel(f"⚠️ Осталось внести по договору: {self.max_amount:.2f} ₽")
            limit_label.setStyleSheet("color: #ffcc80; font-size: 12px;")
            layout.addWidget(limit_label)

        # Кнопки Сохранить/Отмена
        button_layout = QHBoxLayout()
        save_button = QPushButton("Сохранить")
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        # Сохранение при нажатии Enter
        self.amount_input.returnPressed.connect(self.accept)
        
        # Стили для диалога
        self.setStyleSheet("""
            QDialog {
                background-color: #37474f;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #4db6ac;
                border-radius: 4px;
                background-color: #455a64;
                color: #ffffff;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #80cbc4;
                background-color: #546e7a;
            }
            QPushButton {
                background-color: #4db6ac;
                color: #000000;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #80cbc4;
            }
            QPushButton:pressed {
                background-color: #26a69a;
            }
        """)
        
    def _format_date_with_locale(self, date: QDate, format_str: str) -> str:
        """Форматирует дату, используя установленную локаль."""
        return QLocale().toString(date, format_str)

    def accept(self):
        """Обработка сохранения данных с проверкой ввода и лимита."""
        try:
            # Заменяем запятую на точку для преобразования во float
            text = self.amount_input.text().replace(',', '.')
            self.amount = float(text)
            
            # Проверка лимита: не может быть больше оставшейся суммы по договору
            if self.max_amount > 0 and self.amount > self.max_amount:
                QMessageBox.warning(self, "Превышение лимита", 
                                  f"Сумма не может превышать {self.max_amount:.2f} ₽\n"
                                  f"Осталось по договору: {self.max_amount:.2f} ₽")
                return
            
            super().accept()
        except ValueError:
            QMessageBox.warning(self, "Ошибка ввода", "Пожалуйста, введите корректное числовое значение.")

    @staticmethod
    def get_amount(date: QDate, parent=None, max_amount: float = 0.0):
        dialog = InputDialog(date, parent, max_amount)
        result = dialog.exec()
        return result == QDialog.Accepted, dialog.amount


class FinanceCalendar(QMainWindow):
    """Основное окно приложения, отображающее календарь и сводные данные."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Финансовый Календарь")
        self.setFixedSize(1400, 700)

        # Устанавливаем иконку приложения
        self.setWindowIcon(QIcon(resource_path("icon.ico")))

        # Инициализация базы данных
        self.db = DatabaseManager()
        
        # -------------------- Инициализация данных для текущего вида --------------------
        self.current_date = QDate.currentDate()
        self.current_year = self.current_date.year()
        # Определяем текущее полугодие (1 или 2)
        self.current_half = 1 if self.current_date.month() <= 6 else 2 
        
        # Загружаем ежедневные данные из БД (Факт)
        self.daily_data = self.db.get_all_daily_data()
        
        # -------------------- Главный виджет и компоновка --------------------
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 1. Верхняя панель (Навигация)
        main_layout.addLayout(self._create_navigation_widget())
        
        # 2. Панель сводных данных за весь договор
        main_layout.addLayout(self._create_summary_layout())
        
        # 3. Контейнер для 6 месяцев (сетка)
        self.calendar_grid = QGridLayout()
        main_layout.addLayout(self.calendar_grid)
        
        # 4. Растяжитель для прижатия верхних элементов
        main_layout.addStretch(1)
        
        # Первоначальное отображение
        self.update_calendar_view()
        
        # Применяем темную тему
        self._apply_styles()

    def _apply_styles(self):
        """Применение темной CSS-схемы с акцентами."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #293133;
            }
            QWidget {
                color: #e0e0e0;
            }
            #NavigationLabel {
                font-size: 24px;
                font-weight: bold;
                color: #4db6ac;
            }
            #SummaryLabel {
                font-size: 11px;
                font-weight: bold;
                color: #b0bec5;
                padding: 2px 8px;
                border-radius: 6px;
                background-color: #37474f;
            }
            .month-group {
                border: 1px solid #4db6ac;
                border-radius: 8px;
                margin: 5px;
                padding: 10px;
                background-color: #37474f;
            }
            .day-label {
                font-weight: bold;
                text-align: center;
                border-bottom: 1px solid #546e7a;
                color: #e0e0e0;
            }
            .amount-label {
                font-size: 11px;
                color: #80cbc4;
                text-align: center;
            }
            .total-row-label {
                font-weight: 500;
                color: #b0bec5;
            }
            .month-summary-item {
                font-size: 11px;
                padding: 2px 4px;
                border-radius: 3px;
                margin: 0 2px;
            }
            QPushButton {
                background-color: #4db6ac;
                color: #000000;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #80cbc4;
            }
            QPushButton:pressed {
                background-color: #26a69a;
            }
            QGroupBox {
                font-weight: bold;
                color: #4db6ac;
                border: 1px solid #4db6ac;
                border-radius: 8px;
                margin-top: 10px;
                padding: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #4db6ac;
            }
            QLineEdit {
                padding: 6px;
                border: 1px solid #4db6ac;
                border-radius: 4px;
                background-color: #455a64;
                color: #ffffff;
            }
            QLineEdit:focus {
                border-color: #80cbc4;
                background-color: #546e7a;
            }
        """)

    def _open_about_dialog(self):
        """ 'О программе' - показывает информацию о приложении."""
        github_url = "https://github.com/Wadim377"
        
        message = (
            "<h2>Финансовый Календарь</h2>"
            "<p>Версия 1.0</p>"
            "<p>Приложение для удобного ведения финансового плана и контроля накоплений в системе строительных сбережений от Беларусбанка</p>"
            f"<p>GitHub: <a href='{github_url}' style='color: #4db6ac; text-decoration: none;'>{github_url}</a></p>"
        )
        
        about_box = QMessageBox(self)
        about_box.setWindowTitle("О программе")
        about_box.setText(message)
        about_box.setTextFormat(Qt.RichText)
        
        about_box.setStyleSheet("""
            QMessageBox {
                background-color: #293133;
                color: #e0e0e0;
            }
            QMessageBox QLabel {
                color: #e0e0e0;
            }
            QMessageBox QPushButton {
                background-color: #4db6ac;
                color: #000000;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #80cbc4;
            }
            QMessageBox QPushButton:pressed {
                background-color: #26a69a;
            }
        """)
        
        about_box.exec()

    def _open_settings_dialog(self):
        """Открывает диалог настроек договора и обновляет вид после сохранения."""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            # Пересчитываем планы в базе данных
            self.db.calculate_monthly_plans()
            
            # Сбрасываем вид на дату начала договора для удобства
            contract = self.db.get_contract_settings()
            start_date = contract['start_date']
            
            self.current_year = start_date.year()
            self.current_half = 1 if start_date.month() <= 6 else 2
            
            self.half_year_label.setText(self._get_half_year_text())
            self.update_calendar_view()
            self.update_nav_buttons_state()

    def _create_navigation_widget(self):
        """Создает виджет для навигации по полугодиям и кнопки Установки/О программе."""
        nav_layout = QHBoxLayout()
        
        settings_button = QPushButton("Установки")
        settings_button.clicked.connect(self._open_settings_dialog)
        
        about_button = QPushButton("О программе")
        about_button.clicked.connect(self._open_about_dialog)
        nav_layout.addWidget(about_button)

        nav_layout.addStretch()

        # Кнопки навигации по полугодиям
        self.prev_button = QPushButton("← Предыдущее полугодие")
        self.prev_button.clicked.connect(lambda: self.navigate_half(-1))
        nav_layout.addWidget(self.prev_button)

        self.half_year_label = QLabel(self._get_half_year_text())
        self.half_year_label.setAlignment(Qt.AlignCenter)
        self.half_year_label.setObjectName("NavigationLabel")
        nav_layout.addWidget(self.half_year_label)

        self.next_button = QPushButton("Следующее полугодие →")
        self.next_button.clicked.connect(lambda: self.navigate_half(1))
        nav_layout.addWidget(self.next_button)

        nav_layout.addStretch() 
        nav_layout.addWidget(settings_button)
        
        # Обновляем состояние кнопок (активны/неактивны)
        self.update_nav_buttons_state()
        
        return nav_layout

    def update_nav_buttons_state(self):
        """Блокирует кнопки навигации, если достигнуты границы договора (начало/конец)."""
        contract_settings = self.db.get_contract_settings()
        start_date = contract_settings['start_date']
        end_date = contract_settings['end_date']

        # Переводим дату в числовое представление для сравнения периодов
        current_period_val = self.current_year * 10 + self.current_half
        start_half = 1 if start_date.month() <= 6 else 2
        start_period_val = start_date.year() * 10 + start_half
        end_half = 1 if end_date.month() <= 6 else 2
        end_period_val = end_date.year() * 10 + end_half

        # Кнопка "Назад" не активна, если текущее полугодие - это начало договора
        if current_period_val <= start_period_val:
            self.prev_button.setEnabled(False)
        else:
            self.prev_button.setEnabled(True)

        # Кнопка "Вперед" не активна, если текущее полугодие - это конец договора
        if current_period_val >= end_period_val:
            self.next_button.setEnabled(False)
        else:
            self.next_button.setEnabled(True)

    def _get_half_year_text(self):
        """Возвращает текст для заголовка полугодия (например, '2024 1 полугодие (Январь-Июнь)')."""
        start_month_num = 1 if self.current_half == 1 else 7
        end_month_num = 6 if self.current_half == 1 else 12
        
        start_month_name = self._get_month_name_nominative(start_month_num)
        end_month_name = self._get_month_name_nominative(end_month_num)
        
        half_str = f"1 полугодие ({start_month_name}-{end_month_name})" if self.current_half == 1 else f"2 полугодие ({start_month_name}-{end_month_name})"
        return f"{self.current_year} {half_str}"
    
    def _get_month_name_nominative(self, month_num):
        """Возвращает название месяца в именительном падеже (для заголовков)."""
        month_names = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август", 
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
        }
        return month_names.get(month_num, "")

    def _create_summary_layout(self):
        """Создает сводные строки (план, факт, остаток, проценты) для всего договора."""
        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(10)
        
        labels = ["План:", "Факт:", "Осталось внести:", "Накопленные проценты:", "Сумма с учётом процентов:"]
        
        self.summary_labels = {}

        for text in labels:
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(1)
            
            label = QLabel(text)
            label.setObjectName("SummaryLabel")
            label.setAlignment(Qt.AlignCenter)
            container_layout.addWidget(label)
            
            value_label = QLabel("0.00 ₽")
            value_label.setObjectName(f"SummaryValue_{text}")
            value_label.setAlignment(Qt.AlignCenter)

            # Цвета для значений
            if text == "План:":
                color = "#ffb74d"
            elif text == "Факт:":
                color = "#81c784"
            elif text == "Осталось внести:":
                color = "#e57373"
            elif text == "Накопленные проценты:":
                color = "#4db6ac"
            else:
                color = "#64b5f6"

            value_label.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {color};")
            container_layout.addWidget(value_label)
            
            self.summary_labels[text.strip(':')] = value_label
            summary_layout.addWidget(container)

        summary_layout.insertStretch(0)
        summary_layout.addStretch()
        
        return summary_layout

    def navigate_half(self, direction: int):
        """Переключает отображаемое полугодие (direction: 1 вперед, -1 назад)."""
        if direction == 1:
            if self.current_half == 2:
                self.current_year += 1
                self.current_half = 1
            else:
                self.current_half = 2
        elif direction == -1:
            if self.current_half == 1:
                self.current_year -= 1
                self.current_half = 2
            else:
                self.current_half = 1
        
        self.half_year_label.setText(self._get_half_year_text())
        self.update_calendar_view()
        
        # Обновляем состояние кнопок после навигации
        self.update_nav_buttons_state()

    def update_calendar_view(self):
        """Очищает и заново отрисовывает 6 месяцев для текущего полугодия."""
        # Очистка предыдущих виджетов
        while self.calendar_grid.count():
            item = self.calendar_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        start_month = 1 if self.current_half == 1 else 7
        
        # Создание и добавление 6 месяцев
        for i in range(6):
            month_num = start_month + i
            row = i // 3
            col = i % 3
            
            month_box = self._create_month_widget(self.current_year, month_num)
            self.calendar_grid.addWidget(month_box, row, col)
            
        # Обновляем сводные данные (План/Факт всего договора)
        self.update_summary_data()

    def _create_month_widget(self, year: int, month: int):
        """Создает виджет (QGroupBox) для одного месяца с заголовком и сеткой дней."""
        month_group = QGroupBox()
        month_group.setObjectName("month-group")
        
        month_date = QDate(year, month, 1)
        month_name = self._get_month_name_nominative(month)
        
        month_layout = QVBoxLayout(month_group)
        month_layout.setContentsMargins(5, 5, 5, 5)
        month_layout.setSpacing(5)
        
        month_title = QLabel(f"<b>{month_name} {year}</b>")
        month_title.setAlignment(Qt.AlignCenter)
        
        # Стилизация заголовка и рамки: красная для прошедших месяцев, бирюзовая для текущих/будущих
        current_date = QDate.currentDate()
        is_past_month = (year < current_date.year()) or (year == current_date.year() and month < current_date.month())
        
        if is_past_month:
            title_color = "#e57373"
            border_color = "#e57373"
        else:
            title_color = "#4db6ac"
            border_color = "#4db6ac"
        
        month_title.setStyleSheet(f"color: {title_color}; font-size: 14px; margin-bottom: 5px;")
        month_layout.addWidget(month_title)
        
        # Добавление сводки месяца
        summary_layout = self._create_month_summary_rows(year, month)
        month_layout.addLayout(summary_layout)
        
        # Добавление сетки дней
        month_layout.addLayout(self._create_days_grid(year, month))
        
        # Применение стилей для QGroupBox
        month_group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid {border_color};
                border-radius: 8px;
                margin: 5px;
                padding: 10px;
                background-color: #37474f;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: {title_color};
            }}
        """)
        
        return month_group
    
    def _create_month_summary_rows(self, year: int, month: int):
        """Создает строки 'План', 'Факт', 'Осталось', 'Проценты' для сводки месяца."""
        month_key = f"{year}-{month:02d}"
        
        contract_settings = self.db.get_contract_settings()
        end_date = contract_settings['end_date']
        
        # Сводка месяца закрытия договора всегда 0
        if year == end_date.year() and month == end_date.month():
            monthly_plan = 0.0
            monthly_fact = 0.0
            remaining = 0.0
        else:
            # Получение планов и факта
            monthly_plans = self.db.calculate_monthly_plans()
            monthly_plan = monthly_plans.get(month_key, 0.0)
            monthly_fact = self._calculate_monthly_fact(month_key)
            remaining = monthly_plan - monthly_fact
        
        # Получение процентов
        monthly_summary = self.db.get_monthly_summary(year, month)
        monthly_interest = monthly_summary['interest']

        summary_layout = QHBoxLayout()
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(8)
        
        row_data = [
            ("План", monthly_plan, "#ffb74d"),
            ("Факт", monthly_fact, "#81c784"),
            ("Осталось", remaining, "#e57373"),
            ("Проценты", monthly_interest, "#ba68c8")
        ]
        
        # Создание и добавление меток
        for label_text, value, color in row_data:
            item_container = QWidget()
            item_layout = QVBoxLayout(item_container)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(2)
            item_layout.setAlignment(Qt.AlignCenter)
            
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 9px; color: #b0bec5;")
            item_layout.addWidget(label)
            
            value_label = QLabel(f"{value:.2f} ₽")
            # Сохраняем имя объекта для быстрого обновления (update_data_labels)
            value_label.setObjectName(f"month_value_{month_key}_{label_text}")
            value_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 10px;")
            value_label.setAlignment(Qt.AlignCenter)
            item_layout.addWidget(value_label)
            
            summary_layout.addWidget(item_container)
        
        summary_layout.insertStretch(0)
        summary_layout.addStretch()
        
        return summary_layout

    def _create_days_grid(self, year: int, month: int):
        """Создает сетку дней месяца с нумерацией и суммами (ежедневными 'Факт')."""
        days_grid = QGridLayout()
        days_grid.setContentsMargins(0, 0, 0, 0)
        days_grid.setSpacing(2)
        
        first_day = QDate(year, month, 1)
        days_in_month = first_day.daysInMonth()
        
        # Заголовки дней недели
        days_of_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        for i, day_name in enumerate(days_of_week):
            header_label = QLabel(day_name)
            header_label.setAlignment(Qt.AlignCenter)
            header_label.setStyleSheet("font-weight: bold; color: #b0bec5; border-bottom: 1px solid #4db6ac; font-size: 10px;")
            days_grid.addWidget(header_label, 0, i)
        
        first_day_row = 1
        # Позиция первого дня недели (0=Пн, 6=Вс)
        first_day_col = (first_day.dayOfWeek() - 1) % 7
        
        current_row = first_day_row
        current_col = first_day_col
        
        # Создание ячеек для каждого дня
        for day in range(1, days_in_month + 1):
            date = QDate(year, month, day)
            day_key = date.toString('yyyy-MM-dd')
            amount = self.daily_data.get(day_key, 0.00)
            
            day_container = QWidget()
            # Сохраняем имя объекта для обновления стилей
            day_container.setObjectName(f"daily_container_{day_key}")
            
            day_container_layout = QVBoxLayout(day_container)
            day_container_layout.setContentsMargins(2, 2, 2, 2)
            day_container_layout.setSpacing(1)

            day_label = QLabel(str(day))
            day_label.setObjectName("day-label") # Используем общий name для поиска
            day_label.setAlignment(Qt.AlignCenter)
            day_container_layout.addWidget(day_label)

            amount_label = QLabel(f"{amount:.2f} ₽")
            # Сохраняем имя объекта для обновления суммы
            amount_label.setObjectName(f"daily_value_{day_key}")
            amount_label.setAlignment(Qt.AlignCenter)
            day_container_layout.addWidget(amount_label)
            
            # Стилизация: зеленый - внесена сумма, бирюзовый - текущий день, темно-серый - остальные
            if amount > 0:
                style = "background-color: #388e3c; border-radius: 4px;"
                day_label.setStyleSheet("color: white; font-weight: bold;")
                amount_label.setStyleSheet("color: white; font-size: 9px; font-weight: bold;")
            elif date == QDate.currentDate():
                style = "background-color: #4db6ac; border-radius: 4px;"
                day_label.setStyleSheet("color: white; font-weight: bold;")
                amount_label.setStyleSheet("color: white; font-size: 9px;")
            else:
                style = "background-color: #455a64; border-radius: 3px;"
                day_label.setStyleSheet("color: #e0e0e0; font-weight: bold;") 
                amount_label.setStyleSheet("color: #80cbc4; font-size: 9px;")
            
            day_container.setStyleSheet(f"QWidget {{ {style} }}")
            # Обработчик клика
            day_container.mousePressEvent = lambda event, d=date: self._day_clicked(d)

            days_grid.addWidget(day_container, current_row, current_col)
            
            current_col += 1
            if current_col > 6:
                current_col = 0
                current_row += 1
        
        return days_grid

    def _day_clicked(self, date: QDate):
        """Обрабатывает клик по дню: открывает диалог ввода суммы с проверкой лимита договора."""
        contract_settings = self.db.get_contract_settings()
        total_contract_amount = contract_settings['contract_amount']
        start_date: QDate = contract_settings['start_date']
        end_date: QDate = contract_settings['end_date']

        # 1. Проверка нахождения даты в рамках договора
        # Разрешен ввод: [start_date, end_date - 1 день]
        if date < start_date or date >= end_date:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Ошибка ввода")
            msg.setText("Внесение сумм разрешено только в период действия договора.")
            msg.setInformativeText(f"Период: с {start_date.toString('dd.MM.yyyy')} по {end_date.addDays(-1).toString('dd.MM.yyyy')}")

            # Применение CSS стилей
            style_sheet = """
                QMessageBox {
                    background-color: #37474f;
                    color: #ffffff;
                }
                QMessageBox QLabel {
                    color: #ffffff;
                }
                QPushButton {
                    background-color: #4db6ac;
                    color: #000000;
                    border: none;
                    padding: 5px 10px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #80cbc4;
                }
            """
            msg.setStyleSheet(style_sheet)
            msg.exec()
            return
        
        # 2. Расчет оставшейся суммы по договору
        all_daily_data = self.db.get_all_daily_data()
        total_fact = sum(all_daily_data.values())
        max_remaining_to_pay = total_contract_amount - total_fact
        
        # 3. Если договор уже выполнен
        if max_remaining_to_pay <= 0:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Договор выполнен")
            msg_box.setText("Сумма по договору уже внесена.")
            msg_box.setIcon(QMessageBox.Information)
            
            # Установка темного стиля
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #293133;
                    color: #e0e0e0;
                }
                QMessageBox QLabel {
                    color: #e0e0e0;
                }
                QMessageBox QPushButton {
                    background-color: #4db6ac;
                    color: #000000;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                    min-width: 80px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #80cbc4;
                }
                QMessageBox QPushButton:pressed {
                    background-color: #26a69a;
                }
            """)
            
            msg_box.exec()
            return

        # 4. Ограничиваем максимальную сумму ввода
        max_amount = max(0.0, max_remaining_to_pay)

        # 5. Вызов диалога ввода суммы
        dialog = InputDialog(date, self, max_amount=max_amount)

        if dialog.exec() == QDialog.Accepted:
            new_amount = dialog.amount
            if new_amount is not None:
                # Сохранение в БД
                self.db.save_daily_amount(date, new_amount)
                # Обновление локальных данных
                self.daily_data[date.toString('yyyy-MM-dd')] = new_amount

                # Обновление всех меток
                self.update_data_labels(date)
                self.update_summary_data()
                self.update_nav_buttons_state()
            
    def _calculate_monthly_fact(self, month_key: str) -> float:
        """Суммирует все ежедневные 'Факт' для данного месяца (YYYY-MM)."""
        fact = sum(amount for date_key, amount in self.daily_data.items() if date_key.startswith(month_key))
        return fact
    
    def update_data_labels(self, date_in_month: QDate):
        """Обновляет все метки (ежедневные и сводные) для месяца, содержащего date_in_month."""
        year = date_in_month.year()
        month = date_in_month.month()
        month_key = date_in_month.toString('yyyy-MM')
        
        contract_settings = self.db.get_contract_settings()
        end_date = contract_settings['end_date']
        
        # 1. Обновляем ежедневные суммы и их стили
        for day in range(1, date_in_month.daysInMonth() + 1):
            date = QDate(year, month, day)
            day_key = date.toString('yyyy-MM-dd')
            amount = self.daily_data.get(day_key, 0.00)
            
            # Поиск виджетов по имени
            container = self.findChild(QWidget, f"daily_container_{day_key}")
            amount_label = self.findChild(QLabel, f"daily_value_{day_key}")
            # Поиск day_label внутри контейнера
            day_label = container.findChild(QLabel, "day-label") if container else None
            
            if amount_label and container:
                amount_label.setText(f"{amount:.2f} ₽")
                
                # Обновление стилей
                if amount > 0:
                    style = style = "background-color: #388e3c; border-radius: 4px;"
                    label_style = "color: white; font-size: 9px; font-weight: bold;"
                    day_style = "color: white; font-weight: bold;"
                elif date == QDate.currentDate():
                    style = style = "background-color: #4db6ac; border-radius: 4px;"
                    label_style = "color: white; font-size: 9px;"
                    day_style = "color: white; font-weight: bold;"
                else:
                    style = style = "background-color: #455a64; border-radius: 3px;"
                    label_style = "color: #80cbc4; font-size: 9px;"
                    day_style = "font-weight: bold; color: #e0e0e0;" 
                
                container.setStyleSheet(f"QWidget {{ {style} }}")
                amount_label.setStyleSheet(label_style)
                if day_label:
                    day_label.setStyleSheet(day_style)
        
        # 2. Обновляем месячные сводки (План, Факт, Осталось, Проценты)
        if year == end_date.year() and month == end_date.month():
            monthly_plan = 0.0
            monthly_fact = 0.0
            remaining = 0.0
        else:
            monthly_plans = self.db.calculate_monthly_plans()
            monthly_plan = monthly_plans.get(month_key, 0.0)
            monthly_fact = self._calculate_monthly_fact(month_key)
            remaining = monthly_plan - monthly_fact
        
        monthly_summary = self.db.get_monthly_summary(year, month)
        monthly_interest = monthly_summary['interest']

        # Обновление текста меток
        plan_label = self.findChild(QLabel, f"month_value_{month_key}_План")
        if plan_label: plan_label.setText(f"{monthly_plan:.2f} ₽")
        
        fact_label = self.findChild(QLabel, f"month_value_{month_key}_Факт")
        if fact_label: fact_label.setText(f"{monthly_fact:.2f} ₽")
        
        remaining_label = self.findChild(QLabel, f"month_value_{month_key}_Осталось")
        if remaining_label: remaining_label.setText(f"{remaining:.2f} ₽")
        
        interest_label = self.findChild(QLabel, f"month_value_{month_key}_Проценты")
        if interest_label: interest_label.setText(f"{monthly_interest:.2f} ₽")
        
    def update_summary_data(self):
        """Обновляет сводные данные (верхняя панель) для ВСЕГО договора."""
        # 1. Получаем настройки договора
        contract_settings = self.db.get_contract_settings()
        total_contract_amount = contract_settings['contract_amount']
        
        # 2. Считаем ОБЩИЙ факт и ОБЩИЕ проценты
        all_daily_data = self.db.get_all_daily_data()
        total_fact = sum(all_daily_data.values())
        total_interest = self.db.get_total_accumulated_interest(QDate.currentDate())
        
        # 3. Вычисляем остаток и итоговую сумму
        remaining = total_contract_amount - total_fact
        # Используем max(0.0, ...) чтобы остаток не был отрицательным на виджете
        display_remaining = max(0.0, remaining) 
        total_with_interest = total_fact + total_interest
        
        # 4. Обновляем метки верхней панели (Global Totals)
        self.summary_labels["План"].setText(f"{total_contract_amount:.2f} ₽")
        self.summary_labels["Факт"].setText(f"{total_fact:.2f} ₽")
        
        self.summary_labels["Осталось внести"].setText(f"{display_remaining:.2f} ₽")
        # Изменение цвета остатка: красный (нужно внести) / зеленый (договор выполнен)
        color = "#ef5350" if remaining > 0 else "#81c784"
        self.summary_labels["Осталось внести"].setStyleSheet(f"font-weight: bold; font-size: 14px; color: {color};")
        
        self.summary_labels["Накопленные проценты"].setText(f"{total_interest:.2f} ₽")
        self.summary_labels["Сумма с учётом процентов"].setText(f"{total_with_interest:.2f} ₽")
        
        # 5. Важно: Обновляем данные (план/факт/проценты) во всех месяцах текущего вида
        start_month = 1 if self.current_half == 1 else 7
        for i in range(6):
            month_num = start_month + i
            self.update_data_labels(QDate(self.current_year, month_num, 1))

# -------------------- Точка входа в приложение --------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Устанавливаем иконку для всего приложения
    app_icon = QIcon(resource_path("icon.ico"))
    app.setWindowIcon(app_icon)
    
    window = FinanceCalendar()
    window.show()
    sys.exit(app.exec())
