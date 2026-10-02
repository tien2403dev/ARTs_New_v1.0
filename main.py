"""Only the Qt window shell is loaded at startup; import services load on demand."""
import sys


def configure_logging():
    # Kept for import_cli.py compatibility; no file I/O until called by a task.
    from services.logging_service import configure_logging as configure
    return configure()


def main():
    from PyQt5.QtWidgets import QApplication
    from ui.main_window import MainWindow
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == '__main__':
    sys.exit(main())
