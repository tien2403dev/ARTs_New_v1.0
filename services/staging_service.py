import logging
import os
import time
import sqlite3
from pathlib import Path
from database.schema import DATA_SQL
from domain.models import COLUMNS, check_cancel
from services.log_parser import iter_records, transform_rows
logger = logging.getLogger(__name__)
BATCH_SIZE = 5000


def stage_files(files, stage_path, progress, cancel=None):
    conn = sqlite3.connect(str(stage_path))
    sql = f'INSERT INTO data({",".join(COLUMNS)}) VALUES({",".join("?" for _ in COLUMNS)})'
    try:
        conn.execute(DATA_SQL)
        counts = {}
        for index, (source, day) in enumerate(files, 1):
            check_cancel(cancel)
            # Keep only one file snapshot locally. Cap at size observed when opening,
            # so a file continuously appended by the machine cannot extend the import forever.
            snapshot = Path(stage_path).parent / source.name
            started = time.monotonic()
            logger.info('FILE_BEGIN index=%s file=%s', index, source)
            with source.open('rb') as inp, snapshot.open('wb') as out:
                remaining = os.fstat(inp.fileno()).st_size
                while remaining:
                    check_cancel(cancel)
                    chunk = inp.read(min(1024*1024, remaining))
                    if not chunk:
                        raise OSError(f'File bị thu ngắn khi đang đọc: {source}')
                    out.write(chunk)
                    remaining -= len(chunk)
            rows, count = [], 0
            for row in iter_records(snapshot, cancel):
                rows.append(row)
                if len(rows) >= BATCH_SIZE:
                    conn.executemany(sql, transform_rows(rows))
                    count += len(rows)
                    rows.clear()
                    progress(f'Đọc {index}/{len(files)}: {source.name} — {count:,} dòng')
            if rows:
                conn.executemany(sql, transform_rows(rows))
                count += len(rows)
            conn.commit()
            counts[day] = counts.get(day, 0) + count
            snapshot.unlink()
            logger.info('FILE_END file=%s rows=%s seconds=%.3f', source, count, time.monotonic()-started)
            progress(f'Đã đọc {index}/{len(files)} file — {source.name}: {count:,} dòng')
        conn.execute('CREATE INDEX staging_day ON data(File_Date)')
        conn.commit()
        return counts
    finally:
        conn.close()
