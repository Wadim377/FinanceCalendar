from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QLineEdit, QDateEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QAbstractItemView, QWidget
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QDoubleValidator, QRegularExpressionValidator
from PySide6.QtCore import QRegularExpression
# Импорт менеджера БД для работы с настройками
from database_manager import DatabaseManager


class SettingsDialog(QDialog):
    """Диалог для управления глобальными настройками договора (даты, сумма, ставка)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DatabaseManager()  # Инициализация менеджера БД
        self.setWindowTitle("Настройки договора")
        self.setFixedSize(700, 600)
        
        # Загружаем текущие данные из БД
        self.contract_data = self.db.get_contract_settings()
        
        self.init_ui()
        self.load_settings()  # Загрузка данных в поля формы
        
    def init_ui(self):
        """Создание основного интерфейса диалога."""
        layout = QVBoxLayout(self)
        
        # 1. Даты договора
        dates_group = self.create_dates_group()
        layout.addWidget(dates_group)
        
        # 2. Ставка рефинансирования
        rate_group = self.create_rate_group()
        layout.addWidget(rate_group)
        
        # 3. Сумма по договору
        amount_group = self.create_amount_group()
        layout.addWidget(amount_group)
        
        # Кнопки сохранения/отмены
        button_layout = QHBoxLayout()
        
        save_button = QPushButton("Сохранить")
        save_button.clicked.connect(self.save_settings)
        
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        # Применяем темные стили
        self.apply_styles()
        
    def create_dates_group(self):
        """Создает группу полей для ввода дат начала и конца договора."""
        group = QWidget()
        layout = QVBoxLayout(group)
        
        title = QLabel("Даты договора")
        title.setStyleSheet("font-weight: bold; color: #4db6ac; font-size: 14px;")
        layout.addWidget(title)
        
        grid_layout = QGridLayout()
        
        # Дата заключения (Начало)
        grid_layout.addWidget(QLabel("Дата заключения:"), 0, 0)
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.start_date_edit.setCalendarPopup(True) # Включение календаря
        grid_layout.addWidget(self.start_date_edit, 0, 1)
        
        # Дата закрытия (Конец)
        grid_layout.addWidget(QLabel("Дата закрытия:"), 1, 0)
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.end_date_edit.setCalendarPopup(True)
        grid_layout.addWidget(self.end_date_edit, 1, 1)
        
        layout.addLayout(grid_layout)
        
        return group
        
    def create_rate_group(self):
        """Создает группу полей для начальной ставки и истории изменений ставки."""
        group = QWidget()
        layout = QVBoxLayout(group)
        
        title = QLabel("Ставка рефинансирования")
        title.setStyleSheet("font-weight: bold; color: #4db6ac; font-size: 14px;")
        layout.addWidget(title)
        
        # Начальная ставка
        initial_rate_layout = QHBoxLayout()
        initial_rate_layout.addWidget(QLabel("Ставка на дату заключения (%):"))
        
        self.initial_rate_edit = QLineEdit()
        self.initial_rate_edit.setPlaceholderText("0.00")
        
        # Валидатор: 1-3 цифры, опционально запятая/точка и 1-2 цифры (для процентов)
        validator = QRegularExpressionValidator(
            QRegularExpression(r"^\d{1,3}([.,]\d{1,2})?$"), self.initial_rate_edit
        )
        self.initial_rate_edit.setValidator(validator)
        
        initial_rate_layout.addWidget(self.initial_rate_edit)
        
        layout.addLayout(initial_rate_layout)
        
        # История изменений ставки
        history_layout = QVBoxLayout()
        
        history_title = QLabel("История изменений ставки:")
        history_title.setStyleSheet("font-weight: bold; margin-top: 10px;")
        history_layout.addWidget(history_title)
        
        # Таблица для отображения истории ставок
        self.rate_table = QTableWidget()
        self.rate_table.setColumnCount(2)
        self.rate_table.setHorizontalHeaderLabels(["Дата изменения", "Ставка (%)"])
        self.rate_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rate_table.setSelectionBehavior(QAbstractItemView.SelectRows) # Выделение всей строки
        history_layout.addWidget(self.rate_table)
        
        # Кнопки управления историей
        rate_buttons_layout = QHBoxLayout()
        
        add_rate_button = QPushButton("Добавить ставку")
        add_rate_button.clicked.connect(self.add_rate_history)
        
        remove_rate_button = QPushButton("Удалить выбранную")
        remove_rate_button.clicked.connect(self.remove_rate_history)
        
        rate_buttons_layout.addWidget(add_rate_button)
        rate_buttons_layout.addWidget(remove_rate_button)
        rate_buttons_layout.addStretch()
        
        history_layout.addLayout(rate_buttons_layout)
        layout.addLayout(history_layout)
        
        return group
        
    def create_amount_group(self):
        """Создает группу полей для ввода общей суммы по договору."""
        group = QWidget()
        layout = QVBoxLayout(group)
        
        title = QLabel("Сумма по договору")
        title.setStyleSheet("font-weight: bold; color: #4db6ac; font-size: 14px;")
        layout.addWidget(title)
        
        amount_layout = QHBoxLayout()
        amount_layout.addWidget(QLabel("Общая сумма договора:"))
        
        self.amount_edit = QLineEdit()
        self.amount_edit.setPlaceholderText("0.00")
        
        # Валидатор: 1-12 цифр, опционально запятая/точка и 1-2 цифры (для суммы)
        validator = QRegularExpressionValidator(
            QRegularExpression(r"^\d{1,12}([.,]\d{1,2})?$"), self.amount_edit
        )
        self.amount_edit.setValidator(validator)
        
        amount_layout.addWidget(self.amount_edit)
        
        layout.addLayout(amount_layout)
        
        return group
        
    def add_rate_history(self):
        """Открывает диалог для добавления новой записи об изменении ставки."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Добавление ставки")
        dialog.setFixedSize(300, 150)
        
        layout = QVBoxLayout(dialog)
        
        # Поле для даты
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Дата:"))
        date_edit = QDateEdit()
        date_edit.setDisplayFormat("dd.MM.yyyy")
        date_edit.setCalendarPopup(True)
        date_edit.setDate(QDate.currentDate())
        date_layout.addWidget(date_edit)
        layout.addLayout(date_layout)
        
        # Поле для значения ставки
        rate_layout = QHBoxLayout()
        rate_layout.addWidget(QLabel("Ставка (%):"))
        rate_edit = QLineEdit()
        rate_edit.setPlaceholderText("0.00")
        
        # Применяем валидатор для ставки
        validator = QRegularExpressionValidator(
            QRegularExpression(r"^\d{1,3}([.,]\d{1,2})?$"), rate_edit
        )
        rate_edit.setValidator(validator)
        
        rate_layout.addWidget(rate_edit)
        layout.addLayout(rate_layout)
        
        # Кнопки диалога
        button_layout = QHBoxLayout()
        add_button = QPushButton("Добавить")
        
        def add_rate():
            """Функция сохранения данных из диалога в таблицу."""
            try:
                date = date_edit.date()
                rate_text = rate_edit.text().replace(',', '.')
                if not rate_text:
                    QMessageBox.warning(dialog, "Ошибка", "Введите значение ставки")
                    return
                    
                rate = float(rate_text)
                
                # Добавление новой строки в QTableWidget
                row = self.rate_table.rowCount()
                self.rate_table.insertRow(row)
                self.rate_table.setItem(row, 0, QTableWidgetItem(date.toString("dd.MM.yyyy")))
                self.rate_table.setItem(row, 1, QTableWidgetItem(f"{rate:.2f}"))
                
                dialog.accept()
            except ValueError:
                QMessageBox.warning(dialog, "Ошибка", "Введите корректное значение ставки")
        
        add_button.clicked.connect(add_rate)
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addWidget(add_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        dialog.exec()
        
    def remove_rate_history(self):
        """Удаляет выбранную строку из таблицы истории ставок."""
        current_row = self.rate_table.currentRow()
        if current_row >= 0:
            self.rate_table.removeRow(current_row)
        
    def load_settings(self):
        """Загружает сохраненные настройки из базы данных в поля формы."""
        # Установка простых значений
        self.start_date_edit.setDate(self.contract_data['start_date'])
        self.end_date_edit.setDate(self.contract_data['end_date'])
        self.initial_rate_edit.setText(f"{self.contract_data['initial_rate']:.2f}")
        self.amount_edit.setText(f"{self.contract_data['contract_amount']:.2f}")
        
        # Очистка и загрузка истории ставок
        self.rate_table.setRowCount(0)
        
        for rate_item in self.contract_data['rate_history']:
            row = self.rate_table.rowCount()
            self.rate_table.insertRow(row)
            # Вставляем дату и ставку как QTableWidgetItem
            self.rate_table.setItem(row, 0, QTableWidgetItem(rate_item['date']))
            self.rate_table.setItem(row, 1, QTableWidgetItem(f"{rate_item['rate']:.2f}"))
        
    def save_settings(self):
        """Сохраняет данные из полей формы в базу данных."""
        try:
            # Предварительная валидация данных
            if not self.validate_data():
                return
                
            # Сбор данных из полей формы
            self.contract_data['start_date'] = self.start_date_edit.date()
            self.contract_data['end_date'] = self.end_date_edit.date()
            # Замена запятой на точку для float-преобразования
            self.contract_data['initial_rate'] = float(self.initial_rate_edit.text().replace(',', '.'))
            self.contract_data['contract_amount'] = float(self.amount_edit.text().replace(',', '.'))
            
            # Сбор данных из таблицы истории ставок
            self.contract_data['rate_history'] = []
            for row in range(self.rate_table.rowCount()):
                date_item = self.rate_table.item(row, 0)
                rate_item = self.rate_table.item(row, 1)
                if date_item and rate_item:
                    self.contract_data['rate_history'].append({
                        'date': date_item.text(),
                        'rate': float(rate_item.text())
                    })
            
            # Сохранение в базу данных
            self.db.save_contract_settings(self.contract_data)
            
            self.accept()
            QMessageBox.information(self, "Успех", "Настройки сохранены успешно!")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при сохранении: {str(e)}")
            
    def validate_data(self):
        """Проверяет корректность введенных данных."""
        # 1. Проверка дат
        if self.start_date_edit.date() >= self.end_date_edit.date():
            QMessageBox.warning(self, "Ошибка", "Дата закрытия должна быть позже даты заключения")
            return False
            
        # 2. Проверка начальной ставки
        if not self.initial_rate_edit.text():
            QMessageBox.warning(self, "Ошибка", "Введите начальную ставку рефинансирования")
            return False
            
        try:
            rate = float(self.initial_rate_edit.text().replace(',', '.'))
            if rate < 0 or rate > 100:
                QMessageBox.warning(self, "Ошибка", "Ставка должна быть в диапазоне от 0 до 100%")
                return False
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Введите корректное значение ставки")
            return False
            
        # 3. Проверка суммы договора
        if not self.amount_edit.text():
            QMessageBox.warning(self, "Ошибка", "Введите сумму по договору")
            return False
            
        try:
            amount = float(self.amount_edit.text().replace(',', '.'))
            if amount <= 0:
                QMessageBox.warning(self, "Ошибка", "Сумма договора должна быть больше 0")
                return False
            if amount > 1000000000000:  # Защита от слишком больших чисел
                QMessageBox.warning(self, "Ошибка", "Сумма договора слишком большая")
                return False
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Введите корректное значение суммы договора")
            return False
            
        return True
        
    def get_contract_data(self):
        """Возвращает данные договора (используется после сохранения)."""
        return self.contract_data
        
    def apply_styles(self):
        """Применение темного CSS-стиля для диалога."""
        self.setStyleSheet("""
            QDialog {
                background-color: #37474f;
            }
            QWidget {
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
            QLineEdit, QDateEdit {
                padding: 6px;
                border: 1px solid #4db6ac;
                border-radius: 4px;
                background-color: #455a64;
                color: #ffffff;
            }
            QLineEdit:focus, QDateEdit:focus {
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
            QTableWidget {
                background-color: #455a64;
                border: 1px solid #4db6ac;
                border-radius: 4px;
                gridline-color: #546e7a;
            }
            QTableWidget::item {
                padding: 5px;
                border-bottom: 1px solid #546e7a;
            }
            QTableWidget::item:selected {
                background-color: #4db6ac;
            }
            QHeaderView::section {
                background-color: #4db6ac;
                color: #000000;
                padding: 5px;
                border: none;
                font-weight: bold;
            }
        """)
