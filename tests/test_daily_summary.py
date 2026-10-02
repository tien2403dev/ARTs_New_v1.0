import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sqlite3, tempfile, threading, unittest
from pathlib import Path
from types import SimpleNamespace
from database.schema import DATA_SQL
from repositories.machine_yield_repository import MachineYieldRepository
from repositories.daily_summary_repository import parse_scrap_occurrences

class DailyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'test.db'
        with sqlite3.connect(self.path) as c:
            c.execute(DATA_SQL)
            c.executemany('INSERT INTO data(File_Date,EQP,Qty,Fail,Handler,ZONE,SLOT,Model,SCRAP) VALUES(?,?,?,?,?,?,?,?,?)',[
                ('20261001','A',100,3,'H','Z',1,'M','1234:9,1234:8,5678:2'),
                ('20261001','A',100,3,'H','Z',1,'M','1234:9,1234:8,5678:2'),
                ('20261001','A',800,0,'H','Z',1,'M','1234:99'),
                ('20261003','A',100,1,'H','Z',1,'M','0:12'),
                ('20261001','B',999,1,'H','Z',1,'M','8888:1')])
        self.criteria=dict(date_from='20261001',date_to='20261003',eqp='A',handler=None,zone=None,slot=None,models=[],scrap_codes=['1234','9999'])
    def tearDown(self):self.temp.cleanup()
    def load(self,**changes):
        return MachineYieldRepository(self.path).load(dict(self.criteria,**changes),threading.Event(),include_daily=True)[2]
    def test_occurrences_denominator_boundaries_and_missing_days(self):
        result=self.load();r=result.rows[0]
        self.assertEqual(result.scrap_codes,['0000','1234','5678'])
        self.assertEqual((r.in_qty,r.fail_qty,r.out_qty),(1000,6,994))
        self.assertEqual(r.scrap_qty,{'1234':4,'5678':2})
        self.assertEqual(r.scrap_ppm_by_code,{'1234':4000,'5678':2000})
        self.assertEqual(r.fail_ppm,6000)
        self.assertIsNone(result.rows[1].yield_percent)
        self.assertEqual([r.date for r in result.rows],['20261001','20261002','20261003'])
        self.assertEqual(self.load(scrap_codes=[]),result)
        self.assertEqual(self.load(eqp=None).rows,[])
        self.assertEqual(self.load(models=['OTHER']).scrap_codes,[])
        self.assertEqual(parse_scrap_occurrences(' -, ,0:8,1234:5,1234:3'),{'0000':1,'1234':2})
    def test_handler_isolation_empty_cells_and_zero_yield(self):
        from ui.widgets.daily_summary_widget import DailySummaryWidget
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT INTO data(File_Date,EQP,Qty,Fail,Handler,Model,SCRAP) VALUES('20261001','A',200,1,'H2','M','7777:5')")
        result = MachineYieldRepository(self.path).load(dict(self.criteria, handler='H2',scrap_codes=['7777']), threading.Event(), include_daily=True)
        machine, handler = result[2:4]
        self.assertEqual(machine.rows[0].in_qty,1200)
        self.assertEqual(handler.rows[0].in_qty,200)
        self.assertEqual(handler.rows[0].scrap_qty,{'7777':1})
        self.assertEqual(handler.rows[0].scrap_ppm_by_code,{'7777':5000})
        self.assertEqual(handler.handler,'H2')
        widget=DailySummaryWidget(by_handler=True)
        widget.load_result(handler,['7777']);widget.show();self.app.processEvents();widget.chart.draw()
        self.assertEqual(widget.title.text(),'Yield ARTs by Handler | EQP: A | Handler: H2')
        self.assertEqual(widget.model.index(2,4).data(),'')
        self.assertEqual(widget.model.index(2,5).data(),'')
        self.assertEqual(list(widget.chart._yield_line.get_ydata()),[99.5,0,0])
        self.assertEqual(widget.table.width(),sum(widget.table.columnWidth(i) for i in range(widget.model.columnCount()))+2*widget.table.frameWidth())
        bar=widget.chart.hover.bars[0][0];x,y=bar.get_transform().transform((.5,.5))
        self.assertIn('H2',widget.chart.hover.hit_text(SimpleNamespace(x=x,y=y)))
        widget.grab().save(str(Path(__file__).parents[2]/'handler_preview.png'))
        widget.load_result(result[2],['7777'])
        no_handler=MachineYieldRepository(self.path).load(self.criteria,threading.Event(),include_daily=True)[3]
        widget.load_result(no_handler,['7777'])
        self.assertEqual(widget.model.rowCount(),1);self.assertFalse(widget.chart.figure.legends)
        widget.close()

    def test_selected_headers_and_tooltips_legends(self):
        from PyQt5.QtCore import QItemSelectionModel
        from PyQt5.QtWidgets import QApplication
        from ui.widgets.daily_summary_widget import DailySummaryWidget
        w=DailySummaryWidget();w.load_result(self.load(),self.criteria['scrap_codes']);w.show()
        self.app.processEvents();w.chart.draw()
        labels=[t.get_text() for t in w.chart.figure.legends[0].get_texts()]
        self.assertEqual(labels,['1234','Yield'])
        bar=w.chart.hover.bars[0][0];x,y=bar.get_transform().transform((.5,.5))
        tooltip=w.chart.hover.hit_text(SimpleNamespace(x=x,y=y))
        self.assertIn('1234',tooltip);self.assertIn('4,000',tooltip)
        select=w.table.selectionModel()
        for r,c in [(0,0),(0,7),(1,0),(1,7)]:select.select(w.model.index(r,c),QItemSelectionModel.Select)
        w.table.copy_selection()
        self.assertEqual(QApplication.clipboard().text(),'Date\t1234\n20261001\t4000')
        select.clearSelection();select.select(w.model.index(1,7),QItemSelectionModel.Select)
        w.table.copy_selection();self.assertEqual(QApplication.clipboard().text(),'4000')
        select.clearSelection();select.select(w.model.index(0,7),QItemSelectionModel.Select)
        w.table.copy_selection();self.assertEqual(QApplication.clipboard().text(),'1234')
        w.grab().save(str(Path(__file__).parents[2]/'daily_preview.png'))
        w.load_result(self.load(),['9999']);self.assertFalse(w.chart.figure.legends);self.assertFalse(w.chart.hover.bars)
        w.load_result(self.load(),[]);self.assertFalse(w.chart.figure.legends)
        w.clear_result('Chọn EQP');self.assertEqual(w.model.rowCount(),1)
        w.close()

if __name__=='__main__':unittest.main()
