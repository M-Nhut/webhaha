# MVP cá nhân hóa và theo dõi lỗi

Tài liệu này mô tả lát dọc đã triển khai cho mục tiêu luận văn: lưu bằng
chứng câu hỏi/câu trả lời bất biến, cập nhật năng lực từ bài đã chấm, sinh bài
luyện theo kỹ năng yếu và cung cấp báo cáo trong ứng dụng cho giáo viên.

## Luồng dữ liệu

1. Giáo viên tạo đề từ ngân hàng hoặc nhập thủ công. `ExamQuestion` giữ nội
   dung, đáp án và metadata nguồn tại thời điểm đề được tạo. `BankQuestion` có
   `content_revision` và `content_hash`; sửa nội dung hoặc đáp án làm revision
   tăng, nhưng không sửa lại đề đã phát hành.
2. Khi học sinh nộp bài, `SubmissionAnswer` giữ payload thực tế, trạng thái và
   hash. Ba trạng thái có ý nghĩa khác nhau: `unanswered`, `pending_review` và
   `graded/answered`. Câu bỏ trống không phải là câu sai.
3. Chỉ `ExamSubmission.status=graded` hoặc `is_graded=True` mới gọi
   `AdaptiveEngine.update_performance`. `LearningHistory` là một fact duy nhất
   cho cặp submission/item; regrade cập nhật fact và `grading_revision`, không
   nhân bản fact.
4. `ErrorObservation` chỉ được tạo từ câu đã trả lời, đã chấm và sai. Nó dẫn
   chiếu đến `SubmissionAnswer`/`ExamQuestion` bằng `evidence_ref`; không copy
   actual answer vào các bảng aggregate. `StudentErrorProfile` chỉ là số lượng
   quan sát, không phải nhãn chẩn đoán chắc chắn.
5. Selector vẫn dùng luật deterministic và ràng buộc của giáo viên, nhưng có
   boost giới hạn cho `curriculum_code` có error evidence. AI không được sửa
   điểm, key đáp án hay quyết định phát hành đề.

## Diagnostic đầu vào chung

Đặt `Exam.assessment_purpose=initial_diagnostic` (đã có lựa chọn trên form) sẽ
tạo `DiagnosticAssignment` cho mọi enrollment active của course. Assignment
dùng hash của cùng ordered frozen item set; thao tác tạo lại là idempotent và
không random hóa theo từng học sinh. `Exam.diagnostic_coverage` lưu số item
theo skill/difficulty/type và số skill unknown để giáo viên kiểm tra coverage.
Câu hỏi thiếu coverage ID6 vẫn được ghi nhận là metadata unknown, không tự bịa
kỹ năng.

## AI và báo cáo giáo viên

Nút “Phân tích Chương 6 bằng AI” là hành động explicit của giáo viên. Không có
AI URL thì deterministic fallback vẫn lưu `AIAnalysisRun` và
`TeacherLearningReport`; không có email hay job gửi dữ liệu ra ngoài. Khi API
được cấu hình, packet gửi đi chỉ được tạo cho lần chạy explicit đó và bao gồm
evidence refs/actual answer cần thiết.

Schema AI v2 phải dẫn chiếu đúng `evidence_ref` đã có. Ref giả bị reject. Mục
`observed_errors` chỉ được diễn giải là quan sát trên câu cụ thể. Mọi
`future_error_risks` luôn mang `validation=not_validated`; đây là rủi ro cần
theo dõi, chưa phải dự đoán đã kiểm chứng hay nhãn “misconception” chắc chắn.
Giáo viên xem được từng ref, có thể đánh dấu observed/reviewed/dismissed, và
duyệt/sửa report trong app. Quyền xem được kiểm tra qua enrollment và teacher
ownership; không có quyền thì trả 403.

### Báo cáo lớp Bài 4

Màn hình lớp (`/courses/<course_id>`) tự tải báo cáo cố định cho `9C6-4` —
“Phép thử ngẫu nhiên và không gian mẫu. Xác suất của biến cố” — và không có
selector chương/bài hay yêu cầu đề đích. Hai endpoint JSON là
`GET /courses/<course_id>/lesson4-report` và
`POST /courses/<course_id>/lesson4-report/generate` (nút “Làm mới báo cáo”
gửi `force=1`). Giáo viên chỉ được xem lớp mình phụ trách; admin được xem mọi
lớp.

Packet gửi provider chỉ có token ổn định theo học sinh, không có tên, mã học
sinh hay điện thoại. Lịch sử mặc định là strict in-class: chỉ enrollment đang
active, submission đã finalized/graded, câu đã trả lời và metadata đúng mã
`9C6-4-*` của course đó. Câu bỏ trống/chưa chấm bị loại. Cả câu đúng
(tiến bộ/phục hồi) và câu sai (lỗi quan sát kèm câu hỏi, actual/expected answer
và `evidence_ref`) được lưu trong snapshot.

`ClassAIAnalysisRun` lưu từng snapshot theo roster + evidence fingerprint,
provider/model/prompt version và source cutoff. Nút refresh tạo phiên bản mới;
request lặp trên dữ liệu không đổi dùng lại cache. Provider lỗi/không cấu hình
hoặc trả ref không hợp lệ sẽ hiển thị rõ “phân tích dự phòng từ dữ liệu đã
chấm”; không gọi đó là AI. `next_risk_hypotheses` luôn
`validation=not_validated`, không phải xác suất hiệu chuẩn hay kết luận
misconception. Roster vẫn hiển thị đủ học sinh và đánh dấu “Chưa có dữ liệu”.

Payload lớn được chia batch provider (mặc định 40 học sinh, tối đa 100 event/
học sinh mỗi batch); coverage ghi rõ số event bị cắt trong batch. Snapshot quan
sát server vẫn giữ toàn bộ event đã chấm. Không có job nền unmanaged: request
ghi trạng thái `processing` bền vững trước khi gọi provider, dùng khóa DB để
coalesce request đồng thời, timeout xử lý cũ được giải phóng để thử lại.

## Migration và tương thích

Schema additions nằm trong `models.py` và được `migrate_existing_sqlite_schema`
thêm bằng `add_column_if_missing`. `db.create_all()` chỉ tạo bảng mới khi
khởi động; không có `drop_all` trong production startup. Backfill lịch sử chỉ
đụng submission đã finalized; record cũ thiếu metadata giữ trạng thái unknown,
không tự tạo snapshot quá khứ. Không chạy migration/test suite trên database
người dùng hiện có trong quá trình phát triển.

## Test reproducibility

Các test MVP dùng SQLite in-memory và stub `config.load_local_environment` trước
khi import `app`; không gọi AI/email bên ngoài. Chạy toàn bộ suite:

```bash
DATABASE_URL='sqlite:///:memory:' POSTGRES_URL='' python3 -c 'import config; config.load_local_environment=lambda *a,**k:None; import unittest; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover("tests", pattern="test_*.py")); raise SystemExit(not r.wasSuccessful())'
```

Các regression chính ở `tests/test_personalization_mvp.py` bao gồm D/T/S answer
evidence, exclusion pending/unanswered, regrade idempotency/revision,
diagnostic common items, weak-skill selection, fabricated-AI-evidence rejection,
teacher ownership/report fallback và HTTP take/grade flow.

Class report có test riêng trong `tests/test_class_lesson4_report.py` cho strict
course scope, full roster/no-data, correct + wrong evidence, invalid AI refs,
provider fallback, cache invalidation bởi answer/regrade/roster và ownership.

## Giới hạn cần giữ trong luận văn

MVP chưa chứng minh predictive validity, calibration hay accuracy của mô hình
tương lai; chưa có training/OCR. Đánh giá nghiên cứu phải dùng split theo học
sinh/thời gian và tách riêng metric cá nhân hóa khỏi metric dự đoán. Với chỉ
một câu sai, UI chỉ được nói “quan sát lỗi trên câu này”; cần thêm dữ liệu dọc
và teacher review trước khi dùng ngôn ngữ “misconception ổn định”.
