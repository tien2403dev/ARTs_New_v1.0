# ARTs Import v1.0 — 02/10/2026

## 1. Phạm vi thực hiện

Đây là project mới, chạy độc lập, triển khai giai đoạn **Import** của ARTs mới theo kiến trúc của LI. Giải nén và chạy project này; không chép đè vào project ARTs cũ.

Đã có: giao diện chọn SQLite, nút Import, chọn From–To, chọn folder cha, quét TXT đệ quy, parser ARTs, staging local, thay dữ liệu theo ngày, khóa import dùng chung, tiến độ, hủy, log chi tiết và CLI dùng cùng service.

Chưa triển khai các giai đoạn sau: Summary, Analyze, Machine Slot Yield, Alarm/Monitor, mail, scheduler tự động. Bản này không tự tính các bảng phụ thuộc của ARTs cũ. Chọn **database riêng cho app mới** trên ổ mạng, ví dụ `Z:\ARTs_New\arts_data.db` hoặc `\\server\share\ARTs_New\arts_data.db`. Các máy chạy bản mới chọn cùng một đường dẫn database. Không sử dụng database sản xuất của app cũ; app từ chối database có các bảng phụ thuộc cũ để không làm sai số liệu của app đó.

## 2. Cài và chạy trên Windows/PyCharm

Mở terminal tại folder chứa `main.py`:

```bat
python -m pip install -r requirements.txt
python main.py
```

Các thư viện pandas chỉ được nạp khi worker import bắt đầu. Mở giao diện không kết nối hay tạo database.

1. Bấm **Chọn database…** và chọn tên file database của app mới trong folder ổ mạng đã tồn tại. Có thể chọn file đã tạo bởi bản này để import tiếp.
2. Bấm **Import — From / To…**.
3. Chọn From và To, định dạng `yyyy-MM-dd`, tính cả hai ngày biên.
4. Bấm **Tiếp tục chọn folder**, chọn folder cha chứa các folder máy.
5. Theo dõi trạng thái, số file/dòng và kết quả commit.

Đường dẫn database và folder log được nhớ trên từng máy bằng QSettings. Có thể đặt biến môi trường `ARTS_DB_PATH` để cung cấp đường dẫn database khi mở app. Không tự tạo folder mạng nếu đường dẫn sai hoặc không truy cập được.

## 3. Tìm file

Quét `os.walk` đúng một lần cho cả khoảng ngày, không quét lại toàn bộ folder cho từng ngày. Duyệt tới mọi tầng thư mục dưới root, hỗ trợ cả:

- `Root\Machine1\2026-10-01.txt`
- `Root\Machine2\2026-10\2026-10-01_log.txt`
- `Root\Machine3\2026-10\Subfolder\2026-10-02.TXT`

Giữ quy tắc ARTs: phần đầu tên file là `YYYY-MM-DD`, phần mở rộng TXT không phân biệt hoa/thường. `20261001.txt` không đúng cách đặt tên của parser import ARTs này. Ngày import lấy từ tên file, không dùng ngày sửa file hay tên folder tháng.

Nếu duyệt folder hoặc đọc một file đã chọn bị lỗi quyền/mất kết nối, dừng import trước bước thay dữ liệu. Không tự bỏ qua folder không truy cập được. Không đi theo symlink thư mục. Người dùng cần chọn root chứa đầy đủ máy của các ngày định import vì thay thế theo **toàn bộ ngày**, không theo riêng máy.

## 4. Giữ nguyên bảng data và parser

Cấu trúc `data` giữ đúng thứ tự và kiểu khai báo trong ARTs gốc:

| Cột | Kiểu |
|---|---|
| ID | INTEGER PRIMARY KEY AUTOINCREMENT |
| LOTID | TEXT |
| File_Date | TEXT |
| Datetime | TEXT |
| EQP | TEXT |
| Handler | TEXT |
| ZONE | TEXT |
| SLOT | INTEGER |
| Model | TEXT |
| Qty | INTEGER |
| Fail | INTEGER |
| SCRAP | TEXT |
| FULLSITE | TEXT |
| BIN | TEXT |
| BCODE | TEXT |

Giữ cách xử lý `services/import_service.py` của ARTs gốc:

- Chỉ lấy dòng chứa `FUNCTION=SLOT_END`.
- Giữ nguyên vị trí tách LOTID, EQPID, SLOT, BIN, ZONE, SCRAP, BCODE, FULLSITE.
- `File_Date`: 10 ký tự đầu tên file bỏ dấu `-`, thành `yyyyMMdd`.
- `Datetime`: File_Date ghép giờ lấy từ dòng; giá trị không chuyển được vẫn thành NULL như parser cũ.
- `Handler`: ký tự cuối EQPID; `EQP`: phần còn lại.
- `Model`: BCODE tại lát cắt `[12:17]`.
- `Qty`: số ký tự thỏa `isdigit()` trong BIN, bao gồm chữ số 0.
- `Fail`: số ký tự thuộc `23456789` trong BIN.
- Giữ chính sách mở file/encoding với `errors='ignore'` của ARTs gốc.
- Dòng SLOT_END sai cấu trúc vẫn bị bỏ qua như bản cũ, nhưng thêm log `PARSE_SKIP` kèm file và số dòng. Vì vậy số dòng import là số dòng parser chấp nhận, không nhất thiết bằng số dòng SLOT_END trong file. Không thay đổi nghiệp vụ này trong bản import.
- Không tự loại bản ghi trùng giữa nhiều file vì bản cũ không có bước đó.

Parser gốc được giữ tại `reference/arts_import_original.py` để đối chiếu, không dùng trực tiếp lúc chạy app. Parser mới giữ biểu thức tách trường và chuyển đổi của bản gốc, chuyển sang xử lý từng lô để hạn chế RAM.

## 5. Luồng xử lý và import lại như LI PRIME

1. Kiểm tra From–To và tìm file phù hợp.
2. Khởi tạo/kiểm tra database ở worker. Dùng SQLite rollback journal DELETE, `synchronous=FULL`, không WAL trên ổ mạng.
3. Nhận khóa import dùng chung, lưu chủ sở hữu theo máy/user/process/batch.
4. Heartbeat gia hạn lease 15 phút mỗi 30 giây bằng connection riêng.
5. Đọc từng file vào snapshot tạm local, sau đó parse và ghi staging local theo lô 5.000 dòng. Không giữ toàn bộ dữ liệu các file trong RAM.
6. Dừng heartbeat, kiểm tra hủy và quyền sở hữu khóa trước khi ghi chính.
7. `BEGIN IMMEDIATE`; kiểm tra lại khóa; lấy các ngày có dòng hợp lệ trong staging.
8. Xóa **toàn bộ dòng data của các ngày đó**, không giới hạn máy, Handler, Zone hay Slot.
9. Chèn dữ liệu staging theo lô 5.000 dòng trong **cùng transaction**, cập nhật trạng thái import và revision.
10. Giải phóng khóa import trong transaction và COMMIT. Kết quả thành công chỉ phát sau khi commit trả về thành công.

Ví dụ From 01/10 đến To 03/10: nếu 01/10 và 03/10 có dữ liệu hợp lệ còn 02/10 không có file, chỉ thay 01/10 và 03/10; giữ nguyên dữ liệu 02/10 và thông báo ngày thiếu.

Ngày có file nhưng không có dòng hợp lệ: giữ nguyên dữ liệu ngày đó. Nếu toàn bộ staging rỗng: báo lỗi, không xóa dữ liệu. Nếu một ngày có cả file rỗng và file có dòng hợp lệ, ngày đó vẫn được thay bằng tổng dòng hợp lệ đọc được, đúng chính sách bỏ qua dòng lỗi của parser gốc.

Nếu lỗi hoặc hủy trước commit: rollback toàn bộ DELETE/INSERT của cả lần import, giữ nguyên dữ liệu đã commit trước đó. Không commit từng lô lên database chính. ID được sinh mới sau import lại; không giữ ID cũ. Các ngày ngoài tập ngày thay thế không bị xóa.

File được chụp tối đa số byte tại lúc mở để không đọc vô hạn khi máy nối thêm log. File thay đổi sau khi snapshot đọc xong không làm hủy import; lần này dùng nội dung đã chụp, lần import sau lấy bản mới. Đây không phải snapshot nguyên tử của hệ thống file: nếu file bị sửa nội dung tại chỗ ngay trong lúc sao chép thì không bảo đảm ảnh chụp nhất quán. Nếu file bị thu ngắn khiến không đọc đủ số byte đã xác định thì dừng trước khi thay dữ liệu.

## 6. Nhiều máy dùng chung SQLite

Mỗi tác vụ mở connection riêng và đóng trong `finally`; không chia sẻ connection giữa các thread. Khóa `arts_import_lock` ngăn hai phiên **app mới/CLI mới** import đồng thời. Importer ARTs cũ không biết khóa này, vì vậy không trộn các phiên cũ/mới ghi cùng database.

Khi đang scan/parse/staging, không giữ transaction ghi database chính. Khi DELETE/INSERT/COMMIT, SQLite vẫn có thể chờ reader hoặc writer khác; timeout chính là 60 giây mỗi thao tác khóa, không phải giới hạn tổng thời gian import. Nếu hết thời gian chờ thì báo lỗi và rollback phần chưa commit; không tự lặp lại việc ghi vô hạn.

Heartbeat dùng timeout 2 giây và log lỗi; kiểm tra quyền khóa lần cuối bắt buộc trước DELETE. Khi tiến trình bị tắt bất thường, lease hết hạn sau tối đa khoảng 15 phút từ lần gia hạn cuối. Khóa SQLite của transaction và lease import là hai cơ chế riêng. Máy dùng chung cần đồng bộ đồng hồ.

Nút **Hủy import** là yêu cầu hủy có kiểm soát, được kiểm tra khi đọc file, parse dòng và giữa các lô ghi. Không cưỡng bức dừng QThread hay connection. Trong lúc SQLite đang chờ khóa/commit, hủy có thể phải chờ thao tác đó trả về. Nếu commit đã thành công thì vẫn báo thành công, không giả vờ hủy dữ liệu đã commit. Đóng cửa sổ khi import đang chạy sẽ yêu cầu hủy và giữ cửa sổ tới khi worker kết thúc; đóng lại sau đó.

Không cam kết hết lock hoặc tốc độ cụ thể trên SMB/NAS. Mất kết nối trong thời điểm commit cần xem log và kiểm tra database khi kết nối phục hồi; không suy ra kết quả commit chỉ từ lỗi kết nối.

## 7. Các bảng hỗ trợ và index

Không thêm cột vào `data`. Tạo thêm:

- `arts_import_lock`: lease import dùng chung.
- `arts_import_status`: ngày, batch, thời điểm UTC, số dòng của lần import gần nhất.
- `arts_data_revision`: tăng revision trong cùng transaction với dữ liệu, làm nền cho các tab tương lai phát hiện dữ liệu mới.
- `idx_arts_data_file_date`: index trên File_Date phục vụ thay dữ liệu theo ngày.

Không tự VACUUM hoặc ANALYZE toàn bộ database sau mỗi import. Xóa rồi import lại không đảm bảo kích thước file DB giảm ngay; các trang được tái sử dụng.

## 8. Cấu trúc code

| File/Folder | Nhiệm vụ |
|---|---|
| main.py | Khởi động UI, log local |
| ui/main_window.py | Chọn database, nút Import, tiến độ, hủy |
| ui/import_dialog.py | Dialog From–To |
| workers/import_worker.py | Worker và signal về UI |
| services/file_discovery.py | Quét folder đệ quy theo tên file |
| services/log_parser.py | Quy tắc lấy dữ liệu ARTs |
| services/staging_service.py | Snapshot file và staging local |
| services/import_service.py | Điều phối luồng import |
| database/connection.py | Connection theo tác vụ, timeout, rollback/close |
| database/schema.py | Giữ schema data; bảng hỗ trợ |
| repositories/import_lock_repository.py | Lease và heartbeat |
| repositories/data_repository.py | DELETE/INSERT/COMMIT nguyên tử |
| domain/models.py | Cột, kết quả, loại lỗi |
| import_cli.py | Chạy cùng service từ dòng lệnh |
| tests/ | Kiểm thử và benchmark giả lập |
| reference/ | Parser gốc để đối chiếu |

## 9. Log và chạy CLI

Windows: `%LOCALAPPDATA%\ARTs_Import_v1\logs\import.log`; xoay vòng 10 MiB/file, giữ 5 bản cũ. Ghi đường dẫn file, batch, chủ khóa, số dòng, thời gian đọc từng file, thời gian connection/transaction, commit/rollback và traceback. Không ghi nội dung test/serial từng dòng.

```bat
python import_cli.py --database "Z:\ARTs_New\arts_data.db" --folder "Z:\LogRoot" --from 2026-10-01 --to 2026-10-02
```

## 10. Kiểm thử và build

```bat
python -m unittest discover -s tests -v
python -m tests.benchmark_import --rows 1000000
python -m pip install pyinstaller
build_windows.bat
```

Bản build tạo tại `dist\ARTs_Import\ARTs_Import.exe`. Sao chép toàn bộ folder `dist\ARTs_Import`, không chỉ riêng EXE. Cài dependencies và build bằng Python trên chính Windows đích; bản bàn giao là source, không phải EXE đã build/kiểm chứng trên Windows.

Xem `TEST_REPORT.md` cho kết quả thực chạy. Chưa có log sản xuất và ổ mạng của người dùng trong môi trường kiểm thử. Trước khi dùng thực tế, thử trên database mới ở ổ mạng với log của một vài ngày, kiểm tra số dòng/Qty/Fail theo từng ngày/máy và thử nhiều máy mở đồng thời.



ARTs Import v1.0 — 02/10/2026
1. Phạm vi thực hiện
Đây là project mới, chạy độc lập, triển khai giai đoạn Import của ARTs mới theo kiến trúc của LI. Giải nén và chạy project này; không chép đè vào project ARTs cũ.
Đã có: cấu hình SQLite, nút Import, chọn From–To, chọn folder cha, quét TXT đệ quy, parser ARTs, staging local, thay dữ liệu theo ngày, khóa import dùng chung, trạng thái nút, hủy khi đóng cửa sổ, log chi tiết và CLI dùng cùng service.
Chưa triển khai các giai đoạn sau: Summary, Analyze, Machine Slot Yield, Alarm/Monitor, mail, scheduler tự động. Bản này không tự tính các bảng phụ thuộc của ARTs cũ. Chọn database riêng cho app mới trên ổ mạng, ví dụ `Z:\ARTs_New\arts_data.db` hoặc `\\server\share\ARTs_New\arts_data.db`. Các máy chạy bản mới chọn cùng một đường dẫn database. Không sử dụng database sản xuất của app cũ; app từ chối database có các bảng phụ thuộc cũ để không làm sai số liệu của app đó.
2. Cài và chạy — giao diện v1.1
Chép đè các file trong bản patch vào thư mục project v1.0 (cùng cấp `main.py`), giữ nguyên các file còn lại. Không xóa project cũ. Bản patch không chứa database và không di chuyển dữ liệu.
```bat
python -m pip install -r requirements.txt
python main.py
```
Cửa sổ chính chỉ còn nút IMPORT màu xanh. Bấm nút để mở dialog Chọn khoảng ngày import với Từ ngày / Đến ngày, định dạng `dd/MM/yyyy`. Bấm Tiếp tục, chọn folder cha chứa các máy. Trong khi import, nút bị vô hiệu hóa và hiện “Đang import…”. Sau khi worker kết thúc và commit thành công, hiện dialog Success; nếu lỗi hiện dialog lỗi. Không còn tiêu đề lớn, chọn database, khung log, thanh tiến độ hoặc nút hủy trên cửa sổ chính.
Database được xác định theo thứ tự:
Biến môi trường `ARTS_DB_PATH`.
`DATABASE_PATH` trong `app_config.py` nếu điền đường dẫn cố định.
Đường dẫn đã chọn ở v1.0, lưu trong QSettings của đúng user/máy.
Nếu chưa có cấu hình: `arts_data.db` cạnh `main.py` khi chạy source, hoặc cạnh EXE khi đã build.
Ví dụ cấu hình cố định cho các máy dùng chung ổ mạng trong `app_config.py`:
```python
DATABASE_PATH = r"\\server\share\ARTs_New\arts_data.db"
```
Không điền đường dẫn mẫu này nếu đó không phải ổ mạng của bạn. Bản patch mặc định để trống nhằm giữ lại database đã chọn ở phiên trước. Máy khác/user khác không tự có QSettings này; đặt cùng `ARTS_DB_PATH` hoặc `DATABASE_PATH` để dùng chung database. Nếu chạy EXE, thay cấu hình source rồi build lại, hoặc dùng biến môi trường.
Không kiểm tra folder mạng, không kết nối SQLite, không nạp pandas hay tạo log khi mở app. Khởi động chỉ nạp Qt và các widget cần thiết để vẽ cửa sổ. Controller/dialog nạp khi bấm Import; worker nạp sau khi chọn folder; pandas/SQLite/parser/logging được nạp và chạy trong worker. Các thư viện Qt tối thiểu vẫn phải nạp trước khi hiện cửa sổ. Không chủ động preload thư viện nặng ngay sau show vì bản này chưa cần chúng cho đến khi import.
Tổ chức mới: `main_window.py` chỉ là khung cửa sổ; `ui/widgets/import_panel.py` chứa nút/style; `ui/import_dialog.py` chứa dialog ngày; `controllers/import_controller.py` điều phối UI và kết quả; `services/logging_service.py` quản lý log; `app_config.py` xác định đường dẫn database. Parser, staging, transaction và khóa import không thay đổi trong v1.1.
3. Tìm file
Quét `os.walk` đúng một lần cho cả khoảng ngày, không quét lại toàn bộ folder cho từng ngày. Duyệt tới mọi tầng thư mục dưới root, hỗ trợ cả:
`Root\Machine1\2026-10-01.txt`
`Root\Machine2\2026-10\2026-10-01_log.txt`
`Root\Machine3\2026-10\Subfolder\2026-10-02.TXT`
Giữ quy tắc ARTs: phần đầu tên file là `YYYY-MM-DD`, phần mở rộng TXT không phân biệt hoa/thường. `20261001.txt` không đúng cách đặt tên của parser import ARTs này. Ngày import lấy từ tên file, không dùng ngày sửa file hay tên folder tháng.
Nếu duyệt folder hoặc đọc một file đã chọn bị lỗi quyền/mất kết nối, dừng import trước bước thay dữ liệu. Không tự bỏ qua folder không truy cập được. Không đi theo symlink thư mục. Người dùng cần chọn root chứa đầy đủ máy của các ngày định import vì thay thế theo toàn bộ ngày, không theo riêng máy.
4. Giữ nguyên bảng data và parser
Cấu trúc `data` giữ đúng thứ tự và kiểu khai báo trong ARTs gốc:
Cột	Kiểu
ID	INTEGER PRIMARY KEY AUTOINCREMENT
LOTID	TEXT
File_Date	TEXT
Datetime	TEXT
EQP	TEXT
Handler	TEXT
ZONE	TEXT
SLOT	INTEGER
Model	TEXT
Qty	INTEGER
Fail	INTEGER
SCRAP	TEXT
FULLSITE	TEXT
BIN	TEXT
BCODE	TEXT
Giữ cách xử lý `services/import_service.py` của ARTs gốc:
Chỉ lấy dòng chứa `FUNCTION=SLOT_END`.
Giữ nguyên vị trí tách LOTID, EQPID, SLOT, BIN, ZONE, SCRAP, BCODE, FULLSITE.
`File_Date`: 10 ký tự đầu tên file bỏ dấu `-`, thành `yyyyMMdd`.
`Datetime`: File_Date ghép giờ lấy từ dòng; giá trị không chuyển được vẫn thành NULL như parser cũ.
`Handler`: ký tự cuối EQPID; `EQP`: phần còn lại.
`Model`: BCODE tại lát cắt `[12:17]`.
`Qty`: số ký tự thỏa `isdigit()` trong BIN, bao gồm chữ số 0.
`Fail`: số ký tự thuộc `23456789` trong BIN.
Giữ chính sách mở file/encoding với `errors='ignore'` của ARTs gốc.
Dòng SLOT_END sai cấu trúc vẫn bị bỏ qua như bản cũ, nhưng thêm log `PARSE_SKIP` kèm file và số dòng. Vì vậy số dòng import là số dòng parser chấp nhận, không nhất thiết bằng số dòng SLOT_END trong file. Không thay đổi nghiệp vụ này trong bản import.
Không tự loại bản ghi trùng giữa nhiều file vì bản cũ không có bước đó.
Parser gốc được giữ tại `reference/arts_import_original.py` để đối chiếu, không dùng trực tiếp lúc chạy app. Parser mới giữ biểu thức tách trường và chuyển đổi của bản gốc, chuyển sang xử lý từng lô để hạn chế RAM.
5. Luồng xử lý và import lại như LI PRIME
Kiểm tra From–To và tìm file phù hợp.
Khởi tạo/kiểm tra database ở worker. Dùng SQLite rollback journal DELETE, `synchronous=FULL`, không WAL trên ổ mạng.
Nhận khóa import dùng chung, lưu chủ sở hữu theo máy/user/process/batch.
Heartbeat gia hạn lease 15 phút mỗi 30 giây bằng connection riêng.
Đọc từng file vào snapshot tạm local, sau đó parse và ghi staging local theo lô 5.000 dòng. Không giữ toàn bộ dữ liệu các file trong RAM.
Dừng heartbeat, kiểm tra hủy và quyền sở hữu khóa trước khi ghi chính.
`BEGIN IMMEDIATE`; kiểm tra lại khóa; lấy các ngày có dòng hợp lệ trong staging.
Xóa toàn bộ dòng data của các ngày đó, không giới hạn máy, Handler, Zone hay Slot.
Chèn dữ liệu staging theo lô 5.000 dòng trong cùng transaction, cập nhật trạng thái import và revision.
Giải phóng khóa import trong transaction và COMMIT. Kết quả thành công chỉ phát sau khi commit trả về thành công.
Ví dụ From 01/10 đến To 03/10: nếu 01/10 và 03/10 có dữ liệu hợp lệ còn 02/10 không có file, chỉ thay 01/10 và 03/10; giữ nguyên dữ liệu 02/10 và thông báo ngày thiếu.
Ngày có file nhưng không có dòng hợp lệ: giữ nguyên dữ liệu ngày đó. Nếu toàn bộ staging rỗng: báo lỗi, không xóa dữ liệu. Nếu một ngày có cả file rỗng và file có dòng hợp lệ, ngày đó vẫn được thay bằng tổng dòng hợp lệ đọc được, đúng chính sách bỏ qua dòng lỗi của parser gốc.
Nếu lỗi hoặc hủy trước commit: rollback toàn bộ DELETE/INSERT của cả lần import, giữ nguyên dữ liệu đã commit trước đó. Không commit từng lô lên database chính. ID được sinh mới sau import lại; không giữ ID cũ. Các ngày ngoài tập ngày thay thế không bị xóa.
File được chụp tối đa số byte tại lúc mở để không đọc vô hạn khi máy nối thêm log. File thay đổi sau khi snapshot đọc xong không làm hủy import; lần này dùng nội dung đã chụp, lần import sau lấy bản mới. Đây không phải snapshot nguyên tử của hệ thống file: nếu file bị sửa nội dung tại chỗ ngay trong lúc sao chép thì không bảo đảm ảnh chụp nhất quán. Nếu file bị thu ngắn khiến không đọc đủ số byte đã xác định thì dừng trước khi thay dữ liệu.
6. Nhiều máy dùng chung SQLite
Mỗi tác vụ mở connection riêng và đóng trong `finally`; không chia sẻ connection giữa các thread. Khóa `arts_import_lock` ngăn hai phiên app mới/CLI mới import đồng thời. Importer ARTs cũ không biết khóa này, vì vậy không trộn các phiên cũ/mới ghi cùng database.
Khi đang scan/parse/staging, không giữ transaction ghi database chính. Khi DELETE/INSERT/COMMIT, SQLite vẫn có thể chờ reader hoặc writer khác; timeout chính là 60 giây mỗi thao tác khóa, không phải giới hạn tổng thời gian import. Nếu hết thời gian chờ thì báo lỗi và rollback phần chưa commit; không tự lặp lại việc ghi vô hạn.
Heartbeat dùng timeout 2 giây và log lỗi; kiểm tra quyền khóa lần cuối bắt buộc trước DELETE. Khi tiến trình bị tắt bất thường, lease hết hạn sau tối đa khoảng 15 phút từ lần gia hạn cuối. Khóa SQLite của transaction và lease import là hai cơ chế riêng. Máy dùng chung cần đồng bộ đồng hồ.
Thao tác đóng cửa sổ khi import đang chạy gửi yêu cầu hủy có kiểm soát, được kiểm tra khi đọc file, parse dòng và giữa các lô ghi. Không cưỡng bức dừng QThread hay connection. Trong lúc SQLite đang chờ khóa/commit, hủy có thể phải chờ thao tác đó trả về. Nếu commit đã thành công thì vẫn báo thành công, không giả vờ hủy dữ liệu đã commit. Đóng cửa sổ khi import đang chạy sẽ yêu cầu hủy và giữ cửa sổ tới khi worker kết thúc; đóng lại sau đó.
Không cam kết hết lock hoặc tốc độ cụ thể trên SMB/NAS. Mất kết nối trong thời điểm commit cần xem log và kiểm tra database khi kết nối phục hồi; không suy ra kết quả commit chỉ từ lỗi kết nối.
7. Các bảng hỗ trợ và index
Không thêm cột vào `data`. Tạo thêm:
`arts_import_lock`: lease import dùng chung.
`arts_import_status`: ngày, batch, thời điểm UTC, số dòng của lần import gần nhất.
`arts_data_revision`: tăng revision trong cùng transaction với dữ liệu, làm nền cho các tab tương lai phát hiện dữ liệu mới.
`idx_arts_data_file_date`: index trên File_Date phục vụ thay dữ liệu theo ngày.
Không tự VACUUM hoặc ANALYZE toàn bộ database sau mỗi import. Xóa rồi import lại không đảm bảo kích thước file DB giảm ngay; các trang được tái sử dụng.
8. Cấu trúc code
File/Folder	Nhiệm vụ
main.py	Khởi động khung UI; hàm log tương thích CLI được nạp khi cần
ui/main_window.py	Khung cửa sổ và xử lý yêu cầu đóng
ui/widgets/import_panel.py	Nút Import và style
controllers/import_controller.py	Điều phối dialog, worker và thông báo kết quả
app_config.py	Xác định đường dẫn database
services/logging_service.py	Khởi tạo log local khi bắt đầu tác vụ
ui/import_dialog.py	Dialog From–To
workers/import_worker.py	Worker và signal về UI
services/file_discovery.py	Quét folder đệ quy theo tên file
services/log_parser.py	Quy tắc lấy dữ liệu ARTs
services/staging_service.py	Snapshot file và staging local
services/import_service.py	Điều phối luồng import
database/connection.py	Connection theo tác vụ, timeout, rollback/close
database/schema.py	Giữ schema data; bảng hỗ trợ
repositories/import_lock_repository.py	Lease và heartbeat
repositories/data_repository.py	DELETE/INSERT/COMMIT nguyên tử
domain/models.py	Cột, kết quả, loại lỗi
import_cli.py	Chạy cùng service từ dòng lệnh
tests/	Kiểm thử và benchmark giả lập
reference/	Parser gốc để đối chiếu
9. Log và chạy CLI
Windows: `%LOCALAPPDATA%\ARTs_Import_v1\logs\import.log`; xoay vòng 10 MiB/file, giữ 5 bản cũ. Ghi đường dẫn file, batch, chủ khóa, số dòng, thời gian đọc từng file, thời gian connection/transaction, commit/rollback và traceback. Không ghi nội dung test/serial từng dòng.
```bat
python import_cli.py --database "Z:\ARTs_New\arts_data.db" --folder "Z:\LogRoot" --from 2026-10-01 --to 2026-10-02
```
10. Kiểm thử và build
```bat
python -m unittest discover -s tests -v
python -m tests.benchmark_import --rows 1000000
python -m pip install pyinstaller
build_windows.bat
```
Bản build tạo tại `dist\ARTs_Import\ARTs_Import.exe`. Sao chép toàn bộ folder `dist\ARTs_Import`, không chỉ riêng EXE. Cài dependencies và build bằng Python trên chính Windows đích; bản bàn giao là source, không phải EXE đã build/kiểm chứng trên Windows.
Xem `TEST_REPORT.md` cho kết quả thực chạy. Chưa có log sản xuất và ổ mạng của người dùng trong môi trường kiểm thử. Trước khi dùng thực tế, thử trên database mới ở ổ mạng với log của một vài ngày, kiểm tra số dòng/Qty/Fail theo từng ngày/máy và thử nhiều máy mở đồng thời.

Cập nhật v1.2 — Bộ lọc ARTs theo giao diện LI
Chép đè các file trong patch vào project đã áp dụng v1.1, cùng cấp main.py. Giữ các file không có trong patch. Không xóa database.
Bố cục và thao tác
Hàng trên: From, To, EQP.
Hàng dưới: Handler, Zone, Slot.
Hai cột cuối: Model, Scrap Code, cao bằng hai hàng bộ lọc; không có Tier.
Dưới bộ lọc: IMPORT bên trái, SEARCH bên phải. Nền xanh nhạt, khung trắng và nút xanh theo LI.
From mặc định hôm nay trừ 14 ngày, To hôm nay; yyyy-MM-dd như LI. Đổi ngày để From không vượt To.
EQP/Handler/Zone/Slot là dropdown chọn một giá trị; “Chọn…” tương ứng None/không giới hạn trường đó.
Model có checkbox/Select All và mặc định chọn tất cả; Scrap Code mặc định chưa chọn, giống LI.
SEARCH lưu current_criteria, phát signal MainWindow.filter_applied và hiển thị điều kiện đã chọn. Bản này chưa có bảng Summary/Alarm/Report nên SEARCH chưa truy vấn hay hiển thị báo cáo. Danh sách Model rỗng là không chọn model; danh sách Scrap rỗng là chưa chọn mã. Tab sử dụng điều kiện cần giữ rõ quy ước này.
Nguồn lựa chọn là toàn bộ dữ liệu đã import, không quét lại theo From/To mỗi lần chỉnh ngày; giống bộ lọc chính LI. Chưa áp dụng lọc phụ thuộc EQP → Handler/Zone/Slot.
Tối ưu và nguồn dữ liệu
Window hiện trước; sau show 100 ms mới tạo worker tải danh mục. SQLite/repository nạp trong worker, pandas chỉ nạp lúc import.
EQP, Handler, ZONE, SLOT, Model lấy từ các cột cùng tên bảng data. Scrap Code tách từ SCRAP: phân cách dấu phẩy, lấy phần trước dấu hai chấm, bỏ khoảng trắng; 0 thành 0000 theo ARTs. Không hạn chế mã phải là 4 chữ số của LI, không tô đỏ mã ưu tiên LI cho ARTs.
Giống FilterOptionRepository LI: dùng recursive MIN/index seeks để lấy từng giá trị khác nhau; không tải các dòng test vào UI. Tạo các index idx_arts_filter_EQP/Handler/ZONE/SLOT/Model/SCRAP. Bộ lọc mới được sắp theo thứ tự giá trị SQL, SLOT INTEGER theo số.
Database mới tạo index trong bước khởi tạo import. Database v1.0/v1.1 đã có dữ liệu sẽ tạo index còn thiếu một lần trong worker nền lúc tải bộ lọc; lần đầu có thể lâu và cần quyền ghi. Tạo index có thể chờ khóa, và các index cũng làm tăng công việc khi import. Không xem thời gian benchmark v1.0 là tốc độ đã đo của v1.2.
Mỗi lần tải lấy một transaction snapshot và đóng connection sau khi đọc. Danh sách tái sử dụng trong UI, không tải lại khi đổi ngày/nhấn dropdown.
Import thành công ở máy hiện tại: tải lại lựa chọn ngay. Mỗi 60 giây worker kiểm tra arts_data_revision để phát hiện import từ máy khác; revision không đổi thì không truy vấn lại danh mục. Cơ chế dựa trên importer mới cập nhật revision.
Giữ EQP/Handler/Zone/Slot đã chọn nếu còn tồn tại; giá trị bị xóa trở về “Chọn…”. Giữ checkbox còn hợp lệ; khi trước đó chọn tất cả, lựa chọn mới thêm tiếp tục được chọn.
Chưa có database: trả danh sách rỗng, không tự tạo file trong luồng tải bộ lọc.
Database bận: worker timeout 2 giây và thử lại mỗi 5 giây; SEARCH/danh mục tạm vô hiệu hóa, hiện thông báo “Database đang cập nhật, vui lòng thử lại sau 2 phút”. Thông báo có thể đóng; khi đọc được sẽ tự đóng và mở lại bộ lọc. Hai phút là nội dung thông báo, không phải thời gian chờ bắt buộc.
Lỗi khác: hiển thị lỗi trong dòng trạng thái, thử lại ở chu kỳ sau. Đóng app hủy worker và đợi kết thúc, không terminate QThread.
File chính mới/thay đổi
ui/widgets/filter_panel.py, ui/widgets/check_list.py, controllers/filter_controller.py,
workers/filter_option_worker.py, repositories/filter_option_repository.py,
ui/main_window.py, controllers/import_controller.py, database/schema.py.
Giữ nguyên parser, quy tắc thay dữ liệu ngày, dialog import và Success của v1.1.
ui/widgets/import_panel.py cũ có thể giữ nguyên, hiện không còn được MainWindow sử dụng.
Kiểm chứng
24 tests PASS, gồm các tests import hiện có và kiểm tra danh mục, tách Scrap, revision cache,
import lại loại giá trị cũ, database chưa tồn tại, checkbox, điều kiện lọc và giao diện.
Đã kiểm tra ảnh render bằng Qt offscreen. Chưa đo trên Windows/ổ mạng thật hoặc 1 triệu dòng với các index mới.
---
ARTs Import v1.0 — 02/10/2026
1. Phạm vi thực hiện
Đây là project mới, chạy độc lập, triển khai giai đoạn Import của ARTs mới theo kiến trúc của LI. Giải nén và chạy project này; không chép đè vào project ARTs cũ.
Đã có: cấu hình SQLite, nút Import, chọn From–To, chọn folder cha, quét TXT đệ quy, parser ARTs, staging local, thay dữ liệu theo ngày, khóa import dùng chung, trạng thái nút, hủy khi đóng cửa sổ, log chi tiết và CLI dùng cùng service.
Chưa triển khai các giai đoạn sau: Summary, Analyze, Machine Slot Yield, Alarm/Monitor, mail, scheduler tự động. Bản này không tự tính các bảng phụ thuộc của ARTs cũ. Chọn database riêng cho app mới trên ổ mạng, ví dụ `Z:\ARTs_New\arts_data.db` hoặc `\\server\share\ARTs_New\arts_data.db`. Các máy chạy bản mới chọn cùng một đường dẫn database. Không sử dụng database sản xuất của app cũ; app từ chối database có các bảng phụ thuộc cũ để không làm sai số liệu của app đó.
2. Cài và chạy — giao diện v1.1
Chép đè các file trong bản patch vào thư mục project v1.0 (cùng cấp `main.py`), giữ nguyên các file còn lại. Không xóa project cũ. Bản patch không chứa database và không di chuyển dữ liệu.
```bat
python -m pip install -r requirements.txt
python main.py
```
Cửa sổ chính có bộ lọc chung, nút IMPORT và SEARCH. Bấm nút để mở dialog Chọn khoảng ngày import với Từ ngày / Đến ngày, định dạng `dd/MM/yyyy`. Bấm Tiếp tục, chọn folder cha chứa các máy. Trong khi import, nút bị vô hiệu hóa và hiện “Đang import…”. Sau khi worker kết thúc và commit thành công, hiện dialog Success; nếu lỗi hiện dialog lỗi. Không còn tiêu đề lớn, chọn database, khung log, thanh tiến độ hoặc nút hủy trên cửa sổ chính.
Database được xác định theo thứ tự:
Biến môi trường `ARTS_DB_PATH`.
`DATABASE_PATH` trong `app_config.py` nếu điền đường dẫn cố định.
Đường dẫn đã chọn ở v1.0, lưu trong QSettings của đúng user/máy.
Nếu chưa có cấu hình: `arts_data.db` cạnh `main.py` khi chạy source, hoặc cạnh EXE khi đã build.
Ví dụ cấu hình cố định cho các máy dùng chung ổ mạng trong `app_config.py`:
```python
DATABASE_PATH = r"\\server\share\ARTs_New\arts_data.db"
```
Không điền đường dẫn mẫu này nếu đó không phải ổ mạng của bạn. Bản patch mặc định để trống nhằm giữ lại database đã chọn ở phiên trước. Máy khác/user khác không tự có QSettings này; đặt cùng `ARTS_DB_PATH` hoặc `DATABASE_PATH` để dùng chung database. Nếu chạy EXE, thay cấu hình source rồi build lại, hoặc dùng biến môi trường.
Khởi động chỉ nạp Qt và widget để vẽ cửa sổ. Sau show, QTimer 100 ms khởi động controller/worker bộ lọc; SQLite và repository nạp trong worker. Không có truy vấn DB trên UI thread. Pandas/parser vẫn chỉ nạp khi import. Qt tối thiểu phải nạp trước show.
Tổ chức mới: `main_window.py` chỉ là khung cửa sổ; `ui/widgets/import_panel.py` chứa nút/style; `ui/import_dialog.py` chứa dialog ngày; `controllers/import_controller.py` điều phối UI và kết quả; `services/logging_service.py` quản lý log; `app_config.py` xác định đường dẫn database. Parser, staging, transaction và khóa import không thay đổi trong v1.1.
3. Tìm file
Quét `os.walk` đúng một lần cho cả khoảng ngày, không quét lại toàn bộ folder cho từng ngày. Duyệt tới mọi tầng thư mục dưới root, hỗ trợ cả:
`Root\Machine1\2026-10-01.txt`
`Root\Machine2\2026-10\2026-10-01_log.txt`
`Root\Machine3\2026-10\Subfolder\2026-10-02.TXT`
Giữ quy tắc ARTs: phần đầu tên file là `YYYY-MM-DD`, phần mở rộng TXT không phân biệt hoa/thường. `20261001.txt` không đúng cách đặt tên của parser import ARTs này. Ngày import lấy từ tên file, không dùng ngày sửa file hay tên folder tháng.
Nếu duyệt folder hoặc đọc một file đã chọn bị lỗi quyền/mất kết nối, dừng import trước bước thay dữ liệu. Không tự bỏ qua folder không truy cập được. Không đi theo symlink thư mục. Người dùng cần chọn root chứa đầy đủ máy của các ngày định import vì thay thế theo toàn bộ ngày, không theo riêng máy.
4. Giữ nguyên bảng data và parser
Cấu trúc `data` giữ đúng thứ tự và kiểu khai báo trong ARTs gốc:
Cột	Kiểu
ID	INTEGER PRIMARY KEY AUTOINCREMENT
LOTID	TEXT
File_Date	TEXT
Datetime	TEXT
EQP	TEXT
Handler	TEXT
ZONE	TEXT
SLOT	INTEGER
Model	TEXT
Qty	INTEGER
Fail	INTEGER
SCRAP	TEXT
FULLSITE	TEXT
BIN	TEXT
BCODE	TEXT
Giữ cách xử lý `services/import_service.py` của ARTs gốc:
Chỉ lấy dòng chứa `FUNCTION=SLOT_END`.
Giữ nguyên vị trí tách LOTID, EQPID, SLOT, BIN, ZONE, SCRAP, BCODE, FULLSITE.
`File_Date`: 10 ký tự đầu tên file bỏ dấu `-`, thành `yyyyMMdd`.
`Datetime`: File_Date ghép giờ lấy từ dòng; giá trị không chuyển được vẫn thành NULL như parser cũ.
`Handler`: ký tự cuối EQPID; `EQP`: phần còn lại.
`Model`: BCODE tại lát cắt `[12:17]`.
`Qty`: số ký tự thỏa `isdigit()` trong BIN, bao gồm chữ số 0.
`Fail`: số ký tự thuộc `23456789` trong BIN.
Giữ chính sách mở file/encoding với `errors='ignore'` của ARTs gốc.
Dòng SLOT_END sai cấu trúc vẫn bị bỏ qua như bản cũ, nhưng thêm log `PARSE_SKIP` kèm file và số dòng. Vì vậy số dòng import là số dòng parser chấp nhận, không nhất thiết bằng số dòng SLOT_END trong file. Không thay đổi nghiệp vụ này trong bản import.
Không tự loại bản ghi trùng giữa nhiều file vì bản cũ không có bước đó.
Parser gốc được giữ tại `reference/arts_import_original.py` để đối chiếu, không dùng trực tiếp lúc chạy app. Parser mới giữ biểu thức tách trường và chuyển đổi của bản gốc, chuyển sang xử lý từng lô để hạn chế RAM.
5. Luồng xử lý và import lại như LI PRIME
Kiểm tra From–To và tìm file phù hợp.
Khởi tạo/kiểm tra database ở worker. Dùng SQLite rollback journal DELETE, `synchronous=FULL`, không WAL trên ổ mạng.
Nhận khóa import dùng chung, lưu chủ sở hữu theo máy/user/process/batch.
Heartbeat gia hạn lease 15 phút mỗi 30 giây bằng connection riêng.
Đọc từng file vào snapshot tạm local, sau đó parse và ghi staging local theo lô 5.000 dòng. Không giữ toàn bộ dữ liệu các file trong RAM.
Dừng heartbeat, kiểm tra hủy và quyền sở hữu khóa trước khi ghi chính.
`BEGIN IMMEDIATE`; kiểm tra lại khóa; lấy các ngày có dòng hợp lệ trong staging.
Xóa toàn bộ dòng data của các ngày đó, không giới hạn máy, Handler, Zone hay Slot.
Chèn dữ liệu staging theo lô 5.000 dòng trong cùng transaction, cập nhật trạng thái import và revision.
Giải phóng khóa import trong transaction và COMMIT. Kết quả thành công chỉ phát sau khi commit trả về thành công.
Ví dụ From 01/10 đến To 03/10: nếu 01/10 và 03/10 có dữ liệu hợp lệ còn 02/10 không có file, chỉ thay 01/10 và 03/10; giữ nguyên dữ liệu 02/10 và thông báo ngày thiếu.
Ngày có file nhưng không có dòng hợp lệ: giữ nguyên dữ liệu ngày đó. Nếu toàn bộ staging rỗng: báo lỗi, không xóa dữ liệu. Nếu một ngày có cả file rỗng và file có dòng hợp lệ, ngày đó vẫn được thay bằng tổng dòng hợp lệ đọc được, đúng chính sách bỏ qua dòng lỗi của parser gốc.
Nếu lỗi hoặc hủy trước commit: rollback toàn bộ DELETE/INSERT của cả lần import, giữ nguyên dữ liệu đã commit trước đó. Không commit từng lô lên database chính. ID được sinh mới sau import lại; không giữ ID cũ. Các ngày ngoài tập ngày thay thế không bị xóa.
File được chụp tối đa số byte tại lúc mở để không đọc vô hạn khi máy nối thêm log. File thay đổi sau khi snapshot đọc xong không làm hủy import; lần này dùng nội dung đã chụp, lần import sau lấy bản mới. Đây không phải snapshot nguyên tử của hệ thống file: nếu file bị sửa nội dung tại chỗ ngay trong lúc sao chép thì không bảo đảm ảnh chụp nhất quán. Nếu file bị thu ngắn khiến không đọc đủ số byte đã xác định thì dừng trước khi thay dữ liệu.
6. Nhiều máy dùng chung SQLite
Mỗi tác vụ mở connection riêng và đóng trong `finally`; không chia sẻ connection giữa các thread. Khóa `arts_import_lock` ngăn hai phiên app mới/CLI mới import đồng thời. Importer ARTs cũ không biết khóa này, vì vậy không trộn các phiên cũ/mới ghi cùng database.
Khi đang scan/parse/staging, không giữ transaction ghi database chính. Khi DELETE/INSERT/COMMIT, SQLite vẫn có thể chờ reader hoặc writer khác; timeout chính là 60 giây mỗi thao tác khóa, không phải giới hạn tổng thời gian import. Nếu hết thời gian chờ thì báo lỗi và rollback phần chưa commit; không tự lặp lại việc ghi vô hạn.
Heartbeat dùng timeout 2 giây và log lỗi; kiểm tra quyền khóa lần cuối bắt buộc trước DELETE. Khi tiến trình bị tắt bất thường, lease hết hạn sau tối đa khoảng 15 phút từ lần gia hạn cuối. Khóa SQLite của transaction và lease import là hai cơ chế riêng. Máy dùng chung cần đồng bộ đồng hồ.
Thao tác đóng cửa sổ khi import đang chạy gửi yêu cầu hủy có kiểm soát, được kiểm tra khi đọc file, parse dòng và giữa các lô ghi. Không cưỡng bức dừng QThread hay connection. Trong lúc SQLite đang chờ khóa/commit, hủy có thể phải chờ thao tác đó trả về. Nếu commit đã thành công thì vẫn báo thành công, không giả vờ hủy dữ liệu đã commit. Đóng cửa sổ khi import đang chạy sẽ yêu cầu hủy và giữ cửa sổ tới khi worker kết thúc; đóng lại sau đó.
Không cam kết hết lock hoặc tốc độ cụ thể trên SMB/NAS. Mất kết nối trong thời điểm commit cần xem log và kiểm tra database khi kết nối phục hồi; không suy ra kết quả commit chỉ từ lỗi kết nối.
7. Các bảng hỗ trợ và index
Không thêm cột vào `data`. Tạo thêm:
`arts_import_lock`: lease import dùng chung.
`arts_import_status`: ngày, batch, thời điểm UTC, số dòng của lần import gần nhất.
`arts_data_revision`: tăng revision trong cùng transaction với dữ liệu, làm nền cho các tab tương lai phát hiện dữ liệu mới.
`idx_arts_data_file_date`: index trên File_Date phục vụ thay dữ liệu theo ngày.
Không tự VACUUM hoặc ANALYZE toàn bộ database sau mỗi import. Xóa rồi import lại không đảm bảo kích thước file DB giảm ngay; các trang được tái sử dụng.
8. Cấu trúc code
File/Folder	Nhiệm vụ
main.py	Khởi động khung UI; hàm log tương thích CLI được nạp khi cần
ui/main_window.py	Khung cửa sổ và xử lý yêu cầu đóng
ui/widgets/import_panel.py	Nút Import và style
controllers/import_controller.py	Điều phối dialog, worker và thông báo kết quả
app_config.py	Xác định đường dẫn database
services/logging_service.py	Khởi tạo log local khi bắt đầu tác vụ
ui/import_dialog.py	Dialog From–To
workers/import_worker.py	Worker và signal về UI
services/file_discovery.py	Quét folder đệ quy theo tên file
services/log_parser.py	Quy tắc lấy dữ liệu ARTs
services/staging_service.py	Snapshot file và staging local
services/import_service.py	Điều phối luồng import
database/connection.py	Connection theo tác vụ, timeout, rollback/close
database/schema.py	Giữ schema data; bảng hỗ trợ
repositories/import_lock_repository.py	Lease và heartbeat
repositories/data_repository.py	DELETE/INSERT/COMMIT nguyên tử
domain/models.py	Cột, kết quả, loại lỗi
import_cli.py	Chạy cùng service từ dòng lệnh
tests/	Kiểm thử và benchmark giả lập
reference/	Parser gốc để đối chiếu
9. Log và chạy CLI
Windows: `%LOCALAPPDATA%\ARTs_Import_v1\logs\import.log`; xoay vòng 10 MiB/file, giữ 5 bản cũ. Ghi đường dẫn file, batch, chủ khóa, số dòng, thời gian đọc từng file, thời gian connection/transaction, commit/rollback và traceback. Không ghi nội dung test/serial từng dòng.
```bat
python import_cli.py --database "Z:\ARTs_New\arts_data.db" --folder "Z:\LogRoot" --from 2026-10-01 --to 2026-10-02
```
10. Kiểm thử và build
```bat
python -m unittest discover -s tests -v
python -m tests.benchmark_import --rows 1000000
python -m pip install pyinstaller
build_windows.bat
```
Bản build tạo tại `dist\ARTs_Import\ARTs_Import.exe`. Sao chép toàn bộ folder `dist\ARTs_Import`, không chỉ riêng EXE. Cài dependencies và build bằng Python trên chính Windows đích; bản bàn giao là source, không phải EXE đã build/kiểm chứng trên Windows.
Xem `TEST_REPORT.md` cho kết quả thực chạy. Chưa có log sản xuất và ổ mạng của người dùng trong môi trường kiểm thử. Trước khi dùng thực tế, thử trên database mới ở ổ mạng với log của một vài ngày, kiểm tra số dòng/Qty/Fail theo từng ngày/máy và thử nhiều máy mở đồng thời.

Summary — Yield ARTs machine on summary
Bản vá dành cho ARTs_New(3).zip, ngày 02/10/2026.
Cài đặt
Đóng app, giải nén gói này rồi chép các file/thư mục vào thư mục project chứa main.py. Chọn ghi đè các file cùng tên; giữ nguyên cấu trúc controllers, database, repositories, workers, ui, tests.
Trong terminal của môi trường PyCharm đang chạy app, chạy: `python -m pip install -r requirements.txt`.
Chạy `python main.py`, chọn From/To và điều kiện lọc, bấm SEARCH ở tab Summary.
Gói chỉ có file mới/thay đổi và tài liệu; không kèm database, cấu hình đường dẫn hoặc dữ liệu sản xuất.
Sử dụng
Bảng trái: EQPID, In Qty, Out Qty, Fail Qty, Fail PPM, Yield và Total.
Biểu đồ phải: cột vàng Fail PPM, đường xanh Yield. Di chuột lên cột hoặc điểm để xem số liệu của máy. Total không vẽ lên biểu đồ.
Bôi ô bằng chuột, Shift hoặc Ctrl; Ctrl+C hoặc chuột phải → Copy phần đã chọn. Không copy tiêu đề. Ô không được chọn trong vùng rời rạc được để trống khi dán.
Trong lúc Search có hộp Please Wait với vòng xoay giống LI. Nhấn Esc để hủy. Nếu database bận, worker chờ và thử lại; giao diện không thực hiện truy vấn.
Sau import thành công, kết quả cũ được xóa; bấm SEARCH để đọc dữ liệu mới.
Công thức và phạm vi
Lọc File_Date từ From đến To, bao gồm cả hai ngày. Đây là ngày lưu trong database từ tên file ARTs, nhất quán với parser hiện tại.
Gom theo EQP; áp dụng Handler, Zone, Slot, Model và Scrap Code đang chọn. Không chọn điều kiện nghĩa là không giới hạn điều kiện đó.
In = SUM(Qty); Fail = SUM(Fail); Out = In − Fail.
Yield = Out / In × 100%; Fail PPM = Fail / In × 1.000.000.
Total tính từ tổng Qty/Fail của các máy, không lấy trung bình phần trăm từng máy.
In = 0: Yield/PPM hiển thị “—”, không vẽ điểm Yield giả bằng 0.
Scrap Code lọc đúng từng mã của bản ghi, không khớp một phần mã. Mã 0 được hiển thị/lọc bằng 0000. Khi chọn mã, thống kê toàn bộ Qty/Fail của bản ghi khớp mã; không tách Qty theo mã lỗi.
Tối ưu
SQL SUM/GROUP BY tại database, chỉ gửi một dòng mỗi máy về UI, không nạp toàn bộ log hoặc DataFrame.
Hai covering index: idx_arts_summary_date_cover (File_Date đầu tiên) và idx_arts_summary_eqp_date_cover (EQP, File_Date đầu tiên). Bao gồm các cột cần tổng hợp và lọc, tránh đọc lại từng hàng của bảng data.
Database cũ của app mới: tự tạo index thiếu trong worker ở lần SEARCH đầu. Database khởi tạo/import qua schema mới cũng có hai index này. Không cần xóa hoặc import lại database.
Lần tạo index đầu có thể lâu và cần quyền ghi database; tác vụ ghi khác có thể phải chờ. Index tăng dung lượng database và chi phí cập nhật khi import. Các lần SEARCH sau chỉ đọc khi index đã đủ.
QAbstractTableModel cập nhật một lần cho bảng; không tạo từng QTableWidgetItem. Matplotlib chỉ nạp khi Search; tái sử dụng canvas/hai trục, một draw_idle mỗi lần; tooltip không truy vấn database hay vẽ lại biểu đồ.
Search luôn truy vấn snapshot hiện tại, không dùng cache kết quả cũ.
Xác minh
`python -m unittest tests.test_summary tests.test_import tests.test_filters tests.test_ui -v`
29 kiểm tra đã chạy đạt trên môi trường kiểm thử: tổng theo máy/Total, biên ngày, Qty=0, bộ lọc, mã scrap trùng tiền tố, nâng cấp index lặp lại, EXPLAIN QUERY PLAN dùng covering range index, copy vùng rời rạc, tooltip hai trục, xóa biểu đồ rỗng, vòng đời worker và các kiểm tra import/bộ lọc/UI hiện có.
Đã xem ảnh render giao diện PyQt5 bằng chế độ offscreen. Chưa đo tốc độ trên database sản xuất hoặc ổ mạng Windows của bạn.


ARTs — cập nhật Yield Daily / Scrap PPM (02/10/2026)
Cài bản vá này
Áp dụng trên bản đã có ARTs_Summary_Layout_Update.zip. Đóng app, giải nén và chép đè các file trong gói vào thư mục chứa main.py, giữ nguyên cấu trúc thư mục. Chạy `python main.py`. Không cần import lại, đổi database hay cài thêm thư viện so với bản Summary trước.
Database mặc định vẫn là `database/arts_data.db`. Bản vá không kèm file database và không thay đổi dữ liệu import.
Bảng Yield ARTs Daily
Ở tab Summary, kéo xuống dưới khối Yield theo máy. Chọn From/To, một EQP và các Scrap Code, rồi bấm SEARCH.
Bảng gồm Date, In Qty, Pass, Fail Qty, Fail PPM, Yield và các cột mã lỗi tính theo PPM.
Bảng liệt kê tất cả mã có phát sinh trên bản ghi Fail của EQP trong khoảng ngày, giống chức năng CUM YIELD DAILY của LI. Scrap Code trên bộ lọc chỉ quyết định mã được vẽ trong biểu đồ Daily.
Tính theo File_Date; bao gồm cả ngày đầu và ngày cuối. Ngày không sản xuất vẫn có dòng: Qty = 0, Yield và Fail PPM = “—”; cột mã không phát sinh để trống.
Áp dụng thêm Handler, Zone, Slot và Model đang chọn. Chưa chọn EQP: hiện hướng dẫn chọn EQP, xóa Daily cũ.
Bảng dùng thanh cuộn khi có nhiều ngày/mã, để không tạo widget quá cao hoặc quá rộng.
Công thức ARTs
In = SUM(Qty); Fail Qty = SUM(Fail); Pass = In − Fail Qty.
Yield = Pass / In × 100%; Fail PPM = Fail Qty / In × 1.000.000.
Mỗi mục mã trong SCRAP của bản ghi `Fail > 0` tính một lần xuất hiện, theo ARTs cũ (`get_summary_data` / `parse_scrap_codes`). Lấy mã trước dấu `:`, tách mục bằng dấu phẩy; 0 hiển thị thành 0000; bỏ mục trống và dấu `-`.
Không coi phần sau dấu `:` là số lượng. Ví dụ `1234:9,1234:8,5678:2` tính 1234 hai lần, 5678 một lần. Các mục lặp được cộng, không loại trùng mã trong một bản ghi.
PPM của mã trong ngày = số lần xuất hiện mã / tổng In của ngày × 1.000.000. Ví dụ tổng In = 1.000, mã có 4 lần → 4.000 PPM.
Chọn Scrap Code không lọc bớt sản lượng của Daily, nên không làm sai mẫu số PPM. Tổng PPM mã có thể khác Fail PPM khi log thiếu mã hoặc một sản phẩm ghi nhiều mã; không tự phân bổ số Fail vào mã.
Phần thống kê theo máy phía trên giữ cách lọc đã có ở bản trước (có lọc bản ghi theo Scrap Code); do đó khi chọn mã, số tổng ở khối trên có thể khác tổng của Daily. Daily dùng mẫu số toàn bộ sản lượng theo EQP/ngày và các bộ lọc khác như LI.
Copy chính xác vùng bôi chọn
Hàng đầu của bảng Daily là hàng tiêu đề có thể bôi chọn như dữ liệu.
Chỉ chọn dữ liệu → Ctrl+C chỉ copy dữ liệu đó.
Chọn cả hàng đầu và dữ liệu → copy cả các ô tiêu đề được chọn.
Chọn riêng ô tiêu đề → copy được riêng tên cột.
Ctrl+A → chọn toàn bộ bảng; chuột phải → Copy phần đã bôi chọn.
Ô không được chọn trong vùng rời rạc được để trống khi dán; không tự thêm tiêu đề hoặc giá trị ngoài vùng chọn.
Biểu đồ bên dưới
Kế thừa kiểu CUM YIELD DAILY của LI: cột chồng PPM từng mã, đường Yield, lưới ô, khung, ngày và chú thích. Rộng 1.550 px, cao 550 px; có cuộn ngang trên màn hình nhỏ.
Chỉ vẽ mã được chọn và có PPM > 0 trong khoảng ngày. Mã chọn nhưng không có dữ liệu không tạo cột hay legend.
Không chọn mã hoặc toàn bộ mã chọn không phát sinh: thông báo trống, xóa legend/cột cũ.
Di chuột từng đoạn cột: xem EQP, ngày, Scrap Code, PPM mã, số lần mã lỗi, In/Out/Fail và Yield. Tooltip dùng số liệu đã tổng hợp, không truy vấn lại database.
Ngày In = 0 không được vẽ thành Yield 0%; đường ngắt ở ngày thiếu sản lượng để tránh hiểu sai.
Tổ chức và tốc độ
Daily chạy trong SummaryWorker hiện có, cùng hiệu ứng Search và hỗ trợ hủy/chờ database bận.
Machine và Daily đọc trong cùng một transaction/snapshot, không trộn dữ liệu trước/sau một lần import đồng thời.
Tái sử dụng covering index EQP/File_Date có sẵn. SQLite gom Qty/Fail và gom các chuỗi SCRAP trùng nhau theo ngày trước khi Python đếm mã; không đọc lại folder log hay tạo bảng fail_history.
Bảng dùng QAbstractTableModel; chỉ vẽ các đoạn cột có PPM dương. Tái sử dụng canvas; module biểu đồ nạp trong worker, widget được tạo ở UI thread.
Xóa cả Daily khi import cập nhật hoặc Search lỗi, tránh giữ kết quả cũ.
File mới/thay đổi
domain/daily_summary.py
repositories/daily_summary_repository.py
repositories/machine_yield_repository.py
workers/summary_worker.py
ui/pages/summary_page.py
ui/widgets/daily_summary_widget.py
ui/charts/daily_scrap_chart.py
tests/test_daily_summary.py
read.md, changelog.txt
Xác minh
Đã chạy đạt 11 kiểm tra Summary, Daily và UI: đếm mục mã lặp, bỏ mã trên bản ghi Pass, chuẩn hóa 0, mẫu số không phụ thuộc chọn mã, ngày không có dữ liệu, lọc EQP/Model, copy dữ liệu/tiêu đề riêng, tooltip và legend không có mã rỗng; kiểm tra vòng đời Search và UI cũ. Đã xem ảnh render bảng/biểu đồ PyQt5. Chưa kiểm chứng trên log sản xuất/ổ mạng Windows thực tế.
---
Tài liệu giai đoạn Import trước đây
ARTs Import v1.0 — 02/10/2026
1. Phạm vi thực hiện
Đây là project mới, chạy độc lập, triển khai giai đoạn Import của ARTs mới theo kiến trúc của LI. Giải nén và chạy project này; không chép đè vào project ARTs cũ.
Đã có: giao diện chọn SQLite, nút Import, chọn From–To, chọn folder cha, quét TXT đệ quy, parser ARTs, staging local, thay dữ liệu theo ngày, khóa import dùng chung, tiến độ, hủy, log chi tiết và CLI dùng cùng service.
Chưa triển khai các giai đoạn sau: Summary, Analyze, Machine Slot Yield, Alarm/Monitor, mail, scheduler tự động. Bản này không tự tính các bảng phụ thuộc của ARTs cũ. Chọn database riêng cho app mới trên ổ mạng, ví dụ `Z:\ARTs_New\arts_data.db` hoặc `\\server\share\ARTs_New\arts_data.db`. Các máy chạy bản mới chọn cùng một đường dẫn database. Không sử dụng database sản xuất của app cũ; app từ chối database có các bảng phụ thuộc cũ để không làm sai số liệu của app đó.
2. Cài và chạy trên Windows/PyCharm
Mở terminal tại folder chứa `main.py`:
```bat
python -m pip install -r requirements.txt
python main.py
```
Các thư viện pandas chỉ được nạp khi worker import bắt đầu. Mở giao diện không kết nối hay tạo database.
Bấm Chọn database… và chọn tên file database của app mới trong folder ổ mạng đã tồn tại. Có thể chọn file đã tạo bởi bản này để import tiếp.
Bấm Import — From / To….
Chọn From và To, định dạng `yyyy-MM-dd`, tính cả hai ngày biên.
Bấm Tiếp tục chọn folder, chọn folder cha chứa các folder máy.
Theo dõi trạng thái, số file/dòng và kết quả commit.
Đường dẫn database và folder log được nhớ trên từng máy bằng QSettings. Có thể đặt biến môi trường `ARTS_DB_PATH` để cung cấp đường dẫn database khi mở app. Không tự tạo folder mạng nếu đường dẫn sai hoặc không truy cập được.
3. Tìm file
Quét `os.walk` đúng một lần cho cả khoảng ngày, không quét lại toàn bộ folder cho từng ngày. Duyệt tới mọi tầng thư mục dưới root, hỗ trợ cả:
`Root\Machine1\2026-10-01.txt`
`Root\Machine2\2026-10\2026-10-01_log.txt`
`Root\Machine3\2026-10\Subfolder\2026-10-02.TXT`
Giữ quy tắc ARTs: phần đầu tên file là `YYYY-MM-DD`, phần mở rộng TXT không phân biệt hoa/thường. `20261001.txt` không đúng cách đặt tên của parser import ARTs này. Ngày import lấy từ tên file, không dùng ngày sửa file hay tên folder tháng.
Nếu duyệt folder hoặc đọc một file đã chọn bị lỗi quyền/mất kết nối, dừng import trước bước thay dữ liệu. Không tự bỏ qua folder không truy cập được. Không đi theo symlink thư mục. Người dùng cần chọn root chứa đầy đủ máy của các ngày định import vì thay thế theo toàn bộ ngày, không theo riêng máy.
4. Giữ nguyên bảng data và parser
Cấu trúc `data` giữ đúng thứ tự và kiểu khai báo trong ARTs gốc:
Cột	Kiểu
ID	INTEGER PRIMARY KEY AUTOINCREMENT
LOTID	TEXT
File_Date	TEXT
Datetime	TEXT
EQP	TEXT
Handler	TEXT
ZONE	TEXT
SLOT	INTEGER
Model	TEXT
Qty	INTEGER
Fail	INTEGER
SCRAP	TEXT
FULLSITE	TEXT
BIN	TEXT
BCODE	TEXT
Giữ cách xử lý `services/import_service.py` của ARTs gốc:
Chỉ lấy dòng chứa `FUNCTION=SLOT_END`.
Giữ nguyên vị trí tách LOTID, EQPID, SLOT, BIN, ZONE, SCRAP, BCODE, FULLSITE.
`File_Date`: 10 ký tự đầu tên file bỏ dấu `-`, thành `yyyyMMdd`.
`Datetime`: File_Date ghép giờ lấy từ dòng; giá trị không chuyển được vẫn thành NULL như parser cũ.
`Handler`: ký tự cuối EQPID; `EQP`: phần còn lại.
`Model`: BCODE tại lát cắt `[12:17]`.
`Qty`: số ký tự thỏa `isdigit()` trong BIN, bao gồm chữ số 0.
`Fail`: số ký tự thuộc `23456789` trong BIN.
Giữ chính sách mở file/encoding với `errors='ignore'` của ARTs gốc.
Dòng SLOT_END sai cấu trúc vẫn bị bỏ qua như bản cũ, nhưng thêm log `PARSE_SKIP` kèm file và số dòng. Vì vậy số dòng import là số dòng parser chấp nhận, không nhất thiết bằng số dòng SLOT_END trong file. Không thay đổi nghiệp vụ này trong bản import.
Không tự loại bản ghi trùng giữa nhiều file vì bản cũ không có bước đó.
Parser gốc được giữ tại `reference/arts_import_original.py` để đối chiếu, không dùng trực tiếp lúc chạy app. Parser mới giữ biểu thức tách trường và chuyển đổi của bản gốc, chuyển sang xử lý từng lô để hạn chế RAM.
5. Luồng xử lý và import lại như LI PRIME
Kiểm tra From–To và tìm file phù hợp.
Khởi tạo/kiểm tra database ở worker. Dùng SQLite rollback journal DELETE, `synchronous=FULL`, không WAL trên ổ mạng.
Nhận khóa import dùng chung, lưu chủ sở hữu theo máy/user/process/batch.
Heartbeat gia hạn lease 15 phút mỗi 30 giây bằng connection riêng.
Đọc từng file vào snapshot tạm local, sau đó parse và ghi staging local theo lô 5.000 dòng. Không giữ toàn bộ dữ liệu các file trong RAM.
Dừng heartbeat, kiểm tra hủy và quyền sở hữu khóa trước khi ghi chính.
`BEGIN IMMEDIATE`; kiểm tra lại khóa; lấy các ngày có dòng hợp lệ trong staging.
Xóa toàn bộ dòng data của các ngày đó, không giới hạn máy, Handler, Zone hay Slot.
Chèn dữ liệu staging theo lô 5.000 dòng trong cùng transaction, cập nhật trạng thái import và revision.
Giải phóng khóa import trong transaction và COMMIT. Kết quả thành công chỉ phát sau khi commit trả về thành công.
Ví dụ From 01/10 đến To 03/10: nếu 01/10 và 03/10 có dữ liệu hợp lệ còn 02/10 không có file, chỉ thay 01/10 và 03/10; giữ nguyên dữ liệu 02/10 và thông báo ngày thiếu.
Ngày có file nhưng không có dòng hợp lệ: giữ nguyên dữ liệu ngày đó. Nếu toàn bộ staging rỗng: báo lỗi, không xóa dữ liệu. Nếu một ngày có cả file rỗng và file có dòng hợp lệ, ngày đó vẫn được thay bằng tổng dòng hợp lệ đọc được, đúng chính sách bỏ qua dòng lỗi của parser gốc.
Nếu lỗi hoặc hủy trước commit: rollback toàn bộ DELETE/INSERT của cả lần import, giữ nguyên dữ liệu đã commit trước đó. Không commit từng lô lên database chính. ID được sinh mới sau import lại; không giữ ID cũ. Các ngày ngoài tập ngày thay thế không bị xóa.
File được chụp tối đa số byte tại lúc mở để không đọc vô hạn khi máy nối thêm log. File thay đổi sau khi snapshot đọc xong không làm hủy import; lần này dùng nội dung đã chụp, lần import sau lấy bản mới. Đây không phải snapshot nguyên tử của hệ thống file: nếu file bị sửa nội dung tại chỗ ngay trong lúc sao chép thì không bảo đảm ảnh chụp nhất quán. Nếu file bị thu ngắn khiến không đọc đủ số byte đã xác định thì dừng trước khi thay dữ liệu.
6. Nhiều máy dùng chung SQLite
Mỗi tác vụ mở connection riêng và đóng trong `finally`; không chia sẻ connection giữa các thread. Khóa `arts_import_lock` ngăn hai phiên app mới/CLI mới import đồng thời. Importer ARTs cũ không biết khóa này, vì vậy không trộn các phiên cũ/mới ghi cùng database.
Khi đang scan/parse/staging, không giữ transaction ghi database chính. Khi DELETE/INSERT/COMMIT, SQLite vẫn có thể chờ reader hoặc writer khác; timeout chính là 60 giây mỗi thao tác khóa, không phải giới hạn tổng thời gian import. Nếu hết thời gian chờ thì báo lỗi và rollback phần chưa commit; không tự lặp lại việc ghi vô hạn.
Heartbeat dùng timeout 2 giây và log lỗi; kiểm tra quyền khóa lần cuối bắt buộc trước DELETE. Khi tiến trình bị tắt bất thường, lease hết hạn sau tối đa khoảng 15 phút từ lần gia hạn cuối. Khóa SQLite của transaction và lease import là hai cơ chế riêng. Máy dùng chung cần đồng bộ đồng hồ.
Nút Hủy import là yêu cầu hủy có kiểm soát, được kiểm tra khi đọc file, parse dòng và giữa các lô ghi. Không cưỡng bức dừng QThread hay connection. Trong lúc SQLite đang chờ khóa/commit, hủy có thể phải chờ thao tác đó trả về. Nếu commit đã thành công thì vẫn báo thành công, không giả vờ hủy dữ liệu đã commit. Đóng cửa sổ khi import đang chạy sẽ yêu cầu hủy và giữ cửa sổ tới khi worker kết thúc; đóng lại sau đó.
Không cam kết hết lock hoặc tốc độ cụ thể trên SMB/NAS. Mất kết nối trong thời điểm commit cần xem log và kiểm tra database khi kết nối phục hồi; không suy ra kết quả commit chỉ từ lỗi kết nối.
7. Các bảng hỗ trợ và index
Không thêm cột vào `data`. Tạo thêm:
`arts_import_lock`: lease import dùng chung.
`arts_import_status`: ngày, batch, thời điểm UTC, số dòng của lần import gần nhất.
`arts_data_revision`: tăng revision trong cùng transaction với dữ liệu, làm nền cho các tab tương lai phát hiện dữ liệu mới.
`idx_arts_data_file_date`: index trên File_Date phục vụ thay dữ liệu theo ngày.
Không tự VACUUM hoặc ANALYZE toàn bộ database sau mỗi import. Xóa rồi import lại không đảm bảo kích thước file DB giảm ngay; các trang được tái sử dụng.
8. Cấu trúc code
File/Folder	Nhiệm vụ
main.py	Khởi động UI, log local
ui/main_window.py	Chọn database, nút Import, tiến độ, hủy
ui/import_dialog.py	Dialog From–To
workers/import_worker.py	Worker và signal về UI
services/file_discovery.py	Quét folder đệ quy theo tên file
services/log_parser.py	Quy tắc lấy dữ liệu ARTs
services/staging_service.py	Snapshot file và staging local
services/import_service.py	Điều phối luồng import
database/connection.py	Connection theo tác vụ, timeout, rollback/close
database/schema.py	Giữ schema data; bảng hỗ trợ
repositories/import_lock_repository.py	Lease và heartbeat
repositories/data_repository.py	DELETE/INSERT/COMMIT nguyên tử
domain/models.py	Cột, kết quả, loại lỗi
import_cli.py	Chạy cùng service từ dòng lệnh
tests/	Kiểm thử và benchmark giả lập
reference/	Parser gốc để đối chiếu
9. Log và chạy CLI
Windows: `%LOCALAPPDATA%\ARTs_Import_v1\logs\import.log`; xoay vòng 10 MiB/file, giữ 5 bản cũ. Ghi đường dẫn file, batch, chủ khóa, số dòng, thời gian đọc từng file, thời gian connection/transaction, commit/rollback và traceback. Không ghi nội dung test/serial từng dòng.
```bat
python import_cli.py --database "Z:\ARTs_New\arts_data.db" --folder "Z:\LogRoot" --from 2026-10-01 --to 2026-10-02
```
10. Kiểm thử và build
```bat
python -m unittest discover -s tests -v
python -m tests.benchmark_import --rows 1000000
python -m pip install pyinstaller
build_windows.bat
```
Bản build tạo tại `dist\ARTs_Import\ARTs_Import.exe`. Sao chép toàn bộ folder `dist\ARTs_Import`, không chỉ riêng EXE. Cài dependencies và build bằng Python trên chính Windows đích; bản bàn giao là source, không phải EXE đã build/kiểm chứng trên Windows.
Xem `TEST_REPORT.md` cho kết quả thực chạy. Chưa có log sản xuất và ổ mạng của người dùng trong môi trường kiểm thử. Trước khi dùng thực tế, thử trên database mới ở ổ mạng với log của một vài ngày, kiểm tra số dòng/Qty/Fail theo từng ngày/máy và thử nhiều máy mở đồng thời.

ARTs Import v1.0 — 02/10/2026
Phạm vi thực hiện
Đây là project mới, chạy độc lập, triển khai giai đoạn Import của ARTs mới theo kiến trúc của LI. Giải nén và chạy project này; không chép đè vào project ARTs cũ.
Đã có: cấu hình SQLite, nút Import, chọn From–To, chọn folder cha, quét TXT đệ quy, parser ARTs, staging local, thay dữ liệu theo ngày, khóa import dùng chung, trạng thái nút, hủy khi đóng cửa sổ, log chi tiết và CLI dùng cùng service.
Chưa triển khai các giai đoạn sau: Summary, Analyze, Machine Slot Yield, Alarm/Monitor, mail, scheduler tự động. Bản này không tự tính các bảng phụ thuộc của ARTs cũ. Chọn database riêng cho app mới trên ổ mạng, ví dụ `Z:\ARTs_New\arts_data.db` hoặc `\\server\share\ARTs_New\arts_data.db`. Các máy chạy bản mới chọn cùng một đường dẫn database. Không sử dụng database sản xuất của app cũ; app từ chối database có các bảng phụ thuộc cũ để không làm sai số liệu của app đó.
Cài và chạy — giao diện v1.1
Chép đè các file trong bản patch vào thư mục project v1.0 (cùng cấp `main.py`), giữ nguyên các file còn lại. Không xóa project cũ. Bản patch không chứa database và không di chuyển dữ liệu.
```bat
python -m pip install -r requirements.txt
python main.py
```
Cửa sổ chính chỉ còn nút IMPORT màu xanh. Bấm nút để mở dialog Chọn khoảng ngày import với Từ ngày / Đến ngày, định dạng `dd/MM/yyyy`. Bấm Tiếp tục, chọn folder cha chứa các máy. Trong khi import, nút bị vô hiệu hóa và hiện “Đang import…”. Sau khi worker kết thúc và commit thành công, hiện dialog Success; nếu lỗi hiện dialog lỗi. Không còn tiêu đề lớn, chọn database, khung log, thanh tiến độ hoặc nút hủy trên cửa sổ chính.
Database được xác định theo thứ tự:
Biến môi trường `ARTS_DB_PATH`.
`DATABASE_PATH` trong `app_config.py` nếu điền đường dẫn cố định.
Đường dẫn đã chọn ở v1.0, lưu trong QSettings của đúng user/máy.
Nếu chưa có cấu hình: `arts_data.db` cạnh `main.py` khi chạy source, hoặc cạnh EXE khi đã build.
Ví dụ cấu hình cố định cho các máy dùng chung ổ mạng trong `app_config.py`:
```python
DATABASE_PATH = r"\\server\share\ARTs_New\arts_data.db"
```
Không điền đường dẫn mẫu này nếu đó không phải ổ mạng của bạn. Bản patch mặc định để trống nhằm giữ lại database đã chọn ở phiên trước. Máy khác/user khác không tự có QSettings này; đặt cùng `ARTS_DB_PATH` hoặc `DATABASE_PATH` để dùng chung database. Nếu chạy EXE, thay cấu hình source rồi build lại, hoặc dùng biến môi trường.
Không kiểm tra folder mạng, không kết nối SQLite, không nạp pandas hay tạo log khi mở app. Khởi động chỉ nạp Qt và các widget cần thiết để vẽ cửa sổ. Controller/dialog nạp khi bấm Import; worker nạp sau khi chọn folder; pandas/SQLite/parser/logging được nạp và chạy trong worker. Các thư viện Qt tối thiểu vẫn phải nạp trước khi hiện cửa sổ. Không chủ động preload thư viện nặng ngay sau show vì bản này chưa cần chúng cho đến khi import.
Tổ chức mới: `main_window.py` chỉ là khung cửa sổ; `ui/widgets/import_panel.py` chứa nút/style; `ui/import_dialog.py` chứa dialog ngày; `controllers/import_controller.py` điều phối UI và kết quả; `services/logging_service.py` quản lý log; `app_config.py` xác định đường dẫn database. Parser, staging, transaction và khóa import không thay đổi trong v1.1.
3. Tìm file
Quét `os.walk` đúng một lần cho cả khoảng ngày, không quét lại toàn bộ folder cho từng ngày. Duyệt tới mọi tầng thư mục dưới root, hỗ trợ cả:
`Root\Machine1\2026-10-01.txt`
`Root\Machine2\2026-10\2026-10-01_log.txt`
`Root\Machine3\2026-10\Subfolder\2026-10-02.TXT`
Giữ quy tắc ARTs: phần đầu tên file là `YYYY-MM-DD`, phần mở rộng TXT không phân biệt hoa/thường. `20261001.txt` không đúng cách đặt tên của parser import ARTs này. Ngày import lấy từ tên file, không dùng ngày sửa file hay tên folder tháng.
Nếu duyệt folder hoặc đọc một file đã chọn bị lỗi quyền/mất kết nối, dừng import trước bước thay dữ liệu. Không tự bỏ qua folder không truy cập được. Không đi theo symlink thư mục. Người dùng cần chọn root chứa đầy đủ máy của các ngày định import vì thay thế theo toàn bộ ngày, không theo riêng máy.
4. Giữ nguyên bảng data và parser
Cấu trúc `data` giữ đúng thứ tự và kiểu khai báo trong ARTs gốc:
Cột	Kiểu
ID	INTEGER PRIMARY KEY AUTOINCREMENT
LOTID	TEXT
File_Date	TEXT
Datetime	TEXT
EQP	TEXT
Handler	TEXT
ZONE	TEXT
SLOT	INTEGER
Model	TEXT
Qty	INTEGER
Fail	INTEGER
SCRAP	TEXT
FULLSITE	TEXT
BIN	TEXT
BCODE	TEXT
Giữ cách xử lý `services/import_service.py` của ARTs gốc:
Chỉ lấy dòng chứa `FUNCTION=SLOT_END`.
Giữ nguyên vị trí tách LOTID, EQPID, SLOT, BIN, ZONE, SCRAP, BCODE, FULLSITE.
`File_Date`: 10 ký tự đầu tên file bỏ dấu `-`, thành `yyyyMMdd`.
`Datetime`: File_Date ghép giờ lấy từ dòng; giá trị không chuyển được vẫn thành NULL như parser cũ.
`Handler`: ký tự cuối EQPID; `EQP`: phần còn lại.
`Model`: BCODE tại lát cắt `[12:17]`.
`Qty`: số ký tự thỏa `isdigit()` trong BIN, bao gồm chữ số 0.
`Fail`: số ký tự thuộc `23456789` trong BIN.
Giữ chính sách mở file/encoding với `errors='ignore'` của ARTs gốc.
Dòng SLOT_END sai cấu trúc vẫn bị bỏ qua như bản cũ, nhưng thêm log `PARSE_SKIP` kèm file và số dòng. Vì vậy số dòng import là số dòng parser chấp nhận, không nhất thiết bằng số dòng SLOT_END trong file. Không thay đổi nghiệp vụ này trong bản import.
Không tự loại bản ghi trùng giữa nhiều file vì bản cũ không có bước đó.
Parser gốc được giữ tại `reference/arts_import_original.py` để đối chiếu, không dùng trực tiếp lúc chạy app. Parser mới giữ biểu thức tách trường và chuyển đổi của bản gốc, chuyển sang xử lý từng lô để hạn chế RAM.
5. Luồng xử lý và import lại như LI PRIME
Kiểm tra From–To và tìm file phù hợp.
Khởi tạo/kiểm tra database ở worker. Dùng SQLite rollback journal DELETE, `synchronous=FULL`, không WAL trên ổ mạng.
Nhận khóa import dùng chung, lưu chủ sở hữu theo máy/user/process/batch.
Heartbeat gia hạn lease 15 phút mỗi 30 giây bằng connection riêng.
Đọc từng file vào snapshot tạm local, sau đó parse và ghi staging local theo lô 5.000 dòng. Không giữ toàn bộ dữ liệu các file trong RAM.
Dừng heartbeat, kiểm tra hủy và quyền sở hữu khóa trước khi ghi chính.
`BEGIN IMMEDIATE`; kiểm tra lại khóa; lấy các ngày có dòng hợp lệ trong staging.
Xóa toàn bộ dòng data của các ngày đó, không giới hạn máy, Handler, Zone hay Slot.
Chèn dữ liệu staging theo lô 5.000 dòng trong cùng transaction, cập nhật trạng thái import và revision.
Giải phóng khóa import trong transaction và COMMIT. Kết quả thành công chỉ phát sau khi commit trả về thành công.
Ví dụ From 01/10 đến To 03/10: nếu 01/10 và 03/10 có dữ liệu hợp lệ còn 02/10 không có file, chỉ thay 01/10 và 03/10; giữ nguyên dữ liệu 02/10 và thông báo ngày thiếu.
Ngày có file nhưng không có dòng hợp lệ: giữ nguyên dữ liệu ngày đó. Nếu toàn bộ staging rỗng: báo lỗi, không xóa dữ liệu. Nếu một ngày có cả file rỗng và file có dòng hợp lệ, ngày đó vẫn được thay bằng tổng dòng hợp lệ đọc được, đúng chính sách bỏ qua dòng lỗi của parser gốc.
Nếu lỗi hoặc hủy trước commit: rollback toàn bộ DELETE/INSERT của cả lần import, giữ nguyên dữ liệu đã commit trước đó. Không commit từng lô lên database chính. ID được sinh mới sau import lại; không giữ ID cũ. Các ngày ngoài tập ngày thay thế không bị xóa.
File được chụp tối đa số byte tại lúc mở để không đọc vô hạn khi máy nối thêm log. File thay đổi sau khi snapshot đọc xong không làm hủy import; lần này dùng nội dung đã chụp, lần import sau lấy bản mới. Đây không phải snapshot nguyên tử của hệ thống file: nếu file bị sửa nội dung tại chỗ ngay trong lúc sao chép thì không bảo đảm ảnh chụp nhất quán. Nếu file bị thu ngắn khiến không đọc đủ số byte đã xác định thì dừng trước khi thay dữ liệu.
6. Nhiều máy dùng chung SQLite
Mỗi tác vụ mở connection riêng và đóng trong `finally`; không chia sẻ connection giữa các thread. Khóa `arts_import_lock` ngăn hai phiên app mới/CLI mới import đồng thời. Importer ARTs cũ không biết khóa này, vì vậy không trộn các phiên cũ/mới ghi cùng database.
Khi đang scan/parse/staging, không giữ transaction ghi database chính. Khi DELETE/INSERT/COMMIT, SQLite vẫn có thể chờ reader hoặc writer khác; timeout chính là 60 giây mỗi thao tác khóa, không phải giới hạn tổng thời gian import. Nếu hết thời gian chờ thì báo lỗi và rollback phần chưa commit; không tự lặp lại việc ghi vô hạn.
Heartbeat dùng timeout 2 giây và log lỗi; kiểm tra quyền khóa lần cuối bắt buộc trước DELETE. Khi tiến trình bị tắt bất thường, lease hết hạn sau tối đa khoảng 15 phút từ lần gia hạn cuối. Khóa SQLite của transaction và lease import là hai cơ chế riêng. Máy dùng chung cần đồng bộ đồng hồ.
Thao tác đóng cửa sổ khi import đang chạy gửi yêu cầu hủy có kiểm soát, được kiểm tra khi đọc file, parse dòng và giữa các lô ghi. Không cưỡng bức dừng QThread hay connection. Trong lúc SQLite đang chờ khóa/commit, hủy có thể phải chờ thao tác đó trả về. Nếu commit đã thành công thì vẫn báo thành công, không giả vờ hủy dữ liệu đã commit. Đóng cửa sổ khi import đang chạy sẽ yêu cầu hủy và giữ cửa sổ tới khi worker kết thúc; đóng lại sau đó.
Không cam kết hết lock hoặc tốc độ cụ thể trên SMB/NAS. Mất kết nối trong thời điểm commit cần xem log và kiểm tra database khi kết nối phục hồi; không suy ra kết quả commit chỉ từ lỗi kết nối.
7. Các bảng hỗ trợ và index
Không thêm cột vào `data`. Tạo thêm:
`arts_import_lock`: lease import dùng chung.
`arts_import_status`: ngày, batch, thời điểm UTC, số dòng của lần import gần nhất.
`arts_data_revision`: tăng revision trong cùng transaction với dữ liệu, làm nền cho các tab tương lai phát hiện dữ liệu mới.
`idx_arts_data_file_date`: index trên File_Date phục vụ thay dữ liệu theo ngày.
Không tự VACUUM hoặc ANALYZE toàn bộ database sau mỗi import. Xóa rồi import lại không đảm bảo kích thước file DB giảm ngay; các trang được tái sử dụng.
8. Cấu trúc code
File/Folder	Nhiệm vụ
main.py	Khởi động khung UI; hàm log tương thích CLI được nạp khi cần
ui/main_window.py	Khung cửa sổ và xử lý yêu cầu đóng
ui/widgets/import_panel.py	Nút Import và style
controllers/import_controller.py	Điều phối dialog, worker và thông báo kết quả
app_config.py	Xác định đường dẫn database
services/logging_service.py	Khởi tạo log local khi bắt đầu tác vụ
ui/import_dialog.py	Dialog From–To
workers/import_worker.py	Worker và signal về UI
services/file_discovery.py	Quét folder đệ quy theo tên file
services/log_parser.py	Quy tắc lấy dữ liệu ARTs
services/staging_service.py	Snapshot file và staging local
services/import_service.py	Điều phối luồng import
database/connection.py	Connection theo tác vụ, timeout, rollback/close
database/schema.py	Giữ schema data; bảng hỗ trợ
repositories/import_lock_repository.py	Lease và heartbeat
repositories/data_repository.py	DELETE/INSERT/COMMIT nguyên tử
domain/models.py	Cột, kết quả, loại lỗi
import_cli.py	Chạy cùng service từ dòng lệnh
tests/	Kiểm thử và benchmark giả lập
reference/	Parser gốc để đối chiếu
9. Log và chạy CLI
Windows: `%LOCALAPPDATA%\ARTs_Import_v1\logs\import.log`; xoay vòng 10 MiB/file, giữ 5 bản cũ. Ghi đường dẫn file, batch, chủ khóa, số dòng, thời gian đọc từng file, thời gian connection/transaction, commit/rollback và traceback. Không ghi nội dung test/serial từng dòng.
```bat
python import_cli.py --database "Z:\ARTs_New\arts_data.db" --folder "Z:\LogRoot" --from 2026-10-01 --to 2026-10-02
```
Kiểm thử và build
```bat
python -m unittest discover -s tests -v
python -m tests.benchmark_import --rows 1000000
python -m pip install pyinstaller
build_windows.bat
```
Bản build tạo tại `dist\ARTs_Import\ARTs_Import.exe`. Sao chép toàn bộ folder `dist\ARTs_Import`, không chỉ riêng EXE. Cài dependencies và build bằng Python trên chính Windows đích; bản bàn giao là source, không phải EXE đã build/kiểm chứng trên Windows.
Xem `TEST_REPORT.md` cho kết quả thực chạy. Chưa có log sản xuất và ổ mạng của người dùng trong môi trường kiểm thử. Trước khi dùng thực tế, thử trên database mới ở ổ mạng với log của một vài ngày, kiểm tra số dòng/Qty/Fail theo từng ngày/máy và thử nhiều máy mở đồng thời.
Cập nhật v1.2 — Bộ lọc ARTs theo giao diện LI
Chép đè các file trong patch vào project đã áp dụng v1.1, cùng cấp main.py. Giữ các file không có trong patch. Không xóa database.
Bố cục và thao tác
Hàng trên: From, To, EQP.
Hàng dưới: Handler, Zone, Slot.
Hai cột cuối: Model, Scrap Code, cao bằng hai hàng bộ lọc; không có Tier.
Dưới bộ lọc: IMPORT bên trái, SEARCH bên phải. Nền xanh nhạt, khung trắng và nút xanh theo LI.
From mặc định hôm nay trừ 14 ngày, To hôm nay; yyyy-MM-dd như LI. Đổi ngày để From không vượt To.
EQP/Handler/Zone/Slot là dropdown chọn một giá trị; “Chọn…” tương ứng None/không giới hạn trường đó.
Model có checkbox/Select All và mặc định chọn tất cả; Scrap Code mặc định chưa chọn, giống LI.
SEARCH lưu current_criteria, phát signal MainWindow.filter_applied và hiển thị điều kiện đã chọn. Bản này chưa có bảng Summary/Alarm/Report nên SEARCH chưa truy vấn hay hiển thị báo cáo. Danh sách Model rỗng là không chọn model; danh sách Scrap rỗng là chưa chọn mã. Tab sử dụng điều kiện cần giữ rõ quy ước này.
Nguồn lựa chọn là toàn bộ dữ liệu đã import, không quét lại theo From/To mỗi lần chỉnh ngày; giống bộ lọc chính LI. Chưa áp dụng lọc phụ thuộc EQP → Handler/Zone/Slot.
Tối ưu và nguồn dữ liệu
Window hiện trước; sau show 100 ms mới tạo worker tải danh mục. SQLite/repository nạp trong worker, pandas chỉ nạp lúc import.
EQP, Handler, ZONE, SLOT, Model lấy từ các cột cùng tên bảng data. Scrap Code tách từ SCRAP: phân cách dấu phẩy, lấy phần trước dấu hai chấm, bỏ khoảng trắng; 0 thành 0000 theo ARTs. Không hạn chế mã phải là 4 chữ số của LI, không tô đỏ mã ưu tiên LI cho ARTs.
Giống FilterOptionRepository LI: dùng recursive MIN/index seeks để lấy từng giá trị khác nhau; không tải các dòng test vào UI. Tạo các index idx_arts_filter_EQP/Handler/ZONE/SLOT/Model/SCRAP. Bộ lọc mới được sắp theo thứ tự giá trị SQL, SLOT INTEGER theo số.
Database mới tạo index trong bước khởi tạo import. Database v1.0/v1.1 đã có dữ liệu sẽ tạo index còn thiếu một lần trong worker nền lúc tải bộ lọc; lần đầu có thể lâu và cần quyền ghi. Tạo index có thể chờ khóa, và các index cũng làm tăng công việc khi import. Không xem thời gian benchmark v1.0 là tốc độ đã đo của v1.2.
Mỗi lần tải lấy một transaction snapshot và đóng connection sau khi đọc. Danh sách tái sử dụng trong UI, không tải lại khi đổi ngày/nhấn dropdown.
Import thành công ở máy hiện tại: tải lại lựa chọn ngay. Mỗi 60 giây worker kiểm tra arts_data_revision để phát hiện import từ máy khác; revision không đổi thì không truy vấn lại danh mục. Cơ chế dựa trên importer mới cập nhật revision.
Giữ EQP/Handler/Zone/Slot đã chọn nếu còn tồn tại; giá trị bị xóa trở về “Chọn…”. Giữ checkbox còn hợp lệ; khi trước đó chọn tất cả, lựa chọn mới thêm tiếp tục được chọn.
Chưa có database: trả danh sách rỗng, không tự tạo file trong luồng tải bộ lọc.
Database bận: worker timeout 2 giây và thử lại mỗi 5 giây; SEARCH/danh mục tạm vô hiệu hóa, hiện thông báo “Database đang cập nhật, vui lòng thử lại sau 2 phút”. Thông báo có thể đóng; khi đọc được sẽ tự đóng và mở lại bộ lọc. Hai phút là nội dung thông báo, không phải thời gian chờ bắt buộc.
Lỗi khác: hiển thị lỗi trong dòng trạng thái, thử lại ở chu kỳ sau. Đóng app hủy worker và đợi kết thúc, không terminate QThread.
File chính mới/thay đổi
ui/widgets/filter_panel.py, ui/widgets/check_list.py, controllers/filter_controller.py,
workers/filter_option_worker.py, repositories/filter_option_repository.py,
ui/main_window.py, controllers/import_controller.py, database/schema.py.
Giữ nguyên parser, quy tắc thay dữ liệu ngày, dialog import và Success của v1.1.
ui/widgets/import_panel.py cũ có thể giữ nguyên, hiện không còn được MainWindow sử dụng.
Kiểm chứng
24 tests PASS, gồm các tests import hiện có và kiểm tra danh mục, tách Scrap, revision cache,
import lại loại giá trị cũ, database chưa tồn tại, checkbox, điều kiện lọc và giao diện.
Đã kiểm tra ảnh render bằng Qt offscreen. Chưa đo trên Windows/ổ mạng thật hoặc 1 triệu dòng với các index mới.
ARTs Import v1.0 — 02/10/2026
Phạm vi thực hiện
Đây là project mới, chạy độc lập, triển khai giai đoạn Import của ARTs mới theo kiến trúc của LI. Giải nén và chạy project này; không chép đè vào project ARTs cũ.
Đã có: cấu hình SQLite, nút Import, chọn From–To, chọn folder cha, quét TXT đệ quy, parser ARTs, staging local, thay dữ liệu theo ngày, khóa import dùng chung, trạng thái nút, hủy khi đóng cửa sổ, log chi tiết và CLI dùng cùng service.
Chưa triển khai các giai đoạn sau: Summary, Analyze, Machine Slot Yield, Alarm/Monitor, mail, scheduler tự động. Bản này không tự tính các bảng phụ thuộc của ARTs cũ. Chọn database riêng cho app mới trên ổ mạng, ví dụ `Z:\ARTs_New\arts_data.db` hoặc `\\server\share\ARTs_New\arts_data.db`. Các máy chạy bản mới chọn cùng một đường dẫn database. Không sử dụng database sản xuất của app cũ; app từ chối database có các bảng phụ thuộc cũ để không làm sai số liệu của app đó.
Cài và chạy — giao diện v1.1
Chép đè các file trong bản patch vào thư mục project v1.0 (cùng cấp `main.py`), giữ nguyên các file còn lại. Không xóa project cũ. Bản patch không chứa database và không di chuyển dữ liệu.
```bat
python -m pip install -r requirements.txt
python main.py
```
Cửa sổ chính có bộ lọc chung, nút IMPORT và SEARCH. Bấm nút để mở dialog Chọn khoảng ngày import với Từ ngày / Đến ngày, định dạng `dd/MM/yyyy`. Bấm Tiếp tục, chọn folder cha chứa các máy. Trong khi import, nút bị vô hiệu hóa và hiện “Đang import…”. Sau khi worker kết thúc và commit thành công, hiện dialog Success; nếu lỗi hiện dialog lỗi. Không còn tiêu đề lớn, chọn database, khung log, thanh tiến độ hoặc nút hủy trên cửa sổ chính.
Database được xác định theo thứ tự:
Biến môi trường `ARTS_DB_PATH`.
`DATABASE_PATH` trong `app_config.py` nếu điền đường dẫn cố định.
Đường dẫn đã chọn ở v1.0, lưu trong QSettings của đúng user/máy.
Nếu chưa có cấu hình: `arts_data.db` cạnh `main.py` khi chạy source, hoặc cạnh EXE khi đã build.
Ví dụ cấu hình cố định cho các máy dùng chung ổ mạng trong `app_config.py`:
```python
DATABASE_PATH = r"\\server\share\ARTs_New\arts_data.db"
```
Không điền đường dẫn mẫu này nếu đó không phải ổ mạng của bạn. Bản patch mặc định để trống nhằm giữ lại database đã chọn ở phiên trước. Máy khác/user khác không tự có QSettings này; đặt cùng `ARTS_DB_PATH` hoặc `DATABASE_PATH` để dùng chung database. Nếu chạy EXE, thay cấu hình source rồi build lại, hoặc dùng biến môi trường.
Khởi động chỉ nạp Qt và widget để vẽ cửa sổ. Sau show, QTimer 100 ms khởi động controller/worker bộ lọc; SQLite và repository nạp trong worker. Không có truy vấn DB trên UI thread. Pandas/parser vẫn chỉ nạp khi import. Qt tối thiểu phải nạp trước show.
Tổ chức mới: `main_window.py` chỉ là khung cửa sổ; `ui/widgets/import_panel.py` chứa nút/style; `ui/import_dialog.py` chứa dialog ngày; `controllers/import_controller.py` điều phối UI và kết quả; `services/logging_service.py` quản lý log; `app_config.py` xác định đường dẫn database. Parser, staging, transaction và khóa import không thay đổi trong v1.1.
3. Tìm file
Quét `os.walk` đúng một lần cho cả khoảng ngày, không quét lại toàn bộ folder cho từng ngày. Duyệt tới mọi tầng thư mục dưới root, hỗ trợ cả:
`Root\Machine1\2026-10-01.txt`
`Root\Machine2\2026-10\2026-10-01_log.txt`
`Root\Machine3\2026-10\Subfolder\2026-10-02.TXT`
Giữ quy tắc ARTs: phần đầu tên file là `YYYY-MM-DD`, phần mở rộng TXT không phân biệt hoa/thường. `20261001.txt` không đúng cách đặt tên của parser import ARTs này. Ngày import lấy từ tên file, không dùng ngày sửa file hay tên folder tháng.
Nếu duyệt folder hoặc đọc một file đã chọn bị lỗi quyền/mất kết nối, dừng import trước bước thay dữ liệu. Không tự bỏ qua folder không truy cập được. Không đi theo symlink thư mục. Người dùng cần chọn root chứa đầy đủ máy của các ngày định import vì thay thế theo toàn bộ ngày, không theo riêng máy.
4. Giữ nguyên bảng data và parser
Cấu trúc `data` giữ đúng thứ tự và kiểu khai báo trong ARTs gốc:
Cột	Kiểu
ID	INTEGER PRIMARY KEY AUTOINCREMENT
LOTID	TEXT
File_Date	TEXT
Datetime	TEXT
EQP	TEXT
Handler	TEXT
ZONE	TEXT
SLOT	INTEGER
Model	TEXT
Qty	INTEGER
Fail	INTEGER
SCRAP	TEXT
FULLSITE	TEXT
BIN	TEXT
BCODE	TEXT
Giữ cách xử lý `services/import_service.py` của ARTs gốc:
Chỉ lấy dòng chứa `FUNCTION=SLOT_END`.
Giữ nguyên vị trí tách LOTID, EQPID, SLOT, BIN, ZONE, SCRAP, BCODE, FULLSITE.
`File_Date`: 10 ký tự đầu tên file bỏ dấu `-`, thành `yyyyMMdd`.
`Datetime`: File_Date ghép giờ lấy từ dòng; giá trị không chuyển được vẫn thành NULL như parser cũ.
`Handler`: ký tự cuối EQPID; `EQP`: phần còn lại.
`Model`: BCODE tại lát cắt `[12:17]`.
`Qty`: số ký tự thỏa `isdigit()` trong BIN, bao gồm chữ số 0.
`Fail`: số ký tự thuộc `23456789` trong BIN.
Giữ chính sách mở file/encoding với `errors='ignore'` của ARTs gốc.
Dòng SLOT_END sai cấu trúc vẫn bị bỏ qua như bản cũ, nhưng thêm log `PARSE_SKIP` kèm file và số dòng. Vì vậy số dòng import là số dòng parser chấp nhận, không nhất thiết bằng số dòng SLOT_END trong file. Không thay đổi nghiệp vụ này trong bản import.
Không tự loại bản ghi trùng giữa nhiều file vì bản cũ không có bước đó.
Parser gốc được giữ tại `reference/arts_import_original.py` để đối chiếu, không dùng trực tiếp lúc chạy app. Parser mới giữ biểu thức tách trường và chuyển đổi của bản gốc, chuyển sang xử lý từng lô để hạn chế RAM.
5. Luồng xử lý và import lại như LI PRIME
Kiểm tra From–To và tìm file phù hợp.
Khởi tạo/kiểm tra database ở worker. Dùng SQLite rollback journal DELETE, `synchronous=FULL`, không WAL trên ổ mạng.
Nhận khóa import dùng chung, lưu chủ sở hữu theo máy/user/process/batch.
Heartbeat gia hạn lease 15 phút mỗi 30 giây bằng connection riêng.
Đọc từng file vào snapshot tạm local, sau đó parse và ghi staging local theo lô 5.000 dòng. Không giữ toàn bộ dữ liệu các file trong RAM.
Dừng heartbeat, kiểm tra hủy và quyền sở hữu khóa trước khi ghi chính.
`BEGIN IMMEDIATE`; kiểm tra lại khóa; lấy các ngày có dòng hợp lệ trong staging.
Xóa toàn bộ dòng data của các ngày đó, không giới hạn máy, Handler, Zone hay Slot.
Chèn dữ liệu staging theo lô 5.000 dòng trong cùng transaction, cập nhật trạng thái import và revision.
Giải phóng khóa import trong transaction và COMMIT. Kết quả thành công chỉ phát sau khi commit trả về thành công.
Ví dụ From 01/10 đến To 03/10: nếu 01/10 và 03/10 có dữ liệu hợp lệ còn 02/10 không có file, chỉ thay 01/10 và 03/10; giữ nguyên dữ liệu 02/10 và thông báo ngày thiếu.
Ngày có file nhưng không có dòng hợp lệ: giữ nguyên dữ liệu ngày đó. Nếu toàn bộ staging rỗng: báo lỗi, không xóa dữ liệu. Nếu một ngày có cả file rỗng và file có dòng hợp lệ, ngày đó vẫn được thay bằng tổng dòng hợp lệ đọc được, đúng chính sách bỏ qua dòng lỗi của parser gốc.
Nếu lỗi hoặc hủy trước commit: rollback toàn bộ DELETE/INSERT của cả lần import, giữ nguyên dữ liệu đã commit trước đó. Không commit từng lô lên database chính. ID được sinh mới sau import lại; không giữ ID cũ. Các ngày ngoài tập ngày thay thế không bị xóa.
File được chụp tối đa số byte tại lúc mở để không đọc vô hạn khi máy nối thêm log. File thay đổi sau khi snapshot đọc xong không làm hủy import; lần này dùng nội dung đã chụp, lần import sau lấy bản mới. Đây không phải snapshot nguyên tử của hệ thống file: nếu file bị sửa nội dung tại chỗ ngay trong lúc sao chép thì không bảo đảm ảnh chụp nhất quán. Nếu file bị thu ngắn khiến không đọc đủ số byte đã xác định thì dừng trước khi thay dữ liệu.
6. Nhiều máy dùng chung SQLite
Mỗi tác vụ mở connection riêng và đóng trong `finally`; không chia sẻ connection giữa các thread. Khóa `arts_import_lock` ngăn hai phiên app mới/CLI mới import đồng thời. Importer ARTs cũ không biết khóa này, vì vậy không trộn các phiên cũ/mới ghi cùng database.
Khi đang scan/parse/staging, không giữ transaction ghi database chính. Khi DELETE/INSERT/COMMIT, SQLite vẫn có thể chờ reader hoặc writer khác; timeout chính là 60 giây mỗi thao tác khóa, không phải giới hạn tổng thời gian import. Nếu hết thời gian chờ thì báo lỗi và rollback phần chưa commit; không tự lặp lại việc ghi vô hạn.
Heartbeat dùng timeout 2 giây và log lỗi; kiểm tra quyền khóa lần cuối bắt buộc trước DELETE. Khi tiến trình bị tắt bất thường, lease hết hạn sau tối đa khoảng 15 phút từ lần gia hạn cuối. Khóa SQLite của transaction và lease import là hai cơ chế riêng. Máy dùng chung cần đồng bộ đồng hồ.
Thao tác đóng cửa sổ khi import đang chạy gửi yêu cầu hủy có kiểm soát, được kiểm tra khi đọc file, parse dòng và giữa các lô ghi. Không cưỡng bức dừng QThread hay connection. Trong lúc SQLite đang chờ khóa/commit, hủy có thể phải chờ thao tác đó trả về. Nếu commit đã thành công thì vẫn báo thành công, không giả vờ hủy dữ liệu đã commit. Đóng cửa sổ khi import đang chạy sẽ yêu cầu hủy và giữ cửa sổ tới khi worker kết thúc; đóng lại sau đó.
Không cam kết hết lock hoặc tốc độ cụ thể trên SMB/NAS. Mất kết nối trong thời điểm commit cần xem log và kiểm tra database khi kết nối phục hồi; không suy ra kết quả commit chỉ từ lỗi kết nối.
7. Các bảng hỗ trợ và index
Không thêm cột vào `data`. Tạo thêm:
`arts_import_lock`: lease import dùng chung.
`arts_import_status`: ngày, batch, thời điểm UTC, số dòng của lần import gần nhất.
`arts_data_revision`: tăng revision trong cùng transaction với dữ liệu, làm nền cho các tab tương lai phát hiện dữ liệu mới.
`idx_arts_data_file_date`: index trên File_Date phục vụ thay dữ liệu theo ngày.
Không tự VACUUM hoặc ANALYZE toàn bộ database sau mỗi import. Xóa rồi import lại không đảm bảo kích thước file DB giảm ngay; các trang được tái sử dụng.
8. Cấu trúc code
File/Folder	Nhiệm vụ
main.py	Khởi động khung UI; hàm log tương thích CLI được nạp khi cần
ui/main_window.py	Khung cửa sổ và xử lý yêu cầu đóng
ui/widgets/import_panel.py	Nút Import và style
controllers/import_controller.py	Điều phối dialog, worker và thông báo kết quả
app_config.py	Xác định đường dẫn database
services/logging_service.py	Khởi tạo log local khi bắt đầu tác vụ
ui/import_dialog.py	Dialog From–To
workers/import_worker.py	Worker và signal về UI
services/file_discovery.py	Quét folder đệ quy theo tên file
services/log_parser.py	Quy tắc lấy dữ liệu ARTs
services/staging_service.py	Snapshot file và staging local
services/import_service.py	Điều phối luồng import
database/connection.py	Connection theo tác vụ, timeout, rollback/close
database/schema.py	Giữ schema data; bảng hỗ trợ
repositories/import_lock_repository.py	Lease và heartbeat
repositories/data_repository.py	DELETE/INSERT/COMMIT nguyên tử
domain/models.py	Cột, kết quả, loại lỗi
import_cli.py	Chạy cùng service từ dòng lệnh
tests/	Kiểm thử và benchmark giả lập
reference/	Parser gốc để đối chiếu
9. Log và chạy CLI
Windows: `%LOCALAPPDATA%\ARTs_Import_v1\logs\import.log`; xoay vòng 10 MiB/file, giữ 5 bản cũ. Ghi đường dẫn file, batch, chủ khóa, số dòng, thời gian đọc từng file, thời gian connection/transaction, commit/rollback và traceback. Không ghi nội dung test/serial từng dòng.
```bat
python import_cli.py --database "Z:\ARTs_New\arts_data.db" --folder "Z:\LogRoot" --from 2026-10-01 --to 2026-10-02
```
Kiểm thử và build
```bat
python -m unittest discover -s tests -v
python -m tests.benchmark_import --rows 1000000
python -m pip install pyinstaller
build_windows.bat
```
Bản build tạo tại `dist\ARTs_Import\ARTs_Import.exe`. Sao chép toàn bộ folder `dist\ARTs_Import`, không chỉ riêng EXE. Cài dependencies và build bằng Python trên chính Windows đích; bản bàn giao là source, không phải EXE đã build/kiểm chứng trên Windows.
Xem `TEST_REPORT.md` cho kết quả thực chạy. Chưa có log sản xuất và ổ mạng của người dùng trong môi trường kiểm thử. Trước khi dùng thực tế, thử trên database mới ở ổ mạng với log của một vài ngày, kiểm tra số dòng/Qty/Fail theo từng ngày/máy và thử nhiều máy mở đồng thời.


Cập nhật Yield ARTs by Handler — 02/10/2026
Áp dụng
Bản vá dành cho project đã áp dụng ARTs_Daily_Scrap_PPM_Update.zip. Đóng app, chép đè các file trong gói vào thư mục chứa main.py, giữ cấu trúc thư mục rồi chạy lại. Không cần import lại hoặc thay database. Bản vá không kèm database.
Chức năng mới
Trong Summary, dưới phần Yield ARTs Daily của máy, thêm bảng và biểu đồ:
`Yield ARTs by Handler | EQP: {EQP} | Handler: {Handler}`
Chọn EQP, Handler, From/To và Scrap Code rồi bấm SEARCH. Bảng mới dùng đúng mẫu Daily theo máy: Date, In Qty, Pass, Fail Qty, Fail PPM, Yield và PPM từng mã phát sinh. Khác biệt là chỉ lấy dữ liệu của Handler được chọn. Chưa chọn EQP hoặc Handler thì xóa dữ liệu Handler cũ và hiện hướng dẫn chọn.
Daily theo máy hiện tổng hợp tất cả Handler thuộc EQP. Daily theo Handler lấy riêng Handler được chọn. Cả hai áp dụng Zone, Slot và Model đang chọn; Scrap Code chỉ chọn mã vẽ biểu đồ, không lọc mẫu số In. Khối tổng hợp theo máy đầu Summary vẫn giữ cách lọc trước đây.
Công thức đếm mã lỗi và PPM giữ như bản Daily trước: mỗi mục mã trong SCRAP của bản ghi Fail > 0 tính một lần; phần sau dấu : không dùng làm số lượng; mã 0 hiển thị 0000. PPM mã = số lần mã / tổng In ngày của đúng phạm vi máy hoặc Handler × 1.000.000.
Sửa chung cho Daily máy và Handler
Ngày không có sản lượng: biểu đồ nối đường Yield xuống 0%, hiển thị nhãn 0.00. Ô Fail PPM và Yield trong bảng để trống, không hiện dấu gạch hoặc 0%.
Bảng co chiều ngang đúng tổng chiều rộng các cột, kể cả cột Scrap Code cuối cùng; không giữ khung rộng cố định 1.550 px.
Chiều cao bảng cũng vừa số dòng, tối đa 560 px. Nếu cần cuộn dọc, khung chỉ cộng thêm chiều rộng thanh cuộn. Summary dùng cuộn ngang khi quá nhiều mã.
Cột chồng chỉ gồm Scrap Code đang chọn và có PPM dương; không tạo legend cho mã không phát sinh.
Tooltip của Handler có thêm Handler ngoài EQP/ngày/mã/PPM/In/Out/Fail/Yield.
Hàng đầu bảng bôi chọn được. Ctrl+C copy đúng các ô được chọn; chỉ copy tiêu đề khi đã bôi chọn các ô tiêu đề đó.
Tối ưu và lưu dữ liệu
Máy và Handler được tổng hợp trong một truy vấn GROUP BY theo ngày/Handler/SCRAP, trên cùng covering index và cùng snapshot với Summary. Python cộng kết quả cho toàn máy và Handler được chọn từ các nhóm đã tổng hợp, không quét log hoặc đọc lại từng bản ghi. Không thêm index trùng hoặc bảng dẫn xuất mới. Search vẫn dùng worker/loading/hủy/chờ database bận hiện có.
File cần thay
domain/daily_summary.py
repositories/daily_summary_repository.py
repositories/machine_yield_repository.py
ui/pages/summary_page.py
ui/widgets/daily_summary_widget.py
ui/charts/daily_scrap_chart.py
tests/test_daily_summary.py
read.md, changelog.txt
Xác minh
12 kiểm tra Summary/Daily/UI đã đạt. Kiểm tra thêm máy có hai Handler: tổng máy khác đúng tổng Handler được chọn; PPM dùng đúng In của Handler; ô rỗng/ngày 0%, tooltip Handler, khung bảng và xóa kết quả khi bỏ chọn Handler. Đã xem ảnh render PyQt5; chưa đo tốc độ trên database sản xuất/ổ mạng Windows thực tế.
---
ARTs — cập nhật Yield Daily / Scrap PPM (02/10/2026)
Cài bản vá này
Áp dụng trên bản đã có ARTs_Summary_Layout_Update.zip. Đóng app, giải nén và chép đè các file trong gói vào thư mục chứa main.py, giữ nguyên cấu trúc thư mục. Chạy `python main.py`. Không cần import lại, đổi database hay cài thêm thư viện so với bản Summary trước.
Database mặc định vẫn là `database/arts_data.db`. Bản vá không kèm file database và không thay đổi dữ liệu import.
Bảng Yield ARTs Daily
Ở tab Summary, kéo xuống dưới khối Yield theo máy. Chọn From/To, một EQP và các Scrap Code, rồi bấm SEARCH.
Bảng gồm Date, In Qty, Pass, Fail Qty, Fail PPM, Yield và các cột mã lỗi tính theo PPM.
Bảng liệt kê tất cả mã có phát sinh trên bản ghi Fail của EQP trong khoảng ngày, giống chức năng CUM YIELD DAILY của LI. Scrap Code trên bộ lọc chỉ quyết định mã được vẽ trong biểu đồ Daily.
Tính theo File_Date; bao gồm cả ngày đầu và ngày cuối. Ngày không sản xuất vẫn có dòng: Qty = 0, Yield và Fail PPM để trống; cột mã không phát sinh để trống.
Daily theo máy áp dụng Zone, Slot và Model đang chọn, tổng hợp tất cả Handler. Daily theo Handler áp dụng thêm Handler đang chọn. Chưa chọn EQP: hiện hướng dẫn chọn EQP, xóa Daily cũ.
Bảng dùng thanh cuộn khi có nhiều ngày/mã, để không tạo widget quá cao hoặc quá rộng.
Công thức ARTs
In = SUM(Qty); Fail Qty = SUM(Fail); Pass = In − Fail Qty.
Yield = Pass / In × 100%; Fail PPM = Fail Qty / In × 1.000.000.
Mỗi mục mã trong SCRAP của bản ghi `Fail > 0` tính một lần xuất hiện, theo ARTs cũ (`get_summary_data` / `parse_scrap_codes`). Lấy mã trước dấu `:`, tách mục bằng dấu phẩy; 0 hiển thị thành 0000; bỏ mục trống và dấu `-`.
Không coi phần sau dấu `:` là số lượng. Ví dụ `1234:9,1234:8,5678:2` tính 1234 hai lần, 5678 một lần. Các mục lặp được cộng, không loại trùng mã trong một bản ghi.
PPM của mã trong ngày = số lần xuất hiện mã / tổng In của ngày × 1.000.000. Ví dụ tổng In = 1.000, mã có 4 lần → 4.000 PPM.
Chọn Scrap Code không lọc bớt sản lượng của Daily, nên không làm sai mẫu số PPM. Tổng PPM mã có thể khác Fail PPM khi log thiếu mã hoặc một sản phẩm ghi nhiều mã; không tự phân bổ số Fail vào mã.
Phần thống kê theo máy phía trên giữ cách lọc đã có ở bản trước (có lọc bản ghi theo Scrap Code); do đó khi chọn mã, số tổng ở khối trên có thể khác tổng của Daily. Daily dùng mẫu số toàn bộ sản lượng theo EQP/ngày và các bộ lọc khác như LI.
Copy chính xác vùng bôi chọn
Hàng đầu của bảng Daily là hàng tiêu đề có thể bôi chọn như dữ liệu.
Chỉ chọn dữ liệu → Ctrl+C chỉ copy dữ liệu đó.
Chọn cả hàng đầu và dữ liệu → copy cả các ô tiêu đề được chọn.
Chọn riêng ô tiêu đề → copy được riêng tên cột.
Ctrl+A → chọn toàn bộ bảng; chuột phải → Copy phần đã bôi chọn.
Ô không được chọn trong vùng rời rạc được để trống khi dán; không tự thêm tiêu đề hoặc giá trị ngoài vùng chọn.
Biểu đồ bên dưới
Kế thừa kiểu CUM YIELD DAILY của LI: cột chồng PPM từng mã, đường Yield, lưới ô, khung, ngày và chú thích. Rộng 1.550 px, cao 550 px; có cuộn ngang trên màn hình nhỏ.
Chỉ vẽ mã được chọn và có PPM > 0 trong khoảng ngày. Mã chọn nhưng không có dữ liệu không tạo cột hay legend.
Không chọn mã hoặc toàn bộ mã chọn không phát sinh: thông báo trống, xóa legend/cột cũ.
Di chuột từng đoạn cột: xem EQP, ngày, Scrap Code, PPM mã, số lần mã lỗi, In/Out/Fail và Yield. Tooltip dùng số liệu đã tổng hợp, không truy vấn lại database.
Ngày In = 0 vẽ Yield = 0% theo yêu cầu cập nhật Handler; bảng vẫn để trống ô Yield/Fail PPM.
Tổ chức và tốc độ
Daily chạy trong SummaryWorker hiện có, cùng hiệu ứng Search và hỗ trợ hủy/chờ database bận.
Machine và Daily đọc trong cùng một transaction/snapshot, không trộn dữ liệu trước/sau một lần import đồng thời.
Tái sử dụng covering index EQP/File_Date có sẵn. SQLite gom Qty/Fail và gom các chuỗi SCRAP trùng nhau theo ngày trước khi Python đếm mã; không đọc lại folder log hay tạo bảng fail_history.
Bảng dùng QAbstractTableModel; chỉ vẽ các đoạn cột có PPM dương. Tái sử dụng canvas; module biểu đồ nạp trong worker, widget được tạo ở UI thread.
Xóa cả Daily khi import cập nhật hoặc Search lỗi, tránh giữ kết quả cũ.
File mới/thay đổi
domain/daily_summary.py
repositories/daily_summary_repository.py
repositories/machine_yield_repository.py
workers/summary_worker.py
ui/pages/summary_page.py
ui/widgets/daily_summary_widget.py
ui/charts/daily_scrap_chart.py
tests/test_daily_summary.py
read.md, changelog.txt
Xác minh
Đã chạy đạt 11 kiểm tra Summary, Daily và UI: đếm mục mã lặp, bỏ mã trên bản ghi Pass, chuẩn hóa 0, mẫu số không phụ thuộc chọn mã, ngày không có dữ liệu, lọc EQP/Model, copy dữ liệu/tiêu đề riêng, tooltip và legend không có mã rỗng; kiểm tra vòng đời Search và UI cũ. Đã xem ảnh render bảng/biểu đồ PyQt5. Chưa kiểm chứng trên log sản xuất/ổ mạng Windows thực tế.
