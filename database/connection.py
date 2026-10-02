"""A separate connection per task; no connection survives its context."""
import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
logger = logging.getLogger(__name__)

@contextmanager
def connection(path, timeout=60):
    path = Path(path)
    if not path.parent.is_dir():
        raise FileNotFoundError(f'Không truy cập được folder database: {path.parent}')
    start = time.monotonic()
    conn = sqlite3.connect(str(path), timeout=timeout, isolation_level=None)
    logger.info('DB_OPEN path=%s timeout=%s', path, timeout)
    try:
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA synchronous=FULL')
        conn.execute(f'PRAGMA busy_timeout={int(timeout*1000)}')
        yield conn
    except BaseException:
        logger.exception('DB_ERROR transaction=%s elapsed=%.3f', conn.in_transaction, time.monotonic()-start)
        raise
    finally:
        try:
            if conn.in_transaction:
                conn.rollback()
                logger.info('DB_ROLLBACK')
        finally:
            conn.close()
            logger.info('DB_CLOSE elapsed=%.3f', time.monotonic()-start)
