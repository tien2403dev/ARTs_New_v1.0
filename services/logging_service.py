"""Local diagnostic logging, initialized inside the import worker."""
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path


def configure_logging():
    folder = Path(os.environ.get('LOCALAPPDATA') or Path.home()/'.local'/'state')/'ARTs_Import_v1'/'logs'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/'import.log'
    root = logging.getLogger()
    if not any(getattr(handler, '_arts_handler', False) for handler in root.handlers):
        handler = RotatingFileHandler(path, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        handler._arts_handler = True
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s'))
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    return path
