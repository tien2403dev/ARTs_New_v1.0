from PyQt5.QtCore import QObject, QSettings, QTimer, pyqtSignal
from PyQt5.QtWidgets import QMessageBox
from app_config import get_database_path
from ui.widgets.loading_dialog import LoadingDialog


class SummaryController(QObject):
    idle = pyqtSignal()

    def __init__(self, window, page):
        super().__init__(window)
        self.window, self.page = window, page
        self.worker = None
        self.dialog = None
        self.stopping = False

    def search(self, criteria):
        if self.worker is not None or self.stopping:
            return
        from workers.summary_worker import SummaryWorker
        self.criteria = dict(criteria)
        self.window.import_panel.set_search_busy(True)
        self.dialog = LoadingDialog(self.window, 'Đang thống kê yield…')
        self.dialog.setFixedWidth(340)
        self.dialog.rejected.connect(self.cancel)
        self.dialog.show()
        self.worker = SummaryWorker(get_database_path(QSettings('ARTs', 'ImportV1')), criteria, self)
        self.worker.progress.connect(self.progress)
        self.worker.succeeded.connect(self.loaded)
        self.worker.failed.connect(self.failed)
        self.worker.finished.connect(self.finished)
        QTimer.singleShot(0, self.worker.start)

    def progress(self, text):
        if self.dialog is not None:
            self.dialog.set_text(text)

    def loaded(self, result):
        if self.stopping or self.worker.cancel_event.is_set():
            return
        try:
            self.page.load_result(result, self.criteria)
        except Exception as error:
            self.failed(str(error))

    def failed(self, message):
        if self.stopping:
            return
        self.page.clear_result('Search chưa hoàn tất. Hãy bấm SEARCH để thử lại.')
        self.window.filter_status.setText('Search thất bại: '+message)
        QMessageBox.warning(self.window, 'Summary', message)

    def finished(self):
        worker, self.worker = self.worker, None
        if worker is not None:
            worker.deleteLater()
        if self.dialog is not None:
            self.dialog.accept(); self.dialog.deleteLater(); self.dialog = None
        self.window.import_panel.set_search_busy(False)
        if self.stopping:
            self.idle.emit()

    def cancel(self):
        if self.worker is not None:
            self.worker.cancel()

    def stop(self):
        self.stopping = True
        self.cancel()
