from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QDialog, QDateEdit, QDialogButtonBox, QFormLayout, QVBoxLayout, QMessageBox


class DateRangeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Chọn khoảng ngày import')
        self.setMinimumWidth(370)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 12)
        form = QFormLayout()
        self.date_from = QDateEdit(QDate.currentDate())
        self.date_to = QDateEdit(QDate.currentDate())
        for field in (self.date_from, self.date_to):
            field.setCalendarPopup(True)
            field.setDisplayFormat('dd/MM/yyyy')
            field.setMinimumWidth(260)
        form.addRow('Từ ngày:', self.date_from)
        form.addRow('Đến ngày:', self.date_to)
        layout.addLayout(form)
        layout.addSpacing(16)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('Tiếp tục')
        buttons.button(QDialogButtonBox.Cancel).setText('Hủy')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        if self.date_from.date() > self.date_to.date():
            QMessageBox.warning(self, 'Khoảng ngày', 'Từ ngày phải nhỏ hơn hoặc bằng Đến ngày.')
            return
        super().accept()

    def date_range(self):
        return self.date_from.date().toString('yyyy-MM-dd'), self.date_to.date().toString('yyyy-MM-dd')
