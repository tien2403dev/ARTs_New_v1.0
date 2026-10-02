import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sqlite3, tempfile, threading, unittest, time
from pathlib import Path
from types import SimpleNamespace
from database.schema import DATA_SQL
from repositories.machine_yield_repository import MachineYieldRepository, build_query

class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'test.db'
        with sqlite3.connect(self.path) as c:
            c.execute(DATA_SQL)
            c.executemany('INSERT INTO data(File_Date,EQP,Qty,Fail,Handler,ZONE,SLOT,Model,SCRAP) VALUES(?,?,?,?,?,?,?,?,?)',[
                ('20261001','A',100,10,'A','Z1',1,'M1','1234:10'),
                ('20261002','A',50,0,'B','Z2',2,'M2','0:50'),
                ('20261002','B',10,5,'A','Z1',1,'M1','12345:5'),
                ('20261002','C',0,0,'A','Z1',1,'M1',''),
                ('20260930','A',999,999,'A','Z1',1,'M1','1234:999')])
        self.criteria=dict(date_from='20261001',date_to='20261002',eqp=None,handler=None,zone=None,slot=None,models=[],scrap_codes=[])
    def tearDown(self):self.temp.cleanup()
    def load(self,**changes):return MachineYieldRepository(self.path).load(dict(self.criteria,**changes),threading.Event())
    def test_totals_dates_zero_migration(self):
        rows,total=self.load()
        self.assertEqual([(r.eqpid,r.in_qty,r.fail_qty) for r in rows],[('A',150,10),('B',10,5),('C',0,0)])
        self.assertEqual((total.out_qty,total.yield_percent,total.fail_ppm),(145,90.625,93750))
        self.assertIsNone(rows[2].yield_percent);self.assertEqual(self.load(),(rows,total))
        self.assertEqual(self.load(date_from='20270101',date_to='20270102')[0],[])
    def test_filters_exact_codes(self):
        self.assertEqual(self.load(eqp='A',handler='B',zone='Z2',slot=2,models=['M2'])[1].in_qty,50)
        self.assertEqual(self.load(scrap_codes=['1234'])[1].in_qty,100)
        self.assertEqual(self.load(scrap_codes=['0000'])[1].in_qty,50)
        self.assertEqual(self.load(models=['M1'])[1].in_qty,110)
    def test_covering_plans(self):
        self.load()
        with sqlite3.connect(self.path) as c:
            for eqp in [None,'A']:
                sql,args=build_query(dict(self.criteria,eqp=eqp))
                plan=' '.join(r[3] for r in c.execute('EXPLAIN QUERY PLAN '+sql,args))
                self.assertIn('USING COVERING INDEX',plan);self.assertIn('SEARCH data',plan)
    def test_copy_tooltip_empty(self):
        from PyQt5.QtCore import QItemSelectionModel
        from PyQt5.QtWidgets import QApplication
        from ui.pages.summary_page import SummaryPage
        app=QApplication.instance() or QApplication([])
        page=SummaryPage();page.resize(1650,650);page.show()
        page.load_result(self.load(),self.criteria);app.processEvents();page.chart.draw()
        selection=page.table.selectionModel()
        for r,c in [(0,1),(0,3),(1,1)]:selection.select(page.model.index(r,c),QItemSelectionModel.Select)
        page.table.copy_selection();self.assertEqual(app.clipboard().text(),'In Qty\tFail Qty\n150\t10\n10\t')
        bar=page.chart.hover.bars[0][0];x,y=bar.get_transform().transform((.5,.5))
        self.assertIn('A',page.chart.hover.hit_text(SimpleNamespace(x=x,y=y)))
        page.grab().save(str(Path(__file__).parents[2]/'summary_preview.png'))
        page.load_result(self.load(date_from='20270101',date_to='20270102'),self.criteria)
        self.assertEqual(page.model.rowCount(),0);self.assertFalse(page.chart.hover.bars);self.assertFalse(page.chart.figure.legends)
        page.close()
    def test_worker_lifecycle(self):
        from unittest.mock import patch
        from PyQt5.QtWidgets import QApplication
        from ui.main_window import MainWindow
        app=QApplication.instance() or QApplication([]);w=MainWindow();w.import_panel.set_ready(True)
        with patch.dict(os.environ,{'ARTS_DB_PATH':str(self.path)}):
            w.apply_filters(self.criteria);self.assertTrue(w.import_panel.search_busy)
            deadline=time.monotonic()+20
            while w.summary_controller.worker is not None and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
            self.assertIsNone(w.summary_controller.worker);self.assertFalse(w.import_panel.search_busy)
            self.assertEqual(w.summary_page.model.rowCount(),4)
        w.close();app.processEvents()

if __name__=='__main__':unittest.main()
