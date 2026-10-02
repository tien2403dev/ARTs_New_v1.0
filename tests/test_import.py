import contextlib
import importlib.util
import io
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from domain.models import COLUMNS, ImportBusyError, ImportCancelled, LockLostError
from services.import_service import ImportService
from services.file_discovery import discover_files, selected_dates
from services.log_parser import iter_records, transform_rows
from database.schema import initialize_database
from database.connection import connection
from repositories.import_lock_repository import ImportLockRepository
from repositories.data_repository import DataRepository
from services.staging_service import stage_files

def line(lot='LOT1', bins='01239-X', eqp='FT-H001A', time_text='10:11:12', slot='3'):
    return f'DATE[{time_text}] FUNCTION=SLOT_END BCODE=ABCDEFGHIJKLP7ABC999 LOTID={lot} X=0 FULLSITE=111 EQPID={eqp} SLOT={slot} BIN={bins} X=0 ZONE=A SCRAP=A1\n'

class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.logs = self.root/'logs';self.logs.mkdir()
        self.db = self.root/'arts.db'
        self.service = ImportService(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def file(self,name='2026-10-01.txt',content=None,machine='Machine1/2026-10/deep'):
        p = self.logs/machine/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(line() if content is None else content,encoding='utf-8')
        return p

    def run_import(self,start='2026-10-01',end='2026-10-01',**kwargs):
        return self.service.import_folder(self.logs,start,end,**kwargs)

    def rows(self):
        with contextlib.closing(sqlite3.connect(self.db)) as c:
            return c.execute('SELECT '+','.join(COLUMNS)+' FROM data ORDER BY ID').fetchall()

    def test_parser_matches_old(self):
        p=self.file(content=line()+line('LOT2',eqp='FT-H002B',time_text='bad')+'FUNCTION=SLOT_END bad\n'+'ignore\n')
        spec=importlib.util.spec_from_file_location('legacy',Path(__file__).parents[1]/'reference/arts_import_original.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        with contextlib.redirect_stdout(io.StringIO()):
            expected=mod.load_log_date(str(self.logs),'2026-10-01').rename(columns={'QTY':'Qty'})
        expected=expected.loc[:,COLUMNS].astype(object).where(expected.loc[:,COLUMNS].notna(),None)
        self.assertEqual(list(expected.itertuples(index=False,name=None)),list(transform_rows(list(iter_records(p)))))

    def test_recursive_dates_and_case(self):
        self.file();self.file('2026-10-02_extra.TXT',machine='Machine2')
        self.file('2026-09-30.txt');self.file('20261001.txt');self.file('notes.txt')
        self.assertEqual(len(discover_files(self.logs,selected_dates('2026-10-01','2026-10-02'))),2)
        result=self.run_import(end='2026-10-02')
        self.assertEqual((result.inserted,result.files),(2,2))
        self.assertEqual(result.dates,('20261001','20261002'))

    def test_replace_whole_day_all_machines_keep_other_days(self):
        a=self.file();b=self.file(machine='Machine2');self.file('2026-10-02.txt')
        self.run_import(end='2026-10-02')
        b.unlink();a.write_text(line('NEW'),encoding='utf-8')
        result=self.run_import()
        self.assertEqual((result.deleted,result.inserted),(2,1))
        self.assertEqual(len(self.rows()),2)
        self.assertEqual({r[0] for r in self.rows()},{'LOT1','NEW'})
        self.assertEqual(self.run_import().inserted,1)
        self.assertEqual(len(self.rows()),2)

    def test_missing_day_kept(self):
        first=self.file();self.run_import();first.unlink()
        self.file('2026-10-02.txt')
        result=self.run_import(end='2026-10-02')
        self.assertEqual(result.missing_dates,('20261001',));self.assertEqual(len(self.rows()),2)

    def test_empty_day_kept(self):
        p=self.file();self.run_import();p.write_text('NO SLOT_END\n')
        self.file('2026-10-02.txt')
        result=self.run_import(end='2026-10-02')
        self.assertEqual(result.empty_dates,('20261001',));self.assertEqual(len(self.rows()),2)

    def test_no_file_no_db_created(self):
        with self.assertRaises(ValueError):self.run_import()
        self.assertFalse(self.db.exists())

    def test_all_empty_does_not_delete(self):
        p=self.file();self.run_import();before=self.rows();p.write_text('nothing')
        with self.assertRaises(ValueError):self.run_import()
        self.assertEqual(before,self.rows())

    def test_cancel_after_delete_rolls_back(self):
        p=self.file();self.run_import();before=self.rows();p.write_text(line('NEW'))
        cancel=threading.Event()
        def progress(message):
            if 'Đã xóa tạm' in message:cancel.set()
        with self.assertRaises(ImportCancelled):self.run_import(progress=progress,cancel=cancel)
        self.assertEqual(before,self.rows())
        self.assertEqual(self.run_import().inserted,1)

    def test_sql_error_after_delete_rolls_back(self):
        p=self.file();self.run_import();before=self.rows();p.write_text(line('BAD'))
        with connection(self.db) as c:
            c.execute("CREATE TRIGGER reject_bad BEFORE INSERT ON data WHEN NEW.LOTID='BAD' BEGIN SELECT RAISE(ABORT,'injected failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.run_import()
        self.assertEqual(before,self.rows())
        with connection(self.db) as c:
            self.assertEqual(c.execute('SELECT revision FROM arts_data_revision').fetchone()[0],1)

    def test_active_import_lock(self):
        self.file();initialize_database(self.db)
        locks=ImportLockRepository(self.db);batch=locks.acquire('test')
        try:
            with self.assertRaises(ImportBusyError):self.run_import()
        finally:locks.release(batch)
        self.assertEqual(self.run_import().inserted,1)

    def test_expired_lock_and_stale_owner(self):
        initialize_database(self.db);locks=ImportLockRepository(self.db)
        first=locks.acquire('first')
        with connection(self.db) as c:c.execute('UPDATE arts_import_lock SET expires_at=0')
        second=locks.acquire('second');locks.release(first)
        with connection(self.db) as c:
            with self.assertRaises(LockLostError):locks.assert_owner(c,first)
            locks.assert_owner(c,second)
        locks.release(second)

    def test_unreadable_source_does_not_delete(self):
        p=self.file();self.run_import();before=self.rows()
        real_open=Path.open
        def fail_open(path,*args,**kwargs):
            if path==p and args and args[0]=='rb':raise PermissionError('test unreadable')
            return real_open(path,*args,**kwargs)
        with patch.object(Path,'open',fail_open):
            with self.assertRaises(PermissionError):self.run_import()
        self.assertEqual(before,self.rows())

    def test_source_changes_after_snapshot(self):
        p=self.file()
        from services import staging_service
        original=staging_service.iter_records
        def read_after_change(snapshot,cancel):
            p.write_text(line('CHANGED'))
            return original(snapshot,cancel)
        with patch.object(staging_service,'iter_records',read_after_change):self.run_import()
        self.assertEqual(self.rows()[0][0],'LOT1')

    def test_schema_and_batch_boundary(self):
        self.file(content=line()*5001);result=self.run_import()
        self.assertEqual(result.inserted,5001)
        with connection(self.db) as c:
            self.assertEqual(tuple(r[1] for r in c.execute('PRAGMA table_info(data)')),('ID',)+COLUMNS)
            self.assertEqual(c.execute('PRAGMA journal_mode').fetchone()[0],'delete')
            self.assertEqual(c.execute('SELECT Qty,Fail,Model,Handler,EQP,Datetime FROM data LIMIT 1').fetchone(),
                             (5,3,'P7ABC','A','FT-H001','2026-10-01 10:11:12'))

    def test_reader_sees_old_until_commit(self):
        p=self.file();self.run_import();p.write_text(line('NEW'))
        seen=[]
        def observe(message):
            if 'Đã xóa tạm' in message:seen.extend(self.rows())
        self.run_import(progress=observe)
        self.assertEqual(seen[0][0],'LOT1');self.assertEqual(self.rows()[0][0],'NEW')

    def test_reject_old_app_db(self):
        self.file()
        with sqlite3.connect(self.db) as c:c.execute('CREATE TABLE eqp_master(EQP TEXT)')
        with self.assertRaisesRegex(ValueError,'app ARTs cũ'):self.run_import()

    def test_invalid_range(self):
        with self.assertRaises(ValueError):selected_dates('2026-10-02','2026-10-01')

if __name__=='__main__':unittest.main()
