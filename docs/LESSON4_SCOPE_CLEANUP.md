# Phạm vi dữ liệu Math 9 sau cleanup

Sản phẩm hiện giữ duy nhất Chương 6, Bài 4 **Phép thử ngẫu nhiên và không gian mẫu. Xác suất của biến cố**, chủ đề **Thống kê và xác suất**, với tám mã `9C6-4-1` đến `9C6-4-8`. Hạ tầng người dùng, khóa học, đăng nhập, báo cáo giáo viên và cá nhân hóa vẫn được giữ.

## Lệnh vận hành

Chạy dry-run trước:

```bash
python3 scripts/cleanup_math9_chapter6_lesson4.py tutoring_center.db --dry-run
```

Sau khi kiểm tra `plan_fingerprint`, chạy apply:

```bash
python3 scripts/cleanup_math9_chapter6_lesson4.py tutoring_center.db \
  --apply --expected-fingerprint <fingerprint>
```

`--apply` tạo backup SQLite nhất quán bằng `Connection.backup()` trong `uploads/backups/` trước khi mở transaction. Lệnh có thể chạy lại an toàn; lần sau chỉ còn các dòng unknown cần xử lý hoặc báo kế hoạch rỗng. Kiểm tra cuối cùng gồm `PRAGMA integrity_check`.

## Chính sách phạm vi

- Node, bộ đếm ID, câu hỏi, phiên import và snapshot catalog ngoài tám mã được xóa.
- Đề có bất kỳ câu ngoài phạm vi nào bị xóa toàn bộ; như vậy không giữ một bài làm có mẫu số/đáp án không còn đầy đủ. Câu hỏi gốc Bài 4 trong ngân hàng vẫn được giữ.
- Bài làm, đáp án nộp, lịch sử học tập, quan sát lỗi và aggregate/AI/report stale đi theo đề hoặc mã ngoài phạm vi bị xóa; projection còn bằng chứng Bài 4 được dọn orphan và cập nhật lại.
- Bản ghi không có provenance rõ ràng không bị đoán là Bài 4. Dry-run liệt kê ở `unknown`; cần bổ sung metadata hoặc quyết định vận hành riêng trước khi xóa.
- Không xóa `user`, `course`, enrollment, thông tin xác thực hay các bảng hạ tầng không thuộc phạm vi ID/curriculum. Các bảng vận hành lớp học cũ (nếu còn trong database) được giữ nguyên để xử lý ở Pha 5.

## Kết quả áp dụng local

Ngày 09/09/2026, database target là `tutoring_center.db` local. Backup SQLite nhất quán trước apply: `uploads/backups/math9-c6-lesson4-before-20260909T022441433393Z.db` (`PRAGMA integrity_check = ok`). Đã xóa 164 node curriculum ngoài 8 node Bài 4, 24 phiên import cũ/ngoài phạm vi và 2 snapshot catalog cũ; không có bank question, đề, bài làm, lịch sử học tập, aggregate hoặc AI report cần xóa. Không có file nguồn import tồn tại để sao lưu. Còn lại đúng 8 node mã `9C6-4-1`…`9C6-4-8`, 7 user và 2 course; kiểm tra sau apply `ok`.

Dry-run lặp lại sau apply có toàn bộ delete count bằng 0, `unknown_total = 0`, fingerprint `36181898a549eb0978004168dcd4f1217ef4699d85a6e50c716755b9d6044eef`, chứng minh tính idempotent. Các report catalog cũ chứa Bài 1–3 đã được backup tại `uploads/backups/legacy-catalog-reports-20260909/` rồi gỡ khỏi tree hoạt động.
