###DOC TRUC TIEP FILE LOG TU FOLDER
import os
import pandas as pd


def get_txt_files_from_folders(folders):

    txt_files = []

    for folder in folders:

        for file_name in os.listdir(folder):

            if file_name.lower().endswith(".txt"):

                txt_files.append(
                    os.path.join(
                        folder,
                        file_name
                    )
                )

    return txt_files
def read_log_file(file_path):

    encodings = [
        "utf-8",
        "cp949",
        "iso-8859-1",
        "windows-1252"
    ]

    for encoding in encodings:

        try:

            with open(
                    file_path,
                    "r",
                    encoding=encoding
            ) as f:

                return f.readlines()

        except Exception:

            continue

    raise Exception(
        f"Cannot read file:\n{file_path}"
    )


def load_log_date(
        root_folder,
        selected_date,
        progress_callback=None
):


    txt_files = get_txt_files_by_date(
        root_folder,
        selected_date
    )

    rows = []

    total_files = len(txt_files)

    for index, file_path in enumerate(txt_files):

        file_date = (
            os.path.basename(file_path)
            [:10]
            .replace("-", "")
        )

        with open_log_file(file_path) as f:

            for line in f:

                if "FUNCTION=SLOT_END" not in line:
                    continue

                try:

                    parts = line.split()

                    eqpid = (
                        parts[6]
                        .split("=")[1]
                        .strip()
                    )

                    lotid = (
                        parts[3]
                        .split("=")[1]
                        .strip()
                    )

                    zone = (
                        parts[10]
                        .split("=")[1]
                        .strip()
                    )

                    slot = (
                        parts[7]
                        .split("=")[1]
                        .strip()
                    )

                    bin_value = (
                        parts[8]
                        .split("=")[1]
                        .strip()
                    )

                    scrap = (
                        parts[11]
                        .split("=")[1]
                        .strip()
                    )

                    bcode = (
                        parts[2]
                        .split("=")[1]
                        .strip()
                    )

                    date = parts[0][4:-1]

                    qty = sum(
                        c.isdigit()
                        for c in bin_value
                    )

                    fail = sum(
                        c in "23456789"
                        for c in bin_value
                    )
                    fullsite = (
                        parts[5]
                        .split("=", 1)[1]
                        .strip()
                    )

                    # rows.append(
                    #     {
                    #         "LOTID": lotid,
                    #         "File_Date": file_date,
                    #         "Date": f"[{date}]",
                    #         "EQPID": eqpid,
                    #         "ZONE": zone,
                    #         "SLOT": slot,
                    #         "BCODE": bcode,
                    #         "BIN": bin_value,
                    #         "SCRAP": scrap,
                    #         "QTY": qty,
                    #         "Fail": fail
                    #     }
                    # )
                    rows.append(
                        {
                            "LOTID": lotid,
                            "File_Date": file_date,
                            "Date": f"[{date}]",
                            "EQPID": eqpid,
                            "ZONE": zone,
                            "SLOT": slot,
                            "FULLSITE": fullsite,
                            "BIN": bin_value,
                            "BCODE": bcode,
                            "SCRAP": scrap,
                            "QTY": qty,
                            "Fail": fail
                        }
                    )

                except Exception:

                    continue

    df = pd.DataFrame(rows)

    # Datetime

    df["Time"] = (
        df["Date"]
        .astype(str)
        .str.extract(
            r"(\d{2}:\d{2}:\d{2})",
            expand=False
        )
    )

    df["Datetime"] = pd.to_datetime(
        df["File_Date"]
        + " "
        + df["Time"],
        format="%Y%m%d %H:%M:%S",
        errors="coerce"
    )

    df["Datetime"] = (
        df["Datetime"]
        .dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    # Handler

    df["Handler"] = (
        df["EQPID"]
        .astype(str)
        .str[-1]
    )

    # EQP

    df["EQP"] = (
        df["EQPID"]
        .astype(str)
        .str[:-1]
    )

    # Model

    df["Model"] = (
        df["BCODE"]
        .astype(str)
        .str.slice(
            12,
            17
        )
    )

    print(
        "TOTAL ROWS:",
        len(df),
        "TOTAL FILE",total_files
    )

    return df

def open_log_file(file_path):
    encodings = [
        "utf-8",
        "cp949",
        "euc-kr",
        "windows-1252",
        "iso-8859-1"
    ]

    last_error = None

    for encoding in encodings:

        try:

            f = open(
                file_path,
                "r",
                encoding=encoding,
                errors="ignore"  # hoặc "replace"
            )
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


def get_txt_files_by_date(
        root_folder,
        selected_date
):

    txt_files = []

    for root, dirs, files in os.walk(
            root_folder
    ):

        for file_name in files:

            if not file_name.lower().endswith(
                    ".txt"
            ):
                continue

            if not file_name.startswith(
                    selected_date
            ):
                continue

            txt_files.append(
                os.path.join(
                    root,
                    file_name
                )
            )

    return txt_files