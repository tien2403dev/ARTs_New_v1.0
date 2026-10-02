from threading import Event
from PyQt5.QtCore import QThread, pyqtSignal

class FilterOptionWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    waiting = pyqtSignal(bool)

    def __init__(self, path, revision=None, parent=None):
        super().__init__(parent)
        self.path, self.revision = path, revision
        self.cancel_event = Event()

    def run(self):
        import sqlite3
        from repositories.filter_option_repository import FilterOptionRepository
        waiting = False
        try:
            while not self.cancel_event.is_set():
                try:
                    result = FilterOptionRepository(self.path).load_options(self.cancel_event, self.revision)
                    if not self.cancel_event.is_set():
                        self.succeeded.emit(result)
                    return
                except sqlite3.OperationalError as error:
                    if self.cancel_event.is_set():
                        return
                    if 'locked' not in str(error).lower() and 'busy' not in str(error).lower():
                        raise
                    if not waiting:
                        waiting = True
                        self.waiting.emit(True)
                    self.cancel_event.wait(5)
        except Exception as error:
            if not self.cancel_event.is_set():
                self.failed.emit(str(error))
        finally:
            if waiting:
                self.waiting.emit(False)

    def cancel(self):
        self.cancel_event.set()
