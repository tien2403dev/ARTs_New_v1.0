from dataclasses import dataclass

COLUMNS = ('LOTID', 'File_Date', 'Datetime', 'EQP', 'Handler', 'ZONE', 'SLOT',
           'Model', 'Qty', 'Fail', 'SCRAP', 'FULLSITE', 'BIN', 'BCODE')

class ImportCancelled(Exception):
    pass

class ImportBusyError(Exception):
    pass

class LockLostError(Exception):
    pass

def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise ImportCancelled('Đã hủy import; dữ liệu chưa commit được giữ nguyên.')

@dataclass(frozen=True)
class ImportResult:
    dates: tuple
    files: int
    inserted: int
    deleted: int
    missing_dates: tuple
    empty_dates: tuple
    batch_id: str
