# Kết quả kiểm thử — ARTs Import v1.0

Ngày thực hiện: 02/10/2026. Dữ liệu: log giả lập theo vị trí trường của parser ARTs; chưa có log sản xuất người dùng.

## Môi trường

- Linux, Python 3.12.14.
- SQLite 3.53.1; pandas 2.2.3.
- PyQt5 5.15.11, Qt 5.15.14; giao diện chạy offscreen.
- Filesystem local. Không có Windows/SMB/NAS của người dùng.

## Kiểm thử tự động

Lệnh `python -m unittest discover -s tests -v`: **18 tests PASS**.

1. Parser mới khớp kết quả parser ARTs gốc, bao gồm dòng lỗi và thời gian không hợp lệ.
2. Tìm file trong folder máy/tháng/lồng sâu; lấy cả From và To; nhận .TXT; loại ngày ngoài phạm vi và tên không đúng định dạng.
3. Import lại xóa toàn bộ ngày ở tất cả máy, giữ ngày khác, chạy lặp không nhân đôi.
4. Ngày không có file giữ nguyên dữ liệu.
5. Ngày có file nhưng không có dòng hợp lệ giữ nguyên dữ liệu.
6. Không có file: không tạo database.
7. Toàn bộ staging rỗng: không xóa dữ liệu cũ.
8. Hủy sau DELETE: rollback, import tiếp được.
9. Lỗi SQL khi INSERT sau DELETE: rollback cả dữ liệu và revision.
10. Khóa import đang hoạt động chặn phiên khác; giải phóng xong import được.
11. Lease hết hạn cho phép phiên mới; chủ cũ không thể xóa khóa của chủ mới.
12. File không đọc được: không xóa dữ liệu cũ.
13. File nguồn đổi sau snapshot: vẫn import nội dung đã đọc.
14. Vượt ranh giới 5.000 dòng: nhập đủ 5.001 dòng, schema đúng; Qty/Fail/Model/Handler/EQP/Datetime đúng mẫu.
15. Connection đọc khác thấy dữ liệu cũ trước commit, dữ liệu mới sau commit trên filesystem local.
16. Từ chối database ARTs cũ có các bảng phụ thuộc.
17. From > To bị từ chối.
18. Luồng UI: chọn ngày/folder qua dialog được mô phỏng, worker thật import database; nút Import khóa trong lúc chạy rồi mở lại; nhận kết quả thành công.

Đã xem ảnh chụp cửa sổ chính và dialog From–To bằng Qt offscreen để kiểm tra chữ/nút không bị che khuất.

## Kiểm thử khối lượng

Lệnh `python -m tests.benchmark_import --rows 1000000`:

| Chỉ tiêu | Kết quả |
|---|---:|
| File TXT | 50 |
| Tổng dòng hợp lệ | 1.000.000 |
| Import lần đầu | 16,146 giây |
| Import lại cùng ngày | 19,865 giây |
| Dòng bị thay khi import lại | 1.000.000 |
| Số dòng cuối cùng | 1.000.000 |
| SQLite integrity_check | ok |
| Kích thước database sau kiểm thử | 122.220.544 byte |

Thời gian gồm tìm file, staging, parse, khóa, ghi/commit; không gồm tạo dữ liệu benchmark. Dữ liệu được lặp theo mẫu đơn giản trên ổ local; không phải dự báo tốc độ của 50 file thật hay ổ mạng sản xuất. Không đo mức RAM đỉnh.

## Phần cần kiểm tra ở môi trường người dùng

- Windows/Python đang sử dụng và bản EXE build trên Windows.
- Log thật, kích thước từng file, ký tự/encoding và cấu trúc folder máy thực tế.
- Tốc độ SMB, quyền tạo journal, reader/writer trên nhiều máy.
- Mất mạng/reconnect trong lúc commit và đóng tiến trình bất thường.
- Lease và heartbeat dưới tải dài hơn 15 phút.

Không gọi các phần chưa kiểm tra này là đã xác minh. Các tests dùng cùng máy chỉ xác minh logic connection/transaction, không chứng minh cơ chế khóa của server chia sẻ file.
