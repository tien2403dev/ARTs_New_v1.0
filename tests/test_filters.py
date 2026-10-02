import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile,threading,unittest
from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from services.import_service import ImportService
from repositories.filter_option_repository import FilterOptionRepository
from ui.widgets.filter_panel import FilterPanel
from tests.test_import import line

class FilterTests(unittest.TestCase):
    def test_options_refresh_and_scrap(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);db=root/'test.db';file=root/'2026-10-01.txt'
            file.write_text(line().replace('SCRAP=A1','SCRAP=1234:2,0:1,AB:3'))
            service=ImportService(db);service.import_folder(root,'2026-10-01','2026-10-01')
            repo=FilterOptionRepository(db);r=repo.load_options(threading.Event())
            self.assertEqual(r['options']['SCRAP'],['0000','1234','AB'])
            self.assertEqual(r['options']['EQP'],['FT-H001'])
            self.assertEqual(r['options']['Handler'],['A'])
            self.assertEqual(r['options']['SLOT'],[3])
            self.assertIsNone(repo.load_options(threading.Event(),r['revision'])['options'])
            file.write_text(line(eqp='FT-H002B'))
            service.import_folder(root,'2026-10-01','2026-10-01')
            r2=repo.load_options(threading.Event(),r['revision'])
            self.assertEqual(r2['options']['EQP'],['FT-H002'])

    def test_missing_db_not_created(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'missing.db'
            self.assertFalse(FilterOptionRepository(path).load_options(threading.Event())['options']['EQP'])
            self.assertFalse(path.exists())

    def test_selection_and_layout(self):
        app=QApplication.instance() or QApplication([])
        panel=FilterPanel();panel.load_options({'EQP':['FT-H001'],'Handler':['A','B'],'ZONE':['A','B'],'SLOT':[1,2,3],'Model':['P7ABC','P7DEF'],'SCRAP':['0000','1234']})
        panel.set_ready(True)
        self.assertEqual(panel.model_list.selected_values(),['P7ABC','P7DEF'])
        self.assertEqual(panel.scrap_code_list.selected_values(),[])
        panel.combos['EQP'].setCurrentIndex(1)
        panel.scrap_code_list.item(0).setCheckState(Qt.Checked)
        self.assertEqual(panel.get_filter_criteria()['scrap_codes'],['0000','1234'])
        panel.show();app.processEvents()
        panel.grab().save(str(Path(__file__).parents[2]/'filters_preview.png'))
        panel.close()
