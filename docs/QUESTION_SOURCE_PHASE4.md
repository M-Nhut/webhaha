# Phase 4 — Source resolver và snapshot manifest

## Mục tiêu

Mọi đề mới gắn với lớp đều phải lấy quyền sử dụng câu hỏi từ giáo viên đang
được gán cho `Course`. Học sinh và quản trị viên không được dùng làm principal
để mở rộng quyền đối với câu overlay riêng của giáo viên.

## Source resolver

`services/source_resolver.py` cung cấp các điểm dùng chung:

- `resolve_class_banks(course, bank_ids)`: kiểm tra lớp đang hoạt động, giáo
  viên hiện tại, môn/khối và quyền dùng toàn bộ ngân hàng (all-or-nothing).
- `resolve_class_questions(...)`: lọc từng câu theo chính sách câu hỏi hiện
  tại; câu riêng của giáo viên khác bị loại.
- `validate_exam_source(exam, require_live=True)`: kiểm tra nguồn hiện tại
  cho các thao tác mở bài, phát hành và Continue.

Selector `adaptive_engine.py` vẫn giữ kiểm tra câu hỏi ở lớp cuối cùng như một
defense-in-depth; route không được bỏ qua source resolver.

## Snapshot manifest

Đề mới lưu manifest JSON vào `Exam.source_manifest`. Manifest gồm:

- phiên bản manifest, `course_id`, giáo viên tại thời điểm sinh;
- toàn bộ `bank_ids` của session (không chỉ ngân hàng đầu tiên);
- với từng câu: `ExamQuestion`, `BankQuestion`, bank, scope dùng chung/riêng,
  owner riêng, ID6 và content revision/hash.

Manifest không thay thế nội dung/đáp án đã đóng băng. Đề lịch sử không có
manifest vẫn được đọc theo chế độ tương thích.

Manifest mới dùng phiên bản `phase4-source-manifest-v2` và có thêm hash của
toàn bộ snapshot câu/đáp án đã đóng băng. Manifest JSON lỗi, sai schema hoặc
sai mapping không được coi là đề legacy; thao tác live phải fail-closed.
Manifest `v1` chỉ là cầu tương thích có chủ đích và không có hash snapshot
đầy đủ.

## Quy tắc runtime

- `take`, resume, phát hành và Continue yêu cầu nguồn hiện tại còn hợp lệ.
- Trang kết quả lịch sử vẫn được xem khi nguồn cũ không còn được phép; chỉ
  nút Continue bị ẩn và nút kết thúc session vẫn giữ được.
- Đổi giáo viên lớp không sửa đề, câu hỏi, submission hoặc kết quả cũ.
  Đề mới chỉ dùng shared và overlay của giáo viên hiện tại.
