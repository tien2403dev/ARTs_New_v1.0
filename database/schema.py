from database.connection import connection
from domain.models import COLUMNS

DATA_SQL = '''CREATE TABLE IF NOT EXISTS data (
 ID INTEGER PRIMARY KEY AUTOINCREMENT,
 LOTID TEXT, File_Date TEXT, Datetime TEXT, EQP TEXT, Handler TEXT,
 ZONE TEXT, SLOT INTEGER, Model TEXT, Qty INTEGER, Fail INTEGER,
 SCRAP TEXT, FULLSITE TEXT, BIN TEXT, BCODE TEXT
)'''

def verify_data(conn):
    columns = tuple(r[1] for r in conn.execute('PRAGMA table_info(data)'))
    if columns != ('ID',) + COLUMNS:
        raise ValueError('Bảng data không đúng cấu trúc ARTs gốc. Không thay đổi dữ liệu.')

def initialize_database(path):
    with connection(path) as conn:
        mode = conn.execute('PRAGMA journal_mode').fetchone()[0].lower()
        if mode == 'wal':
            raise ValueError('Database đang dùng WAL. Hãy chọn database mới dùng DELETE journal cho ổ mạng.')
        if mode != 'delete':
            conn.execute('PRAGMA journal_mode=DELETE')
        # This deliverable is the NEW app's import module, not a writer for old derived tables.
        old = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if old.intersection({'alarm_summary', 'fail_history', 'eqp_master', 'date_master'}):
            raise ValueError('Đây là database app ARTs cũ có bảng phụ thuộc. Hãy chọn tên database mới cho ARTs Import v1 để tránh làm lệch Summary/Alarm của app cũ.')
        conn.execute('BEGIN IMMEDIATE')
        conn.execute(DATA_SQL)
        verify_data(conn)
        from repositories.filter_option_repository import ensure_filter_indexes
        ensure_filter_indexes(conn)
        from repositories.machine_yield_repository import ensure_summary_indexes
        ensure_summary_indexes(conn)
        conn.execute('CREATE INDEX IF NOT EXISTS idx_arts_data_file_date ON data(File_Date)')
        conn.execute('''CREATE TABLE IF NOT EXISTS arts_import_lock(
            lock_name TEXT PRIMARY KEY, batch_id TEXT NOT NULL, owner TEXT NOT NULL,
            source TEXT NOT NULL, heartbeat_at REAL NOT NULL, expires_at REAL NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS arts_import_status(
            File_Date TEXT PRIMARY KEY, batch_id TEXT NOT NULL, imported_at TEXT NOT NULL,
            row_count INTEGER NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS arts_data_revision(
            singleton INTEGER PRIMARY KEY CHECK(singleton=1), revision INTEGER NOT NULL)''')
        conn.execute('INSERT OR IGNORE INTO arts_data_revision VALUES(1,0)')
        conn.commit()
