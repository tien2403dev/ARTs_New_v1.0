"""Field extraction and pandas transformations preserved from ARTs SLOT_END parser."""
import logging
import os
import pandas as pd
from domain.models import COLUMNS, check_cancel
logger = logging.getLogger(__name__)

def open_log_file(file_path):
    encodings = ['utf-8', 'cp949', 'euc-kr', 'windows-1252', 'iso-8859-1']
    last_error = None
    for encoding in encodings:
        try:
            f = open(file_path, 'r', encoding=encoding, errors='ignore')
            f.readline()
            f.seek(0)
            return f
        except Exception as e:
            last_error = e
            try:
                f.close()
            except:
                pass
    raise last_error

def iter_records(file_path, cancel=None):
    file_date = os.path.basename(file_path)[:10].replace("-", "")
    with open_log_file(file_path) as f:
        for line_no, line in enumerate(f, 1):
            check_cancel(cancel)
            if 'FUNCTION=SLOT_END' not in line:
                continue
            try:
                parts = line.split()
                eqpid = parts[6].split('=')[1].strip()
                lotid = parts[3].split('=')[1].strip()
                zone = parts[10].split('=')[1].strip()
                slot = parts[7].split('=')[1].strip()
                bin_value = parts[8].split('=')[1].strip()
                scrap = parts[11].split('=')[1].strip()
                bcode = parts[2].split('=')[1].strip()
                date = parts[0][4:-1]
                qty = sum((c.isdigit() for c in bin_value))
                fail = sum((c in '23456789' for c in bin_value))
                fullsite = parts[5].split('=', 1)[1].strip()
                yield {'LOTID': lotid, 'File_Date': file_date, 'Date': f'[{date}]', 'EQPID': eqpid, 'ZONE': zone, 'SLOT': slot, 'FULLSITE': fullsite, 'BIN': bin_value, 'BCODE': bcode, 'SCRAP': scrap, 'QTY': qty, 'Fail': fail}
            except Exception:
                logger.warning("PARSE_SKIP file=%s line=%s", file_path, line_no)
                continue

def transform_rows(rows):
    df = pd.DataFrame(rows)
    df['Time'] = df['Date'].astype(str).str.extract('(\\d{2}:\\d{2}:\\d{2})', expand=False)
    df['Datetime'] = pd.to_datetime(df['File_Date'] + ' ' + df['Time'], format='%Y%m%d %H:%M:%S', errors='coerce')
    df['Datetime'] = df['Datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df['Handler'] = df['EQPID'].astype(str).str[-1]
    df['EQP'] = df['EQPID'].astype(str).str[:-1]
    df['Model'] = df['BCODE'].astype(str).str.slice(12, 17)
    df = df.rename(columns={"QTY": "Qty"})
    return df.loc[:, COLUMNS].astype(object).where(pd.notna(df.loc[:, COLUMNS]), None).itertuples(index=False, name=None)
