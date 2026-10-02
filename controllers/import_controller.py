from PyQt5.QtCore import QObject, QSettings, pyqtSignal
from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox
from app_config import get_database_path
from ui.import_dialog import DateRangeDialog


class ImportController(QObject):
    import_completed = pyqtSignal()
    def __init__(self, window, panel):
        super().__init__(window)
        self.window, self.panel = window, panel
        self.settings = QSettings('ARTs', 'ImportV1')
        self.worker = None
        self.outcome = None
        self.cancel_requested = False

    @property
    def is_running(self):
        return self.worker is not None

    def start_import(self):
        if self.is_running:
            return
        dialog = DateRangeDialog(self.window)
        if dialog.exec_() != QDialog.Accepted:
            return
        start, end = dialog.date_range()
        folder = QFileDialog.getExistingDirectory(
            self.window, 'Chọn folder cha chứa các folder máy',
            self.settings.value('log_folder', '', type=str))
        if not folder:
            return
        self.settings.setValue('log_folder', folder)
        from workers.import_worker import ImportWorker
        self.outcome = None
        self.cancel_requested = False
        self.worker = ImportWorker(get_database_path(self.settings), folder, start, end, self)
        self.worker.succeeded.connect(lambda result: self.set_outcome('success', result))
        self.worker.failed.connect(lambda message: self.set_outcome('error', message))
        self.worker.cancelled.connect(lambda message: self.set_outcome('cancelled', message))
        self.worker.finished.connect(self.finished)
        self.panel.set_busy(True)
        self.worker.start()

    def set_outcome(self, kind, payload):
        self.outcome = (kind, payload)

    def finished(self):
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.deleteLater()
        self.panel.set_busy(False)
        kind, value = self.outcome or ('error', 'Không nhận được kết quả import. Kiểm tra log.')
        if kind == 'success':
            self.import_completed.emit()
            message = (f'Import thành công!\n\nSố file: {value.files}\n'
                       f'Dòng đã import: {value.inserted:,}\nDòng cũ đã thay: {value.deleted:,}')
            if value.missing_dates:
                message += '\n\nNgày không có file (giữ nguyên):\n' + ', '.join(value.missing_dates)
            if value.empty_dates:
                message += '\n\nNgày không có dòng hợp lệ (giữ nguyên):\n' + ', '.join(value.empty_dates)
            QMessageBox.information(self.window, 'Success', message)
        elif kind == 'cancelled':
            QMessageBox.information(self.window, 'Đã hủy import', value)
        else:
            QMessageBox.warning(self.window, 'Import không hoàn tất', value)

    def cancel_import(self):
        if self.worker is not None and not self.cancel_requested:
            self.cancel_requested = True
            self.worker.cancel()
            QMessageBox.information(self.window, 'Đang hủy import',
                                    'Đang chờ tác vụ kết thúc/rollback. Vui lòng đóng cửa sổ lại sau khi hoàn tất.')
