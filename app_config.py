"""Resolve configuration without probing the network or opening SQLite."""
import os
from pathlib import Path
import sys

# Optional fixed shared path, e.g. r'\\server\share\ARTs_New\database\arts_data.db'.
# Empty preserves the database selected in v1.0 on this machine.
DATABASE_PATH = ''


def get_database_path(settings):
    root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
    target = root / 'database' / 'arts_data.db'
    explicit = os.environ.get('ARTS_DB_PATH') or DATABASE_PATH
    if explicit:
        return os.path.expandvars(os.path.expanduser(explicit.strip().strip('"')))
    saved = settings.value('database', '', type=str)
    if saved:
        saved = os.path.expandvars(os.path.expanduser(saved.strip().strip('"')))
        # Redirect the previous default setting after moving the file manually.
        # Keep custom/shared database locations selected by the user.
        if os.path.normcase(os.path.abspath(saved)) != os.path.normcase(str(root / 'arts_data.db')):
            return saved
    return str(target)
