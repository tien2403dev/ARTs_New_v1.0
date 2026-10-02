import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sqlite3,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from database.schema import DATA_SQL
from repositories.machine_yield_repository import MachineYieldRepository

class ZoneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'test.db'
        with sqlite3.connect(self.path) as c:
            c.execute(DATA_SQL)
            c.executemany('INSERT INTO data(File_Date,EQP,Handler,ZONE,SLOT,Model,Qty,Fail,SCRAP) VALUES(?,?,?,?,?,?,?,?,?)',[
                ('20261001','EQP1','A','A',1,'M1',100,6,'1234:8'),
                ('20261002','EQP1','A','A',1,'M1',200,2,''),
                ('20261002','EQP1','A','F',1,'M1',50,3,'5678:2'),
                ('20261002','EQP1','B','A',1,'M1',1000,50,'1234:8'),
                ('20261002','OTHER','A','A',1,'M1',1000,50,'1234:8'),
                ('20260930','EQP1','A','A',1,'M1',1000,50,'1234:8')])
        self.criteria=dict(date_from='20261001',date_to='20261002',eqp='EQP1',handler='A',zone='A',slot=None,models=[],scrap_codes=['1234'])
    def tearDown(self):self.temp.cleanup()
    def load(self,**changes):return MachineYieldRepository(self.path).load(dict(self.criteria,**changes),threading.Event(),include_daily=True)
    def test_zone_quantities_fixed_rows_and_filters(self):
        result=self.load();zones=result[4]
        self.assertEqual([r.zone for r in zones.rows],list('ABCDEF'))
        self.assertEqual((zones.rows[0].in_qty,zones.rows[0].pass_qty,zones.rows[0].fail_qty),(300,292,8))
        self.assertAlmostEqual(zones.rows[0].yield_percent,292/300*100)
        self.assertEqual(zones.rows[-1].fail_qty,3)
        self.assertEqual(result[3].rows[1].in_qty,200) # Daily still respects Zone A.
        self.assertEqual(self.load(scrap_codes=['NONEXISTENT'])[4],zones)
        self.assertEqual(self.load(zone='F')[4],zones)
        self.assertEqual(self.load(handler=None)[4].rows,[])
        self.assertEqual(self.load(eqp=None)[4].rows,[])
        self.assertEqual(self.load(models=['OTHER'])[4].rows[0].in_qty,0)
    def test_ui_quantity_bars_alignment_copy_tooltip(self):
        from PyQt5.QtCore import QItemSelectionModel
        from PyQt5.QtWidgets import QApplication
        from ui.widgets.zone_summary_widget import ZoneSummaryWidget
        w=ZoneSummaryWidget();w.load_result(self.load()[4]);w.show();self.app.processEvents();w.chart.draw()
        self.assertEqual(w.model.rowCount(),7)
        self.assertEqual([b.get_height() for b,t in w.chart.hover.bars],[8,0,0,0,0,3])
        self.assertEqual(w.table.mapToGlobal(w.table.rect().topLeft()).y(),w.chart.mapToGlobal(w.chart.rect().topLeft()).y())
        selection=w.table.selectionModel()
        for r,c in [(0,3),(1,3)]:selection.select(w.model.index(r,c),QItemSelectionModel.Select)
        w.table.copy_selection();self.assertEqual(QApplication.clipboard().text(),'Fail\n8')
        bar=w.chart.hover.bars[0][0];x,y=bar.get_transform().transform((.5,.5))
        tooltip=w.chart.hover.hit_text(SimpleNamespace(x=x,y=y))
        self.assertIn('Fail Qty',tooltip);self.assertIn('Handler',tooltip);self.assertNotIn('PPM',tooltip)
        w.grab().save(str(Path(__file__).parents[2]/'zone_preview.png'))
        w.clear_result('Chọn Handler');self.assertFalse(w.chart.hover.bars);self.assertEqual(w.model.rowCount(),1)
        w.close()

if __name__=='__main__':unittest.main()
