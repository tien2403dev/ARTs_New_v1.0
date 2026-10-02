"""Aggregate ARTs quantities in SQLite; return only one row per machine."""
from dataclasses import dataclass
from pathlib import Path
from database.connection import connection
from repositories.filter_option_repository import scrap_codes

INDEXES = {
    'idx_arts_summary_date_cover': 'File_Date, EQP, Qty, Fail, Handler, ZONE, SLOT, Model, SCRAP',
    'idx_arts_summary_eqp_date_cover': 'EQP, File_Date, Qty, Fail, Handler, ZONE, SLOT, Model, SCRAP',
}


def ensure_summary_indexes(conn):
    for name, columns in INDEXES.items():
        conn.execute(f'CREATE INDEX IF NOT EXISTS {name} ON data({columns})')


@dataclass(frozen=True)
class MachineYieldRow:
    eqpid: str
    in_qty: int
    fail_qty: int

    @property
    def out_qty(self):
        return self.in_qty - self.fail_qty

    @property
    def fail_ppm(self):
        return self.fail_qty * 1_000_000 / self.in_qty if self.in_qty else None

    @property
    def yield_percent(self):
        return self.out_qty * 100 / self.in_qty if self.in_qty else None


def build_query(criteria):
    clauses = ['File_Date >= ?', 'File_Date <= ?']
    params = [criteria['date_from'], criteria['date_to']]
    for key, column in [('eqp', 'EQP'), ('handler', 'Handler'), ('zone', 'ZONE'), ('slot', 'SLOT')]:
        value = criteria.get(key)
        if value is not None and value != '':
            clauses.append(f'{column} = ?')
            params.append(value)
    models = criteria.get('models') or []
    if models:
        clauses.append('Model IN (' + ','.join('?' for _ in models) + ')')
        params.extend(models)
    if criteria.get('scrap_codes'):
        clauses.append('arts_has_scrap(SCRAP) = 1')
    index = 'idx_arts_summary_eqp_date_cover' if criteria.get('eqp') else 'idx_arts_summary_date_cover'
    sql = f'''SELECT EQP, COALESCE(SUM(Qty),0), COALESCE(SUM(Fail),0)
              FROM data INDEXED BY {index}
              WHERE {' AND '.join(clauses)} GROUP BY EQP ORDER BY EQP'''
    return sql, params


class MachineYieldRepository:
    def __init__(self, path):
        self.path = path

    def load(self, criteria, cancel, progress=lambda text: None, include_daily=False):
        if not Path(self.path).is_file():
            raise FileNotFoundError('Chưa có database. Hãy import dữ liệu trước.')
        with connection(self.path, timeout=1) as conn:
            conn.set_progress_handler(lambda: int(cancel.is_set()), 1000)
            indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
            if not set(INDEXES).issubset(indexes):
                progress('Đang tạo index lần đầu…')
                conn.execute('BEGIN IMMEDIATE')
                ensure_summary_indexes(conn)
                conn.commit()
            conn.execute('BEGIN')
            selected = set(criteria.get('scrap_codes') or [])
            # Match entire codes, including the parser's 0 -> 0000 display alias.
            # A scrap filter selects whole records; Qty and Fail retain ARTs semantics.
            if selected:
                conn.create_function('arts_has_scrap', 1,
                                     lambda value: int(bool(selected.intersection(scrap_codes([value])))))
            progress('Đang thống kê yield…')
            sql, params = build_query(criteria)
            rows = [MachineYieldRow(str(eqp or ''), int(qty), int(fail))
                    for eqp, qty, fail in conn.execute(sql, params)]
            daily = handler_daily = zones = None
            if include_daily:
                progress('Đang thống kê mã lỗi theo ngày…')
                from repositories.daily_summary_repository import load_daily_summaries
                daily, handler_daily, zones = load_daily_summaries(conn, criteria, cancel, include_zones=True)
            conn.commit()
        total = MachineYieldRow('Total', sum(r.in_qty for r in rows), sum(r.fail_qty for r in rows))
        return (rows, total, daily, handler_daily, zones) if include_daily else (rows, total)
