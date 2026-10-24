# Giai đoạn 1 — Danh mục Chương 6

Hoàn thành ngày 05/09/2026; đã áp dụng vào `tutoring_center.db` local. Chức năng tự phân loại, giao diện chọn phạm vi và chặn câu trùng sẽ được triển khai ở các giai đoạn tiếp theo.

Cập nhật theo yêu cầu người dùng: **Thống kê và xác suất là một chủ đề duy nhất**. Bản `math9-c6-v4` hiện chỉ phục vụ Bài 4, giữ nguyên tám mã `9C6-4-1`…`9C6-4-8`. Các receipt catalog cũ chứa bài ngoài phạm vi được xóa bởi migration Lesson 4.

## Kết quả

| Nội dung | Đã thực hiện |
|---|---|
| Danh mục | Đúng 8 dạng Bài 4, mã `9C6-4-1`…`9C6-4-8`; phiên bản `math9-c6-v4` |
| Chủ đề | Một chủ đề chung **Thống kê và xác suất** cho Bài 4; lưu trong nút danh mục và trả qua `catalog_options()` |
| Tiêu chí | Yêu cầu nhận diện và điều kiện loại trừ cho từng dạng; bốn mức NB–TH–VD–VDC; quy ước Đúng/Sai theo mức cao nhất của các ý bắt buộc |
| Danh mục cũ | Chỉ giữ dữ liệu Bài 4; mã/bản ghi bài 1–3 bị cleanup theo phạm vi, không tự suy nghĩa câu từ tên dạng cũ |
| Chuyển dữ liệu | Công cụ chạy thử, áp dụng nguyên tử, snapshot trước/sau, phát hiện thay đổi sau chạy thử và phục hồi có điều kiện |
| Bảo toàn | 148 dạng ngoài Chương 6 và 21 bảng khác không đổi; không sửa câu hỏi, đề, đáp án hoặc bộ đếm ID |

Các ví dụ mức độ là hướng dẫn vận hành, chưa phải bộ câu mẫu có nhãn được giáo viên kiểm chứng. Bộ phân loại tương lai không được lấy độ dài câu, số lớn hoặc mã dạng làm căn cứ duy nhất; không đặt mặc định NB trong cấu hình mới. Normalizer nhập file hiện tại sẽ được thay đổi ở giai đoạn sau, không phải đã thay đổi trong giai đoạn 1.

## Các tệp chính

- `services/data/math9_curriculum.json`: danh mục được dùng khi tạo cơ sở dữ liệu mới.
- `services/data/math9_chapter6_rules.json`: một chủ đề chung, tiêu chí bốn mức độ và quy tắc cho 8 dạng Bài 4.
- `services/data/math9_chapter6_legacy_v2.json`: định nghĩa Chương 6 trước chuyển đổi.
- `services/data/math9_chapter6_transition.json`: mã cũ, tên cũ và các dạng đích có thể đối chiếu; mọi mục có trạng thái `needs_review`.
- `services/curriculum_data.py`: kiểm tra tính nhất quán mã, phiên bản, chủ đề và tiêu chí trước khi seed/migration.
- `services/curriculum_migration.py`: kiểm kê, chuyển đổi và phục hồi; dùng SQLAlchemy độc lập với khởi động ứng dụng.
- `scripts/migrate_math9_chapter6.py`: lệnh vận hành; không import `app.py`, không chạy seed dữ liệu mẫu.
- `tests/test_chapter6_migration.py`: 18 ca kiểm thử cho dữ liệu và migration.

## Quy tắc chuyển đổi

Chỉ tự cập nhật các nút khớp chính xác bản nguồn được hỗ trợ và chưa được câu hỏi tham chiếu. Phiên bản `math9-v1` chỉ được nhận nếu các định nghĩa khớp bản nguồn đã đóng gói. Dữ liệu ngoài 8 mã Bài 4 được xử lý bởi cleanup có backup, không tái seed hoặc tự gắn lại vào catalog.

Migration tìm tham chiếu từ khóa ngoại, các trường chương/bài/dạng, `source_id`, `id6_scope` và bảng `question_skill` lịch sử. Phiên import chưa hết hạn còn ở trạng thái uploaded/processing/preview cũng chặn chuyển đổi vì có thể chứa tag cũ. Cả lô sẽ không thay đổi khi có mục cần xử lý; báo cáo chỉ rõ nút, mã và ID câu liên quan. Đây là kiểm tra dữ liệu, không phải yêu cầu giáo viên duyệt một thao tác kỹ thuật trống.

Apply khóa giao dịch ghi: SQLite dùng `BEGIN IMMEDIATE`; PostgreSQL dùng khóa bảng cho các bảng danh mục, câu hỏi, bộ đếm, phiên nhập và ánh xạ cũ đang tồn tại. Không thay nội dung/ID/mức độ của câu cũ. Bộ đếm được giữ nguyên, kể cả phạm vi từng có câu đã xóa.

Snapshot nằm trong bảng `curriculum_catalog_migration`, cùng giao dịch với dữ liệu danh mục. Chạy lại apply không tạo receipt hoặc cập nhật lần hai. Seed lúc khởi động giữ nguyên Chương 6 cũ, kể cả chương chưa đủ nút; không tự gắn các tag cũ mồ côi vào định nghĩa mới.

Rollback chỉ phục hồi khi danh mục/bộ đếm chưa đổi từ lúc apply và không có tham chiếu hoặc phiên nhập mới cần bảo vệ. Hai cột chủ đề vẫn tồn tại để tương thích model, nhưng giá trị cũ được khôi phục. Receipt được đánh dấu `rolled_back`; chạy lại rollback không đổi thêm dữ liệu. Muốn áp dụng lại một bản đã rollback cần phiên migration mới để giữ lịch sử.

## Lệnh vận hành

Chạy tại thư mục dự án. Thay đường dẫn cơ sở dữ liệu/báo cáo theo môi trường; công cụ không tự tạo tệp cơ sở dữ liệu đích.

```sh
python3 scripts/migrate_math9_chapter6.py --database tutoring_center.db --dry-run --report /tmp/chapter6-plan.json
python3 scripts/migrate_math9_chapter6.py --database tutoring_center.db --apply --report /tmp/chapter6-applied.json
```

Mặc định là dry-run nếu không truyền hành động. Có thể truyền `--expected-fingerprint` bằng giá trị `plan_fingerprint` trong báo cáo chạy thử để từ chối apply khi dữ liệu thay đổi. Mã thoát 0 là thành công hoặc đã cập nhật; mã 2 là có mục chặn, chi tiết nằm trong `blockers`.

Phục hồi một migration còn đủ điều kiện:

```sh
python3 scripts/migrate_math9_chapter6.py --database tutoring_center.db --rollback --report /tmp/chapter6-rollback.json
```

Với PostgreSQL, dùng `--database-url-env DATABASE_URL` thay `--database ...` để lấy URL từ biến môi trường đã cấu hình. Không đưa mật khẩu vào báo cáo hoặc câu lệnh. Nhánh khóa/giao dịch PostgreSQL chưa được kiểm thử tích hợp trong môi trường local này.

## Bằng chứng thực hiện local

Báo cáo vận hành hiện tại nằm trong `docs/LESSON4_SCOPE_CLEANUP.md`; các report catalog cũ chứa mã bài 1–3 đã được đưa khỏi tree hoạt động và lưu bản phục hồi trong `uploads/backups/legacy-catalog-reports-20260909/`.

Kiểm thử đã chạy trên cơ sở dữ liệu riêng:

```sh
DATABASE_URL='sqlite:///:memory:' POSTGRES_URL='' python3 -m unittest discover -s tests -q
node tests/test_id6_picker.js
```

Kết quả: **131 kiểm thử Python đạt**, gồm 18 ca mới cho Chương 6; kiểm thử JavaScript của bộ chọn ID6 đạt. Có kiểm tra lỗi giữa giao dịch, schema cũ chưa có chủ đề, tham chiếu qua tag cũ, seed dữ liệu, bảo toàn chỉnh sửa, snapshot, rollback và dữ liệu đã đổi sau chạy thử. Các cảnh báo deprecated của thư viện/model hiện có không làm thất bại kiểm thử.
