"""Build machine and selected Handler daily results with one indexed scan."""
from collections import Counter
from datetime import datetime, timedelta
from domain.daily_summary import DailyYieldRow, DailyYieldResult
from domain.zone_summary import ZONES, ZoneYieldRow, ZoneYieldResult
from repositories.machine_yield_repository import build_query


def parse_scrap_occurrences(text):
    counts = Counter()
    for item in str(text or '').split(','):
        code = item.split(':', 1)[0].strip()
        if not code or code == '-':
            continue
        counts['0000' if code == '0' else code] += 1
    return counts


def _add_group(quantities, codes_by_day, date, qty, fail, counts, frequency):
    totals = quantities.setdefault(date, [0, 0])
    totals[0] += int(qty or 0)
    totals[1] += int(fail or 0)
    day_counts = codes_by_day.setdefault(date, Counter())
    for code, count in counts.items():
        day_counts[code] += count * frequency


def _result(eqp, handler, quantities, codes_by_day, criteria, cancel):
    start = datetime.strptime(criteria['date_from'], '%Y%m%d').date()
    end = datetime.strptime(criteria['date_to'], '%Y%m%d').date()
    if start > end:
        raise ValueError('From phải nhỏ hơn hoặc bằng To.')
    rows = []
    day = start
    while day <= end:
        if cancel.is_set():
            raise InterruptedError('Đã hủy Search.')
        date = day.strftime('%Y%m%d')
        qty, fail = quantities.get(date, (0, 0))
        rows.append(DailyYieldRow(date, qty, fail, dict(codes_by_day.get(date, {}))))
        day += timedelta(days=1)
    codes = sorted({code for counts in codes_by_day.values() for code in counts})
    return DailyYieldResult(eqp, codes, rows, handler)


def load_daily_summaries(conn, criteria, cancel, include_zones=False):
    eqp, handler = criteria.get('eqp'), criteria.get('handler')
    if not eqp:
        results = (DailyYieldResult(None, [], []), DailyYieldResult(None, [], []))
        return (*results, ZoneYieldResult(None, None, [])) if include_zones else results
    # Machine Daily covers all handlers. Scrap selection only controls the chart.
    sql, params = build_query(dict(criteria, scrap_codes=[], handler=None, zone=None))
    where = sql.split('WHERE ', 1)[1].split(' GROUP BY ', 1)[0]
    groups = conn.execute(f'''SELECT File_Date, Handler, ZONE, SCRAP, (Fail > 0),
                                    SUM(Qty), SUM(Fail), COUNT(*)
                             FROM data INDEXED BY idx_arts_summary_eqp_date_cover
                             WHERE {where}
                             GROUP BY File_Date, Handler, ZONE, SCRAP, (Fail > 0)''', params)
    machine_qty, machine_codes, handler_qty, handler_codes = {}, {}, {}, {}
    zone_qty = {zone: [0, 0] for zone in ZONES}
    for date, group_handler, zone, scrap, is_fail, qty, fail, frequency in groups:
        if cancel.is_set():
            raise InterruptedError('Đã hủy Search.')
        counts = parse_scrap_occurrences(scrap) if is_fail else {}
        matches_handler = handler is not None and handler != '' and group_handler == handler
        if not criteria.get('zone') or zone == criteria['zone']:
            _add_group(machine_qty, machine_codes, date, qty, fail, counts, frequency)
            if matches_handler:
                _add_group(handler_qty, handler_codes, date, qty, fail, counts, frequency)
        if matches_handler and zone in zone_qty:
            zone_qty[zone][0] += int(qty or 0)
            zone_qty[zone][1] += int(fail or 0)
    machine = _result(eqp, None, machine_qty, machine_codes, criteria, cancel)
    selected = (_result(eqp, handler, handler_qty, handler_codes, criteria, cancel)
                if handler is not None and handler != '' else DailyYieldResult(eqp, [], []))
    zones = ZoneYieldResult(eqp, handler, [ZoneYieldRow(zone, *zone_qty[zone]) for zone in ZONES]
                            if handler is not None and handler != '' else [])
    return (machine, selected, zones) if include_zones else (machine, selected)


def load_daily_summary(conn, criteria, cancel):
    """Compatibility entry point for the machine Daily result."""
    return load_daily_summaries(conn, criteria, cancel)[0]
