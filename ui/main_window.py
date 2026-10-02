"""Lightweight shell; filter database loading starts after the window is shown."""
from PyQt5.QtCore import QTimer,pyqtSignal
from PyQt5.QtWidgets import QWidget,QVBoxLayout,QLabel,QScrollArea,QTabWidget
from ui.widgets.filter_panel import FilterPanel

class MainWindow(QWidget):
    filter_applied=pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle('ARTs');self.resize(1200,650)
        self.setStyleSheet('MainWindow {background:#e3efff;}')
        self.controller=None;self.filter_controller=None;self.current_criteria=None;self._scheduled=False
        layout=QVBoxLayout(self);layout.setContentsMargins(8,10,8,10)
        self.import_panel=FilterPanel(self)
        area=QScrollArea();area.setWidget(self.import_panel);area.setWidgetResizable(False)
        area.setFixedHeight(self.import_panel.sizeHint().height()+8);area.setFrameShape(QScrollArea.NoFrame)
        area.setStyleSheet('QScrollArea {background:transparent;}')
        layout.addWidget(area)
        self.filter_status=QLabel('');self.filter_status.setStyleSheet('color:#315a8a;');self.filter_status.setWordWrap(True)
        layout.addWidget(self.filter_status)
        from ui.pages.summary_page import SummaryPage
        self.tabs=QTabWidget();self.summary_page=SummaryPage(self)
        self.tabs.addTab(self.summary_page, 'Summary');layout.addWidget(self.tabs,1)
        self.summary_controller=None
        self.import_panel.import_requested.connect(self.request_import)
        self.import_panel.filter_applied.connect(self.apply_filters)

    def showEvent(self,event):
        super().showEvent(event)
        if not self._scheduled:
            self._scheduled=True;QTimer.singleShot(100,self.start_filters)

    def start_filters(self):
        if not self.isVisible():return
        from controllers.filter_controller import FilterController
        self.filter_controller=FilterController(self,self.import_panel,self.filter_status)

    def apply_filters(self,criteria):
        self.current_criteria=criteria
        self.filter_status.setText(f"Đã chọn điều kiện: {criteria['date_from']} → {criteria['date_to']} | EQP: {criteria['eqp'] or 'ALL'} | Handler: {criteria['handler'] or 'ALL'} | Zone: {criteria['zone'] or 'ALL'} | Slot: {criteria['slot'] if criteria['slot'] is not None else 'ALL'} | Model: {len(criteria['models'])} | Scrap Code: {len(criteria['scrap_codes'])}")
        self.filter_applied.emit(criteria)
        if self.summary_controller is None:
            from controllers.summary_controller import SummaryController
            self.summary_controller=SummaryController(self,self.summary_page)
        self.summary_controller.search(criteria)

    def request_import(self):
        if self.controller is None:
            from controllers.import_controller import ImportController
            self.controller=ImportController(self,self.import_panel)
            self.controller.import_completed.connect(self.refresh_filters)
        self.controller.start_import()

    def refresh_filters(self):
        self.summary_page.clear_result("Dữ liệu đã cập nhật. Bấm SEARCH để tải lại.")
        if self.filter_controller:self.filter_controller.refresh(True)

    def closeEvent(self,event):
        if self.summary_controller:
            self.summary_controller.stop()
            if self.summary_controller.worker is not None:
                self.summary_controller.idle.connect(self.close)
                event.ignore();return
        if self.controller is not None and self.controller.is_running:
            self.controller.cancel_import();event.ignore();return
        if self.filter_controller:
            self.filter_controller.stop()
            if self.filter_controller.worker is not None:
                self.filter_controller.idle.connect(self.close)
                event.ignore();return
        event.accept()
