from threading import Event
from PyQt5.QtCore import QThread, pyqtSignal

class ImportWorker(QThread):
    progress = pyqtSignal(str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal(str)

    def __init__(self, database_path, folder, date_from, date_to, parent=None):
        super().__init__(parent)
        self.arguments = database_path, folder, date_from, date_to
        self.cancel_event = Event()

    def run(self):
        # Heavy dependencies load in the worker, after the window is visible.
        from domain.models import ImportCancelled
        try:
            from services.logging_service import configure_logging
            configure_logging()
            from services.import_service import ImportService
            db, folder, start, end = self.arguments
            result = ImportService(db).import_folder(folder,start,end,self.progress.emit,self.cancel_event)
            self.succeeded.emit(result)
        except ImportCancelled as error:
            self.cancelled.emit(str(error))
        except Exception as error:
            import logging
            logging.getLogger(__name__).exception('IMPORT_FAILED')
            self.failed.emit(str(error))

    def cancel(self):
        self.cancel_event.set()
