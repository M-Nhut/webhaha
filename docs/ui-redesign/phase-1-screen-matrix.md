# Phase 1 — Ma trận toàn bộ template

Ngày kiểm kê: 13/10/2026. Phạm vi là mã nguồn hiện có; chưa xác minh trực quan bằng trình duyệt. Mỗi dòng là một file template, không phải một chức năng độc lập. Một file có thể có nhiều URL, vai trò và trạng thái.

Đọc cùng [báo cáo tổng](README.md), [ngân hàng/nhập câu hỏi](phase-1-bank-import.md), [kiểm tra/học tập](phase-1-assessments-learning.md), [quản lý/báo cáo](phase-1-management-reports.md). Chi tiết assets, ID, data attributes, form names, Alpine directives và route nằm trong [inventory JSON](phase-1-inventory.json).

## 1. Các màn hình cấp trang — 33 file

Có 32 file tìm thấy render từ route hiện tại và 1 template cũ cần xác minh để dọn. Tất cả 32 màn hình hoạt động đều nằm trong phạm vi thiết kế lại, kể cả trang đang dùng theme trắng trong `main.css`.

| File | Chức năng/biến thể chính | Endpoint render | Phase | style trực tiếp / khối CSS / JS inline |
|---|---|---|---|---|
| [ai_reports.html](../../templates/ai_reports.html) | Báo cáo AI: tổng quan/lớp/cá nhân | `ai_reports_class`, `ai_reports_individual`; `ai_reports` là alias redirect dùng chung handler | 8 | 0 / 0 / 1 |
| [assessment_from_bank.html](../../templates/assessment_from_bank.html) | Tạo đề từ ngân hàng | `assessment_from_bank` | 5 | 2 / 0 / 1 |
| [assessment_import.html](../../templates/assessment_import.html) | Biên soạn và duyệt đề nhập | `assessment_import` | 5 | 1 / 0 / 0 |
| [assessment_list.html](../../templates/assessment_list.html) | Danh sách đề kiểm tra | `assessment_list` | 6 | 0 / 0 / 0 |
| [assessment_matrix.html](../../templates/assessment_matrix.html) | Ma trận đề và xuất Excel | `assessment_matrix` | 6 | 0 / 0 / 0 |
| [classification_evaluation.html](../../templates/classification_evaluation.html) | Đánh giá phân loại ngân hàng | `classification_evaluation_page` | 4 | 5 / 0 / 0 |
| [course_detail.html](../../templates/course_detail.html) | Chi tiết lớp và ghi danh | `course_detail` | 8 | 42 / 0 / 0 |
| [course_form.html](../../templates/course_form.html) | Tạo/sửa lớp học | `edit_course`, `add_course` | 8 | 14 / 0 / 1 |
| [courses.html](../../templates/courses.html) | Danh sách lớp học | `courses` | 8 | 10 / 0 / 0 |
| [curriculum_catalog.html](../../templates/curriculum_catalog.html) | Danh mục kiến thức | `curriculum_catalog` | 4 | 21 / 0 / 0 |
| [diagnostic_form.html](../../templates/diagnostic_form.html) | Tạo đánh giá đầu vào | `create_diagnostic` | 7 | 0 / 0 / 1 |
| [diagnostic_list.html](../../templates/diagnostic_list.html) | Quản lý đánh giá đầu vào | `diagnostic_list` | 7 | 8 / 0 / 0 |
| [edit_user.html](../../templates/edit_user.html) | Sửa tài khoản người dùng | `edit_user` | 8 | 6 / 0 / 0 |
| [exam_result.html](../../templates/exam_result.html) | Kết quả cá nhân/danh sách bài nộp | `assessment_result`, `practice_result` | 6 + 7 | 53 / 0 / 1 |
| [exam_take.html](../../templates/exam_take.html) | Làm bài kiểm tra/đầu vào/tự luyện | `assessment_take`, `practice_take` | 6 + 7 | 16 / 0 / 0 |
| [index.html](../../templates/index.html) | Tổng quan theo vai trò | `index` | 8 | 0 / 0 / 0 |
| [login.html](../../templates/login.html) | Đăng nhập | `login` | 3 | 0 / 0 / 0 |
| [manage_users.html](../../templates/manage_users.html) | Quản lý học sinh/giáo viên | `manage_users` | 8 | 16 / 0 / 0 |
| [my_students.html](../../templates/my_students.html) | Học sinh của giáo viên | `my_students` | 8 | 7 / 0 / 0 |
| [practice_draft.html](../../templates/practice_draft.html) | Duyệt bản nháp luyện tập | `teacher_practice_draft` | 7 | 0 / 0 / 0 |
| [practice_home.html](../../templates/practice_home.html) | Không gian tự luyện của học sinh | `practice_home` | 7 | 0 / 0 / 0 |
| [practice_progress.html](../../templates/practice_progress.html) | Tiến độ học tập cá nhân | `practice_progress` | 7 | 42 / 0 / 2 |
| [profile.html](../../templates/profile.html) | Hồ sơ và đổi mật khẩu | `profile` | 3 | 17 / 0 / 1 |
| [question_bank_classification.html](../../templates/question_bank_classification.html) | Duyệt và cập nhật phân loại | `question_bank_classification` | 4 | 37 / 0 / 2 |
| [question_bank_detail.html](../../templates/question_bank_detail.html) | Chi tiết ngân hàng, câu hỏi và overlay | `question_bank_detail` | 4 | 137 / 0 / 1 |
| [question_bank_form.html](../../templates/question_bank_form.html) | Tạo/sửa ngân hàng | `edit_question_bank`, `create_question_bank` | 4 | 3 / 0 / 0 |
| [question_bank_import.html](../../templates/question_bank_import.html) | Nhập .tex, duyệt câu, trùng và xác nhận | `import_questions_page` | 5 | 138 / 1 / 1 |
| [question_banks.html](../../templates/question_banks.html) | Danh sách ngân hàng | `question_bank_list` | 4 | 20 / 0 / 0 |
| [register.html](../../templates/register.html) | Đăng ký | `register` | 3 | 21 / 0 / 0 |
| [teacher_ai_settings.html](../../templates/teacher_ai_settings.html) | Cài đặt và kiểm tra khóa AI | `teacher_ai_settings` | 8 | 15 / 0 / 0 |
| [teacher_analytics.html](../../templates/teacher_analytics.html) | Template cũ; endpoint cùng tên hiện redirect | Không thấy render; xem ghi chú dọn | 9: ứng viên loại bỏ | 26 / 0 / 0 |
| [teacher_practice_detail.html](../../templates/teacher_practice_detail.html) | Theo dõi học tập từng học sinh | `teacher_practice_detail` | 7 | 33 / 0 / 1 |
| [teacher_practice_list.html](../../templates/teacher_practice_list.html) | Danh sách học sinh cần theo dõi | `teacher_practice_list` | 7 | 0 / 0 / 0 |

Số `style` là số xuất hiện dạng `style=` trong mã nguồn; không phải số phần tử DOM sau khi render. Khối JS inline bao gồm cả cấu hình/data bootstrap cần giữ hoặc chuyển có kiểm soát, không mặc định là mã chết.

## 2. Khung dùng chung và partial — 13 file

| File | Vai trò | Phase | Quan hệ hiện tại |
|---|---|---|---|
| [base.html](../../templates/base.html) | Khung ứng dụng, CSRF, MathJax, nạp CSS/JS | 2 + 3 | Base của các trang nghiệp vụ |
| [components/bank_overview.html](../../templates/components/bank_overview.html) | Tổng quan ma trận ngân hàng | 4 | `question_bank_detail.html` |
| [components/bank_pagination.html](../../templates/components/bank_pagination.html) | Phân trang giữ bộ lọc ngân hàng | 4 | `question_bank_detail.html` |
| [components/diagnostic_report.html](../../templates/components/diagnostic_report.html) | Báo cáo chẩn đoán cũ; script preview/test còn dùng | 7 + 9 | Chưa thấy include/import từ template runtime; xem báo cáo dọn |
| [components/flash_messages.html](../../templates/components/flash_messages.html) | Thông báo phản hồi toàn ứng dụng | 3 | `base.html` |
| [components/footer.html](../../templates/components/footer.html) | Nạp thư viện và khởi tạo render toán/icon | 3 | `base.html` |
| [components/header.html](../../templates/components/header.html) | Thanh tiêu đề và tài khoản | 3 | `base.html` |
| [components/id6_picker.html](../../templates/components/id6_picker.html) | Macro chọn nhãn kiến thức/ID6 | 4 + 5 | `question_bank_classification.html`, `question_bank_detail.html`, `question_bank_import.html` |
| [components/import_duplicates.html](../../templates/components/import_duplicates.html) | Dò trùng, đối chiếu và nhập câu | 5 | `question_bank_import.html` |
| [components/import_scope.html](../../templates/components/import_scope.html) | Partial phạm vi nhập chưa thấy include trong runtime | 5 + 9 | Chưa thấy include/import từ template runtime; xem báo cáo dọn |
| [components/navigation.html](../../templates/components/navigation.html) | Điều hướng và vai trò | 3 | `base.html` |
| [components/practice_skill_matrix.html](../../templates/components/practice_skill_matrix.html) | Ma trận kỹ năng trong báo cáo tiến độ | 7 | `practice_home.html`, `practice_progress.html`, `teacher_practice_detail.html` |
| [components/selection_audit.html](../../templates/components/selection_audit.html) | Giải thích câu được chọn và nguồn | 7 | `exam_result.html`, `exam_take.html`, `practice_draft.html` |

## 3. Trang lỗi — 6 file

| File | Trạng thái | Phase |
|---|---|---|
| [errors/400.html](../../templates/errors/400.html) | Biến thể HTTP 400; include errors/error.html | 3 |
| [errors/403.html](../../templates/errors/403.html) | Biến thể HTTP 403; include errors/error.html | 3 |
| [errors/404.html](../../templates/errors/404.html) | Biến thể HTTP 404; include errors/error.html | 3 |
| [errors/405.html](../../templates/errors/405.html) | Biến thể HTTP 405; include errors/error.html | 3 |
| [errors/500.html](../../templates/errors/500.html) | Biến thể HTTP 500; include errors/error.html | 3 |
| [errors/error.html](../../templates/errors/error.html) | Layout lỗi độc lập và fallback cho mã lỗi khác, gồm 429 | 3 |

## 4. Kiểm tra tính đầy đủ

- Tổng: **52 template = 33 màn hình cấp trang + 12 component + 6 trang lỗi + 1 base**.
- Không thấy dependency template literal bị thiếu; không thấy asset static literal được template gọi mà thiếu file.
- Template không thấy render/include trong runtime: `teacher_analytics.html`, `components/diagnostic_report.html`, `components/import_scope.html`. Đây là ứng viên rà soát, không phải kết luận được phép xóa ngay.
- `components/diagnostic_report.html` còn được dùng bởi `scripts/preview_personalization_v2.py` và `tests/test_diagnostic_report_contract.py`; phải xử lý các bên dùng trước khi dọn.
- Không tính các file bị Git đánh dấu đã xóa hoặc template của sản phẩm lịch sử là màn hình hiện tại. Không khôi phục các tính năng đã loại bỏ trong đợt thiết kế này.
- Phase 1 chỉ tạo tài liệu. Quyết định bố cục, token và bản mẫu thuộc Phase 2; triển khai giao diện và xóa file thuộc các phase tiếp theo.
