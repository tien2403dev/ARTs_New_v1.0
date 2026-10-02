"""LI-style distinct index seeks, one snapshot per load; no test rows sent to UI."""
from pathlib import Path
from database.connection import connection

FIELDS = ('EQP', 'Handler', 'ZONE', 'SLOT', 'Model', 'SCRAP')

def ensure_filter_indexes(conn):
    for column in FIELDS:
        conn.execute(f'CREATE INDEX IF NOT EXISTS idx_arts_filter_{column} ON data({column})')

def scrap_codes(texts):
    codes = set()
    for text in texts:
        for entry in str(text or '').split(','):
            code = entry.strip().split(':')[0].strip()
            if code:
                codes.add('0000' if code == '0' else code)
    return sorted(codes)

class FilterOptionRepository:
    def __init__(self, path):
        self.path = path

    def load_options(self, cancel, known_revision=None):
        if not Path(self.path).is_file():
            return {'revision': None, 'options': {key: [] for key in FIELDS}}
        with connection(self.path, timeout=2) as conn:
            conn.set_progress_handler(lambda: int(cancel.is_set()), 1000)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'data' not in tables:
                return {'revision': None, 'options': {key: [] for key in FIELDS}}
            indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
            if any('idx_arts_filter_'+key not in indexes for key in FIELDS):
                conn.execute('BEGIN IMMEDIATE')
                ensure_filter_indexes(conn)
                conn.commit()
            conn.execute('BEGIN')
            revision = conn.execute('SELECT revision FROM arts_data_revision WHERE singleton=1').fetchone()[0] if 'arts_data_revision' in tables else None
            if revision is not None and revision == known_revision:
                return {'revision': revision, 'options': None}
            def values(column):
                sql = f'''WITH RECURSIVE options(value) AS (
                    SELECT MIN({column}) FROM data
                    UNION ALL
                    SELECT (SELECT MIN({column}) FROM data WHERE {column}>options.value)
                    FROM options WHERE value IS NOT NULL
                ) SELECT value FROM options WHERE value IS NOT NULL'''
                return [row[0] for row in conn.execute(sql) if str(row[0]).strip()]
            options = {key: values(key) for key in FIELDS}
            options['SCRAP'] = scrap_codes(options['SCRAP'])
            return {'revision': revision, 'options': options}
