# Refactoring Pha 2 — bỏ bài kiểm tra truyền thống

## Phạm vi đã hoàn thành

- Xóa route và authoring service của bài kiểm tra truyền thống: list, create,
  edit, delete, take, result kiểu summative và `grade_submission`.
- Xóa các template authoring/chấm tay (`exam_list.html`, `exam_form.html`,
  `grade_submission.html`) và JavaScript authoring tương ứng.
- Giữ `Exam`, `ExamQuestion`, `ExamAnswer`, `ExamSubmission` và các bảng dữ
  liệu dùng chung; không migration, không xóa dữ liệu hoặc file upload thật.
- Giữ runtime canonical `/practice/<id>/take` và
  `/practice/<id>/result` cho tự luyện 22 câu và initial diagnostic.
- Tách authoring diagnostic sang `routes/diagnostics.py` với
  `/diagnostics` và `/diagnostics/new`. Diagnostic chỉ lấy một bộ câu hỏi
  8 dạng kiến thức Bài 4 đã `teacher_confirmed`, node curriculum còn active, đáp án hợp
  lệ và không bị loại; bộ câu hỏi được đóng băng một lần rồi giao cho cohort
  active bằng `assign_diagnostic_cohort`.
- Initial diagnostic không đi qua manual authoring/chấm tay. Câu trả lời ngắn
  phải có rule `numeric` hoặc `text` và đáp án đúng hợp lệ; runtime tự chấm,
  kể cả input numeric sai được ghi nhận là câu sai chứ không thành
  `pending_review`. Diagnostic legacy thiếu rule bị chặn trước khi ghi bài,
  không tự gán điểm.
- Tách draft/publish practice fixed sang endpoint
  `/teacher/practice/drafts/<id>` (`teacher_practice_draft`) để sinh tự luyện
  22 câu không còn phụ thuộc route edit exam.
- Dashboard, menu và teacher practice workspace chỉ còn nhãn theo dõi học tập,
  diagnostic và kết quả; không còn nút chấm tay. Báo cáo năng lực, lỗi quan
  sát và teacher review report vẫn giữ nguyên.

## Giới hạn có chủ ý

`pending_review` và upload của các bài tự luyện cũ không bị xóa trong Pha 2;
đó là phạm vi Pha 3. Chúng không được dùng để mở lại endpoint chấm tay hoặc
authoring bài kiểm tra truyền thống.

## Kiểm tra

Đã chạy kiểm tra cú pháp/static bằng `python3 -m py_compile` trên các module
route và bootstrap đã chỉnh sửa. Không chạy test suite, không chạy app hoặc
database thật theo yêu cầu.
