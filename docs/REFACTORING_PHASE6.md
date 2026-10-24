# Refactoring Phase 6 — final consistency cleanup

Hoàn thành ngày 2026-09-13. Đây là đợt dọn cuối sau các pha bỏ đề truyền
thống, chấm thủ công, lịch/điểm danh và dữ liệu SQLite tương ứng.

## Phạm vi đã xử lý

- Xóa hai template mồ côi của luồng đã bỏ (`tuition.html` và
  `teaching_records.html`) cùng các liên kết `url_for` tới endpoint không còn
  tồn tại.
- Xóa helper `services/retired_features.py`, vốn không được ứng dụng đăng ký
  hoặc gọi; không xóa model `Exam`, `ExamSubmission` hay bất kỳ bảng dữ liệu
  học tập nào.
- Gỡ import Python không dùng còn sót từ các route/feature cũ và gỡ các CSS
  selector chỉ dành cho học phí, bảng lương hoặc điểm danh. Các kiểu câu hỏi,
  ảnh/công thức, import ngân hàng và runtime tự luyện vẫn giữ nguyên.
- Bỏ các test chỉ kiểm tra route đã bị xóa; giữ test policy/parser/import,
  practice 22 câu, diagnostic, bằng chứng mastery/error và quyền sở hữu khóa
  AI. Kiểm tra policy import không còn gọi endpoint kiểm tra ngân hàng cũ.
- Đánh dấu các báo cáo refactor cũ là tài liệu lịch sử/superseded thay vì xóa;
  bổ sung checklist nghiệm thu thủ công và giới hạn còn lại tại tài liệu này.

Không đổi `.env`/secret, không gọi ứng dụng, database thật hoặc AI provider,
không migrate/đổi tên model dùng chung và không sửa dữ liệu/backup Phase 5.

## Kiểm tra tĩnh đã thực hiện

- Biên dịch cú pháp Python bằng `compileall` cho module ứng dụng, route,
  service và model.
- Đối chiếu tĩnh endpoint với mọi `url_for` literal và template được gọi bởi
  `render_template`; không còn endpoint mồ côi từ template hoạt động.
- Đối chiếu tĩnh đường dẫn CSS/JavaScript được template dùng; các module còn
  lại đều có nơi sử dụng.

Không chạy test suite, không khởi động Flask và không thực hiện kiểm tra
trình duyệt trong pha này theo giới hạn vận hành đã chốt.

## Checklist nghiệm thu thủ công

Bạn khởi động lại web rồi thực hiện tối thiểu:

1. Đăng nhập lần lượt tài khoản admin, giáo viên và học sinh; mở dashboard,
   khóa học, hồ sơ và các trang được cấp quyền.
2. Giáo viên mở ngân hàng câu hỏi, import một file mẫu, xem preview/phạm vi,
   phân loại ID6, tạo và giao một đánh giá đầu vào; không thấy liên kết học
   phí, lịch, điểm danh, payroll hay chấm tay.
3. Học sinh mở diagnostic hoặc bài practice, nộp đủ cấu trúc 12 câu trắc
   nghiệm + 4 câu Đúng/Sai + 6 câu trả lời ngắn; xác nhận điểm Đúng/Sai theo
   bảng điểm từng ý (0 / 0,1 / 0,25 / 0,5 / 1 theo số ý đúng) và trang tiến bộ dùng các URL canonical
   `/practice/<id>/take` và `/practice/<id>/result`. Gửi thử multipart có file
   bài làm phải bị từ chối trước khi tạo submission.
4. Từ kết quả practice, chọn lần lượt **Tiếp tục** và **Kết thúc**; kiểm tra
   mỗi quyết định chỉ tạo đúng một trạng thái/đề tiếp theo và không mở lại
   phiên đã kết thúc.
5. Giáo viên mở hồ sơ practice của học sinh, xem evidence/report; xác nhận
   observed error và future risk vẫn được hiển thị tách biệt. Thử xem hồ sơ
   học sinh khác lớp và dùng nhóm khóa AI của giáo viên khác để xác nhận đều
   bị chặn; khóa AI của giáo viên chỉ hiển thị chủ sở hữu đúng.
6. Kiểm tra trực tiếp `/exams/new`, `/exams/<id>/take`, `/attendance`,
   `/schedules` và `/tuition` không phải là entry point được hỗ trợ.

## Giới hạn còn lại

- Các tên `Exam*`/`Submission*` và một số script/tài liệu lịch sử vẫn tồn tại
  có chủ ý vì chúng lưu bằng chứng frozen practice/initial diagnostic và phục
  vụ đối soát; không được hiểu là khôi phục đề truyền thống.
- Bản cleanup Phase 5 và backup `backups/phase5-eRGXgZLX` được giữ nguyên để
  phục hồi có kiểm soát; Phase 6 không đọc hoặc thay đổi backup.
- Chưa có browser end-to-end hoặc kiểm tra provider AI thật. AI chỉ là lớp báo
  cáo được giáo viên xem xét; ảnh hưởng vào bộ sinh đề vẫn là 0, và nguy cơ
  tương lai không được nâng thành lỗi quan sát.
- Các migration/startup tương thích cũ vẫn có thể tồn tại cho dữ liệu nâng cấp;
  việc loại bỏ chúng cần một pha migration riêng, ngoài phạm vi cleanup này.
