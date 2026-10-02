import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PyQt5.QtWidgets import QApplication, QDialog, QPushButton, QLineEdit, QPlainTextEdit
from ui.main_window import MainWindow
from ui.import_dialog import DateRangeDialog
from tests.test_import import line


class UiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_startup_loads_only_shell(self):
        code = '''
import sys
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow
app=QApplication([])
w=MainWindow();w.show();app.processEvents()
for name in ['pandas','sqlite3','services.import_service','services.logging_service',
             'workers.import_worker','controllers.import_controller','ui.import_dialog']:
    assert name not in sys.modules, name
w.close()
'''
        subprocess.run([sys.executable, '-c', code], check=True, cwd=Path(__file__).parents[1], env=os.environ.copy())

    def test_window_and_import_flow(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            logs = root/'machine'/'month'; logs.mkdir(parents=True)
            (logs/'2026-10-01.txt').write_text(line())
            window = MainWindow(); window.show(); self.app.processEvents()
            self.assertEqual(len(window.findChildren(QPushButton)), 2)
            # Date editors contain QLineEdit internally; no database path editor.
            self.assertFalse(window.findChildren(QPlainTextEdit))
            with patch.dict(os.environ, {'ARTS_DB_PATH': str(root/'arts.db')}), \
                 patch.object(DateRangeDialog, 'exec_', return_value=QDialog.Accepted), \
                 patch.object(DateRangeDialog, 'date_range', return_value=('2026-10-01','2026-10-01')), \
                 patch('controllers.import_controller.QFileDialog.getExistingDirectory', return_value=str(root)), \
                 patch('controllers.import_controller.QMessageBox.information') as success, \
                 patch('controllers.import_controller.QMessageBox.warning') as warning:
                window.request_import()
                self.assertFalse(window.import_panel.button.isEnabled())
                deadline = time.monotonic()+20
                while window.controller.is_running and time.monotonic()<deadline:
                    self.app.processEvents(); time.sleep(.005)
                self.assertFalse(window.controller.is_running)
                self.assertTrue(window.import_panel.button.isEnabled())
                success.assert_called_once()
                self.assertEqual(success.call_args.args[1], 'Success')
                self.assertIn('Import thành công', success.call_args.args[2])
                warning.assert_not_called()
            window.grab().save(str(Path(__file__).parents[2]/'ui_v11_main.png'))
            dialog = DateRangeDialog(window); dialog.show(); self.app.processEvents()
            self.assertEqual(dialog.date_from.displayFormat(), 'dd/MM/yyyy')
            dialog.grab().save(str(Path(__file__).parents[2]/'ui_v11_dialog.png'))
            dialog.close(); window.close()
            for _ in range(100):
                self.app.processEvents(); time.sleep(.005)

    def test_cancel_dialog_does_not_start_worker(self):
        window = MainWindow()
        with patch.object(DateRangeDialog, 'exec_', return_value=QDialog.Rejected), \
             patch('controllers.import_controller.QFileDialog.getExistingDirectory') as folder:
            window.request_import()
            folder.assert_not_called()
            self.assertFalse(window.controller.is_running)
        window.close()

    def test_database_path_preserves_previous_setting(self):
        from app_config import get_database_path
        from unittest.mock import Mock
        settings = Mock()
        settings.value.return_value = 'Z:/ARTs_New/arts_data.db'
        with patch.dict(os.environ, {}, clear=True), patch('app_config.DATABASE_PATH',''):
            self.assertEqual(get_database_path(settings), 'Z:/ARTs_New/arts_data.db')


if __name__ == '__main__':
    unittest.main()
