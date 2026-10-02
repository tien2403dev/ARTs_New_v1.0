import os
from datetime import datetime, timedelta
from pathlib import Path
from domain.models import check_cancel

def selected_dates(date_from, date_to):
    start, end = (datetime.strptime(x, '%Y-%m-%d').date() for x in (date_from, date_to))
    if start > end:
        raise ValueError('From phải nhỏ hơn hoặc bằng To.')
    return tuple((start+timedelta(days=i)).strftime('%Y%m%d') for i in range((end-start).days+1))

def discover_files(root, dates, cancel=None):
    if not Path(root).is_dir():
        raise FileNotFoundError(f'Không truy cập được folder log: {root}')
    prefixes = {f'{d[:4]}-{d[4:6]}-{d[6:]}': d for d in dates}
    found = []
    def onerror(error):
        raise error  # Never replace a day after silently skipping an inaccessible machine.
    for folder, dirs, files in os.walk(root, onerror=onerror, followlinks=False):
        check_cancel(cancel)
        dirs.sort()
        for name in sorted(files):
            if name.lower().endswith('.txt') and name[:10] in prefixes:
                found.append((Path(folder)/name, prefixes[name[:10]]))
    return found
