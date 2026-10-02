from PyQt5.QtCore import QObject,QTimer,QSettings,pyqtSignal
from PyQt5.QtWidgets import QMessageBox
from app_config import get_database_path

class FilterController(QObject):
    idle=pyqtSignal()

    def __init__(self,window,panel,status):
        super().__init__(window)
        self.window,self.panel,self.status=window,panel,status
        self.worker=None;self.revision=None;self.pending=False;self.stopping=False;self.wait_dialog=None
        self.timer=QTimer(self);self.timer.setInterval(60000);self.timer.timeout.connect(self.refresh);self.timer.start()
        self.refresh()

    def refresh(self,force=False):
        if self.stopping:return
        if force:self.revision=None
        if self.worker is not None:
            self.pending=self.pending or force
            return
        from workers.filter_option_worker import FilterOptionWorker
        path=get_database_path(QSettings('ARTs','ImportV1'))
        self.worker=FilterOptionWorker(path,self.revision,self)
        self.worker.succeeded.connect(self.loaded);self.worker.failed.connect(self.failed)
        self.worker.waiting.connect(self.waiting);self.worker.finished.connect(self.finished)
        if not self.panel.ready:self.status.setText('Đang tải bộ lọc…')
        self.worker.start()

    def loaded(self,result):
        if self.stopping:return
        self.revision=result['revision']
        if result['options'] is not None:self.panel.load_options(result['options'])
        self.panel.set_ready(True)
        if not self.window.current_criteria:self.status.setText('Chọn điều kiện và bấm SEARCH.')

    def failed(self,message):
        self.panel.set_ready(False)
        self.status.setText('Không tải được bộ lọc: '+message+' — sẽ thử lại sau 60 giây.')

    def waiting(self,value):
        if value and not self.stopping:
            self.panel.set_ready(False)
            self.status.setText('Database đang cập nhật, vui lòng thử lại sau 2 phút')
            if self.wait_dialog is None:
                self.wait_dialog=QMessageBox(QMessageBox.Information,'Database đang cập nhật',
                    'Database đang cập nhật, vui lòng thử lại sau 2 phút',QMessageBox.Ok,self.window)
                self.wait_dialog.setModal(False);self.wait_dialog.show()
        elif self.wait_dialog is not None:
            self.wait_dialog.close();self.wait_dialog.deleteLater();self.wait_dialog=None

    def finished(self):
        worker=self.worker;self.worker=None
        if worker:worker.deleteLater()
        if self.stopping:self.idle.emit()
        elif self.pending:
            self.pending=False;self.refresh(True)

    def stop(self):
        self.stopping=True;self.timer.stop();self.waiting(False)
        if self.worker is not None:self.worker.cancel()
