import logging
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from database.connection import connection
from database.schema import verify_data
from domain.models import COLUMNS, check_cancel
from repositories.import_lock_repository import ImportLockRepository, LOCK_NAME
logger = logging.getLogger(__name__)
BATCH_SIZE = 5000

class DataRepository:
    def __init__(self, path):
        self.path = path

    def replace_from_staging(self, stage_path, batch_id, progress, cancel=None):
        started = time.monotonic()
        with closing(sqlite3.connect(str(stage_path))) as stage:
            counts = stage.execute('SELECT File_Date,COUNT(*) FROM data GROUP BY File_Date ORDER BY File_Date').fetchall()
            if not counts:
                raise ValueError('Không có dòng SLOT_END hợp lệ. Không xóa dữ liệu cũ.')
            with connection(self.path) as conn:
                verify_data(conn)
                check_cancel(cancel)
                progress('Đang chờ quyền ghi database (tối đa 60 giây cho mỗi thao tác khóa)…')
                conn.execute('BEGIN IMMEDIATE')
                ImportLockRepository.assert_owner(conn, batch_id)
                conn.execute('CREATE TEMP TABLE replace_dates(File_Date TEXT PRIMARY KEY)')
                conn.executemany('INSERT INTO replace_dates VALUES(?)', [(d,) for d,n in counts])
                check_cancel(cancel)
                logger.info('REPLACE_BEGIN batch=%s dates=%s', batch_id, counts)
                cur = conn.execute('DELETE FROM data WHERE File_Date IN (SELECT File_Date FROM replace_dates)')
                deleted = cur.rowcount
                logger.info('DELETE_DONE batch=%s rows=%s', batch_id, deleted)
                progress(f'Đã xóa tạm {deleted:,} dòng cũ; đang ghi dữ liệu mới (chưa commit).')
                sql = f'INSERT INTO data({",".join(COLUMNS)}) VALUES({",".join("?" for _ in COLUMNS)})'
                cursor = stage.execute(f'SELECT {",".join(COLUMNS)} FROM data ORDER BY ID')
                inserted = 0
                while True:
                    check_cancel(cancel)
                    rows = cursor.fetchmany(BATCH_SIZE)
                    if not rows:
                        break
                    conn.executemany(sql, rows)
                    inserted += len(rows)
                    progress(f'Đang ghi database: {inserted:,} dòng (chưa commit).')
                now = datetime.now(timezone.utc).isoformat()
                conn.executemany('''INSERT INTO arts_import_status VALUES(?,?,?,?)
                    ON CONFLICT(File_Date) DO UPDATE SET batch_id=excluded.batch_id,
                    imported_at=excluded.imported_at,row_count=excluded.row_count''',
                    [(day,batch_id,now,n) for day,n in counts])
                conn.execute('UPDATE arts_data_revision SET revision=revision+1 WHERE singleton=1')
                check_cancel(cancel)
                # Release atomically with data commit. Writer transaction prevents takeover.
                conn.execute('DELETE FROM arts_import_lock WHERE lock_name=? AND batch_id=?', (LOCK_NAME,batch_id))
                progress('Đang commit dữ liệu; vui lòng đợi kết quả…')
                check_cancel(cancel)
                conn.commit()
                logger.info('COMMIT_OK batch=%s inserted=%s deleted=%s elapsed=%.3f', batch_id, inserted,deleted,time.monotonic()-started)
        return tuple(day for day,n in counts), inserted, deleted
