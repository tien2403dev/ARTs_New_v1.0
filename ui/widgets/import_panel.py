from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QPushButton


class ImportPanel(QFrame):
    import_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('importPanel')
        self.setStyleSheet('''
            QFrame#importPanel { background: #f7f9fb; border: 1px solid #dce4ec; border-radius: 6px; }
            QPushButton { background: #1675d1; color: white; border: 1px solid #0866be;
                          border-radius: 4px; font-weight: bold; padding: 0 12px; }
            QPushButton:hover { background: #0868bf; }
            QPushButton:disabled { background: #94b5d5; border-color: #94b5d5; }
        ''')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        self.button = QPushButton('IMPORT')
        self.button.setFixedSize(120, 30)
        self.button.clicked.connect(self.import_requested.emit)
        layout.addWidget(self.button)
        layout.addStretch()

    def set_busy(self, busy):
        self.button.setEnabled(not busy)
        self.button.setText('Đang import…' if busy else 'IMPORT')
