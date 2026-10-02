from threading import Event
from PyQt5.QtCore import QThread, pyqtSignal


class SummaryWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, path, criteria, parent=None):
        super().__init__(parent)
        self.path, self.criteria = path, dict(criteria)
        self.cancel_event = Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        import sqlite3
        from repositories.machine_yield_repository import MachineYieldRepository
        try:
            while not self.cancel_event.is_set():
                try:
                    result = MachineYieldRepository(self.path).load(
                        self.criteria, self.cancel_event, self.progress.emit, include_daily=True)
                    # Import heavy modules off the UI thread; create Qt widgets only in UI.
                    self.progress.emit('Đang chuẩn bị biểu đồ…')
                    import ui.charts.machine_yield_chart
                    import ui.charts.daily_scrap_chart
                    import ui.charts.zone_yield_chart
                    if not self.cancel_event.is_set():
                        self.succeeded.emit(result)
                    return
                except sqlite3.OperationalError as error:
                    if self.cancel_event.is_set():
                        return
                    if not any(word in str(error).lower() for word in ('locked', 'busy')):
                        raise
                    self.progress.emit('Database bận, đang chờ…')
                    self.cancel_event.wait(1)
        except Exception as error:
            if not self.cancel_event.is_set():
                self.failed.emit(str(error))
