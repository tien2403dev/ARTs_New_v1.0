"""LI-style shared lease. SQLite transaction ownership is checked before DELETE."""
import getpass
import logging
import os
import socket
import time
import uuid
from threading import Event, Thread
from database.connection import connection
from domain.models import ImportBusyError, LockLostError
logger = logging.getLogger(__name__)
LOCK_NAME = 'ARTS_GLOBAL_IMPORT'
LEASE_SECONDS = 900

class ImportLockRepository:
    def __init__(self, path):
        self.path = path

    def acquire(self, source):
        batch_id = uuid.uuid4().hex
        with connection(self.path) as conn:
            conn.execute('BEGIN IMMEDIATE')
            now = time.time()
            row = conn.execute('SELECT owner,expires_at FROM arts_import_lock WHERE lock_name=?', (LOCK_NAME,)).fetchone()
            if row and row[1] > now:
                raise ImportBusyError(f'Đang có phiên import trên {row[0]}. Vui lòng đợi hoàn tất.')
            conn.execute('DELETE FROM arts_import_lock WHERE lock_name=?', (LOCK_NAME,))
            conn.execute('INSERT INTO arts_import_lock VALUES(?,?,?,?,?,?)',
                         (LOCK_NAME, batch_id, f'{socket.gethostname()}/{getpass.getuser()}/{os.getpid()}', str(source), now, now+LEASE_SECONDS))
            conn.commit()
        logger.info('LOCK_ACQUIRED batch=%s', batch_id)
        return batch_id

    @staticmethod
    def assert_owner(conn, batch_id):
        row = conn.execute('SELECT batch_id,expires_at FROM arts_import_lock WHERE lock_name=?', (LOCK_NAME,)).fetchone()
        if not row or row[0] != batch_id or row[1] <= time.time():
            raise LockLostError('Phiên import mất hoặc hết hạn khóa. Không thay thế dữ liệu.')

    @staticmethod
    def renew(conn, batch_id):
        now = time.time()
        cur = conn.execute('UPDATE arts_import_lock SET heartbeat_at=?,expires_at=? WHERE lock_name=? AND batch_id=?',
                           (now, now+LEASE_SECONDS, LOCK_NAME, batch_id))
        if cur.rowcount != 1:
            raise LockLostError('Phiên import không còn giữ khóa.')

    def refresh(self, batch_id):
        with connection(self.path, timeout=2) as conn:
            conn.execute('BEGIN IMMEDIATE')
            self.assert_owner(conn, batch_id)
            self.renew(conn, batch_id)
            conn.commit()

    def release(self, batch_id):
        with connection(self.path, timeout=2) as conn:
            conn.execute('DELETE FROM arts_import_lock WHERE lock_name=? AND batch_id=?', (LOCK_NAME,batch_id))
        logger.info('LOCK_RELEASED batch=%s', batch_id)

class ImportHeartbeat:
    def __init__(self, repository, batch_id):
        self.repository, self.batch_id = repository, batch_id
        self.stopped, self.lost = Event(), Event()
        self.thread = Thread(target=self._run, name='ARTsImportHeartbeat', daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stopped.set()
        self.thread.join(5)
        if self.thread.is_alive():
            raise TimeoutError('Heartbeat chưa dừng. Không bắt đầu thay dữ liệu.')

    def _run(self):
        while not self.stopped.wait(30):
            try:
                self.repository.refresh(self.batch_id)
            except LockLostError:
                self.lost.set()
                return
            except Exception:
                logger.exception('HEARTBEAT_ERROR batch=%s', self.batch_id)
