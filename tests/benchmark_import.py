"""Synthetic LOCAL benchmark; not a network-share performance claim."""
import argparse
import contextlib
import json
import sqlite3
import tempfile
import time
from pathlib import Path
from services.import_service import ImportService
from tests.test_import import line

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--rows',type=int,default=1000000)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='arts_bench_') as t:
        root=Path(t);logs=root/'logs';logs.mkdir()
        for i in range(50):
            folder=logs/f'Machine{i:02d}'/'2026-10'/'nested';folder.mkdir(parents=True)
            n=args.rows//50+(i<args.rows%50)
            (folder/'2026-10-01.txt').write_text(line(eqp=f'FT-H{i:03d}A')*n)
        service=ImportService(root/'bench.db')
        start=time.perf_counter();first=service.import_folder(logs,'2026-10-01','2026-10-01');first_s=time.perf_counter()-start
        start=time.perf_counter();second=service.import_folder(logs,'2026-10-01','2026-10-01');second_s=time.perf_counter()-start
        with contextlib.closing(sqlite3.connect(root/'bench.db')) as c:
            count=c.execute('SELECT COUNT(*) FROM data').fetchone()[0]
            integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
        assert first.inserted==second.inserted==second.deleted==count==args.rows
        assert integrity=='ok'
        print(json.dumps({'files':50,'rows':count,'first_seconds':round(first_s,3),'replace_seconds':round(second_s,3),'integrity':integrity,'database_bytes':(root/'bench.db').stat().st_size,'location':'local Linux filesystem, synthetic logs'},indent=2))
if __name__=='__main__':main()
