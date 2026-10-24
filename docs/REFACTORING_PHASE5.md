# Pha 5 — dữ liệu cục bộ đã dọn

Thực hiện ngày 2026-09-13 trên `tutoring_center.db` của workspace.

- Sao lưu SQLite: `backups/phase5-eRGXgZLX/before.sqlite3`.
- Đã xoá bảng `schedule` (3 bản ghi) và `attendance` (0 bản ghi) trong một giao dịch.
- Không có đề/bài nộp trong dữ liệu hiện tại; không cần chuyển/xoá cây dữ liệu đề truyền thống.
- Không có file bài nộp cần dọn trong `static/uploads/submissions`.
- File phụ macOS `.DS_Store` được chuyển vào backup; thư mục bài nộp rỗng đã được bỏ.
- Đối chiếu toàn bộ hàng của 34 bảng còn lại với backup: không thay đổi.
- Giữ nguyên 185 câu hỏi, tài khoản, lớp, khoá AI và các bảng hồ sơ học tập.
- Kiểm tra toàn vẹn và khoá ngoại SQLite: đạt.

Các model `Exam`, câu hỏi và bài nộp vẫn phục vụ tự luyện/đánh giá đầu vào.
Các cột cấu hình đang dùng không bị đổi tên hoặc xoá. Không tính lại điểm/hồ sơ
cũ; dữ liệu hiện tại không có bài cần xử lý trường hợp này. Các bảng của tính
năng bị bỏ từ những đợt khác nằm ngoài phạm vi pha này.

## Công cụ chạy sau

Mặc định chỉ đọc và lập kế hoạch:

```sh
python3 scripts/cleanup_phase5.py --database tutoring_center.db
```

Áp dụng với fingerprint chính xác nhận được sau khi xem kế hoạch:

```sh
python3 scripts/cleanup_phase5.py --database tutoring_center.db --apply --expect <fingerprint>
```

Công cụ chỉ xoá hai tên bảng chính xác, tự sao lưu, kiểm tra toàn vẹn, khoá
giao dịch, đối chiếu dữ liệu còn lại và rollback khi phát hiện thay đổi.
Chạy lại dữ liệu đã dọn không xoá thêm gì. Không import Flask, seed, đọc file
môi trường hoặc gọi AI. Chỉ hỗ trợ SQLite, không tự truy cập DB bên ngoài.

Nếu có đề truyền thống/không xác định, thư mục bài nộp không rỗng, schema lạ,
trigger/view hoặc quan hệ ngoài phạm vi, công cụ dừng để lập migration riêng.
Không suy đoán từ tên đề và không xoá file ngân hàng câu hỏi.

## Khôi phục

Dừng web và mọi tiến trình ghi dữ liệu, sao lưu trạng thái hiện tại trước.
Dùng SQLite restore từ `before.sqlite3` nêu trên; kiểm tra `PRAGMA integrity_check`
và `PRAGMA foreign_key_check` trước khi mở web. Restore toàn bộ sẽ đưa dữ liệu
về thời điểm sao lưu, nên không ghi đè dữ liệu mới chưa có kế hoạch hợp nhất.

Không chạy bộ kiểm thử ứng dụng. Kiểm tra thực tế gồm dữ liệu đích, bản sao lưu,
tính toàn vẹn và bảo toàn toàn bộ các bảng còn lại.
Dry-run công cụ sau khi dọn: không còn bảng cần xoá và không có điều kiện chặn.
