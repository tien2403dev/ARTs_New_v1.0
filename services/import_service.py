import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from database.schema import initialize_database
from domain.models import ImportResult, LockLostError, check_cancel
from repositories.import_lock_repository import ImportLockRepository, ImportHeartbeat
from repositories.data_repository import DataRepository
from services.file_discovery import discover_files, selected_dates
from services.staging_service import stage_files
logger = logging.getLogger(__name__)

class ImportService:
    def __init__(self, database_path):
        self.database_path = Path(database_path)

    def import_folder(self, root, date_from, date_to, progress=None, cancel=None):
        dates = selected_dates(date_from, date_to)
        def notify(message):
            logger.info('PROGRESS %s', message)
            if progress:
                progress(message)
        check_cancel(cancel)
        notify('Đang tìm file TXT theo khoảng ngày…')
        files = discover_files(root, dates, cancel)
        if not files:
            raise ValueError('Không tìm thấy file YYYY-MM-DD*.txt trong khoảng ngày. Không thay đổi database.')
        initialize_database(self.database_path)
        locks = ImportLockRepository(self.database_path)
        batch_id = locks.acquire(f'{root} | {date_from} → {date_to}')
        heartbeat = ImportHeartbeat(locks, batch_id)
        committed = False
        try:
            heartbeat.start()
            with TemporaryDirectory(prefix='arts_import_') as temporary:
                stage = Path(temporary)/'staging.sqlite'
                notify(f'Tìm thấy {len(files)} file. Đang đọc vào staging local…')
                counts = stage_files(files, stage, notify, cancel)
                heartbeat.stop()
                if heartbeat.lost.is_set():
                    raise LockLostError('Phiên import đã mất khóa. Không thay dữ liệu.')
                check_cancel(cancel)
                days, inserted, deleted = DataRepository(self.database_path).replace_from_staging(stage,batch_id,notify,cancel)
                committed = True
                return ImportResult(days,len(files),inserted,deleted,
                                    tuple(d for d in dates if d not in counts),
                                    tuple(d for d,n in counts.items() if not n),batch_id)
        finally:
            if heartbeat.thread.is_alive():
                try:
                    heartbeat.stop()
                except Exception:
                    logger.exception('HEARTBEAT_CLEANUP_ERROR batch=%s',batch_id)
            if not committed:
                try:
                    locks.release(batch_id)
                except Exception:
                    logger.exception('LOCK_RELEASE_ERROR batch=%s; lease will expire',batch_id)
