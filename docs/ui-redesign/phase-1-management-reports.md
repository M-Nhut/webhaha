# Phase 1 — Kiểm kê tài khoản, quản lý, theo dõi và báo cáo

Ngày kiểm kê: 13/10/2026. Phạm vi: đọc mã nguồn tĩnh; chưa chạy ứng dụng, đăng nhập, gọi AI, đọc/sửa cơ sở dữ liệu hoặc thay giao diện. Các nhận xét về bố cục và tương tác bên dưới là kết luận từ template/CSS/JavaScript, chưa phải kết quả kiểm tra trên trình duyệt.

## 1. Kết luận và phạm vi thiết kế lại

- Có **14 template màn hình đang được route gọi** trong nhóm này, **6 template lỗi** đang dùng trực tiếp hoặc làm fallback/include, và **1 template phân tích cũ chưa tìm thấy nơi render/include**. Một template có nhiều biến thể theo vai trò và trạng thái; không đồng nhất số template với số màn hình cần nghiệm thu.
- Tất cả màn hình này phải được thiết kế lại, kể cả trang đang dùng `main.css`; không coi các màn hình CRUD, hồ sơ hoặc lỗi là đã đạt Modern White Academy.
- Vai trò có bằng chứng hỗ trợ xuyên suốt là `admin`, `teacher`, `student`. `manager` còn trong vài điều kiện trình bày, `parent` xuất hiện trong comment cũ; chưa có luồng đăng ký, nhãn vai trò và quyền chuyên biệt tương ứng. Không lập thêm màn hình phụ huynh/quản lý rồi mặc định đó là chức năng đang có.
- Hai điểm cần sửa khi chuyển UI: lựa chọn `admin` trong form thêm/sửa người dùng trái với backend; một số nút/liên kết gắn `manager` dẫn tới route không cho `manager` sử dụng.
- `/analytics/teacher` là **URL tương thích còn dùng**, nhưng `teacher_analytics.html` là **ứng viên code giao diện chết**. Không xóa endpoint cùng với template.
- `class_learning_report.js` là **ứng viên JS giao diện cũ**: chỉ thấy bản thân file tham chiếu trình dựng báo cáo nhúng; template chi tiết lớp hiện chỉ có liên kết sang báo cáo riêng. API báo cáo lớp vẫn được giao diện mới hơn `ai_reports.js` sử dụng.

Nguồn: `routes/auth.py`, `routes/academic.py`, `routes/practice.py`, `routes/ai_reports.py`, `routes/ai_settings.py`, `routes/errors.py`, `forms.py`, `helpers.py`, `services/dashboard.py`, các template tương ứng và các module JS được nêu ở phần 4.

## 2. Danh mục đầy đủ màn hình và biến thể

`GET/POST` dưới đây là phương thức khai báo trong mã nguồn; các route `GET` thông thường có thể được Flask cung cấp thêm `HEAD/OPTIONS`. Quyền thực tế có thể khác điều kiện hiển thị nút trong template; chỗ khác nhau được ghi riêng.

| ID | URL / endpoint | Template / biến thể | Quyền và dữ liệu | Trạng thái cần đưa vào thiết kế mới |
|---|---|---|---|---|
| MG-01 | `GET/POST /login` · `login` | `login.html`, HTML độc lập | Khách; người đã đăng nhập chuyển `/`; đăng nhập kiểm tra `is_active` | Bình thường; trường bỏ trống; sai tài khoản/mật khẩu hoặc khóa; flash sau đăng ký; ẩn/hiện mật khẩu; mobile; URL `next` |
| MG-02 | `GET/POST /register` · `register` | `register.html`, HTML độc lập | Khách; đăng ký chỉ `student/teacher`; đã đăng nhập chuyển `/` | Hai vai trò; tên đăng nhập/mã đã tồn tại; mật khẩu ngắn/không khớp; dữ liệu hợp lệ/không hợp lệ; flash thành công chuyển login |
| MG-03 | `GET/POST /profile` · `profile` | `profile.html` | Mọi tài khoản đã đăng nhập; thông tin chính và đổi mật khẩu là hai form | Avatar mặc định/hiện có/xem trước ảnh mới; sai định dạng ảnh; username trùng; ngày sinh trống; sai mật khẩu cũ; xác nhận mật khẩu không khớp; cập nhật thành công |
| MG-04 | `GET /` · `index` | `index.html` · **giáo viên** | Hai KPI số lớp và học sinh do giáo viên phụ trách; hoạt động nộp đánh giá đầu vào | Có/không lớp; có/không học sinh; có/không hoạt động; tên dài; lối vào ngân hàng và theo dõi |
| MG-05 | `GET /` · `index` | `index.html` · **học sinh** | Hai KPI khóa học đang ghi danh và bài đầu vào/tự luyện đã chấm | Chưa ghi danh; chưa làm bài; có hoạt động; lối vào tự luyện và tiến độ |
| MG-06 | `GET /` · `index` | `index.html` · **trung tâm** | `admin` theo luồng chính; route thực tế rơi vào nhánh này với mọi vai trò đăng nhập khác teacher/student | Có/không học sinh/giáo viên/hoạt động; CTA tạo lớp cho admin; không suy diễn ra dashboard manager/parent riêng |
| MG-07 | `GET /courses` · `courses` | `courses.html` | Admin xem tất cả; teacher xem lớp được giao; student xem lớp ghi danh (truy vấn danh sách không lọc trạng thái Enrollment) | Danh sách rỗng; lớp đang hoạt động/tạm ngưng; giáo viên/phòng chưa phân công; tên dài; thao tác theo vai trò |
| MG-08 | `GET/POST /courses/new` · `add_course` | `course_form.html` · tạo | Admin | Chưa chọn giáo viên; có giáo viên; ngày/mô tả trống; bật/tắt; xem trước giáo viên |
| MG-09 | `GET/POST /courses/<course_id>/edit` · `edit_course` | `course_form.html` · sửa | Admin; không có lớp → 404 | Giáo viên hiện có/thay mới/bỏ phân công; dữ liệu cũ thiếu; hủy/lưu; trạng thái hoạt động |
| MG-10 | `GET /courses/<course_id>` · `course_detail` | `course_detail.html` | Admin; teacher đúng người phụ trách; student có ghi danh active. Teacher/student sai phạm vi nhận flash và chuyển về courses | Có/không giáo viên, phòng, ngày, mô tả; cấu hình AI khả dụng/chưa có; danh sách học sinh rỗng/có dữ liệu; admin có ghi danh; teacher/admin có lối vào theo dõi và báo cáo |
| MG-11 | `GET /my-students` · `my_students` | `my_students.html` | Chỉ teacher bằng kiểm tra trực tiếp; admin cũng nhận flash rồi chuyển `/` | Không có học sinh; dữ liệu liên hệ/vị trí thiếu; danh sách nhiều dòng; tên/mã dài |
| MG-12 | `GET /users/students`, `/users/teachers` · `manage_users` | `manage_users.html` · 2 tab | Admin; role_name khác → 404 | Tab học sinh/giáo viên; người dùng active/khóa; rỗng; modal thêm mở/đóng; role student/teacher; xác nhận xóa |
| MG-13 | `GET/POST /users/<user_id>/edit` · `edit_user` | `edit_user.html` | Admin; không có người dùng → 404; backend chặn đổi role admin và role ngoài student/teacher | Thông tin thiếu; khóa/mở; role; lưu/hủy; reset mật khẩu; admin là trường hợp bị backend hạn chế |
| MG-14 | `GET /teacher/practice` · `teacher_practice_list` | `teacher_practice_list.html` | Teacher với lớp được giao; admin được decorator chấp nhận và xem tất cả; `course_id` ngoài phạm vi → 403 | Chưa có lớp/chưa có học sinh; chọn lớp; chưa làm bài; có bài đầu vào/tự luyện/kiểm tra; không có điểm trung bình; điều hướng tới học sinh |
| MG-15 | `GET /teacher/practice/<student_id>` · `teacher_practice_detail` | `teacher_practice_detail.html` | Teacher có lớp active của học sinh; admin theo decorator; `course_id` ngoài tập được xem → 403; không phải student → 404 | Phạm vi tất cả lớp/cụ thể; hồ sơ chưa có dữ liệu; mức nhận thức thiếu; vùng cần củng cố; kết quả kiểm tra; lịch sử đang làm/đã hoàn tất; vùng tạo bài luyện đóng/mở; ngân hàng theo lớp |
| MG-16 | `GET /ai-reports/class?course_id=…` · `ai_reports_class` | `ai_reports.html` · cả lớp **tổng quan** | Admin; teacher đúng lớp; mặc định lớp đầu nếu không chọn | Chưa có lớp; lớp không học sinh; học sinh chưa có dữ liệu; bộ lọc rỗng/có; đúng/sai/chưa đủ ý; bảng roster; bằng chứng và phân trang; tải lại/lỗi phiên/lỗi mạng |
| MG-17 | `GET /ai-reports/class?course_id=…&view=detail` | `ai_reports.html` · cả lớp **chi tiết** | Cùng quyền MG-16; chỉ teacher đúng lớp có nút phát sinh phân tích AI | AI missing/processing/completed/stale/failed; chưa có bài đã chấm; giả thuyết/khuyến nghị có hoặc không; đối chiếu đã/chưa xác nhận; dữ liệu thay đổi; bằng chứng; metadata |
| MG-18 | `GET /ai-reports/individual?course_id=…&student_id=…` · `ai_reports_individual` | `ai_reports.html` · cá nhân **tổng quan** | Admin; teacher đúng lớp; student phải ghi danh active; mặc định học sinh đầu nếu không chọn | Chưa có lớp; lớp chưa có học sinh; cá nhân chưa có bài chấm; bộ lọc, biểu đồ, tiến bộ và bằng chứng theo cá nhân |
| MG-19 | `GET /ai-reports/individual?course_id=…&student_id=…&view=detail` | `ai_reports.html` · cá nhân **chi tiết** | Cùng quyền MG-18; admin chỉ xem, teacher đúng lớp mới phát sinh AI | Toàn bộ trạng thái AI MG-17; phân tích cá nhân lưu trước đây có/không; không tìm thấy bằng chứng hợp lệ; quay về tổng quan lớp |
| MG-20 | `GET /teacher/ai-settings` · `teacher_ai_settings` | `teacher_ai_settings.html` | **Chỉ teacher thực sự**, admin không được dùng; từng khóa phải thuộc nhóm mặc định của chính teacher | Chưa sẵn sàng bảo vệ khóa; chưa nhóm/chưa khóa; nhóm đang bật/tạm dừng; có nhóm cũ; tối đa 20 khóa/dòng; ready/failed/chưa kiểm tra/chờ quota và các nguyên nhân lỗi cụ thể |
| MG-21 | Bất kỳ URL trả lỗi HTML | `errors/400.html`, `403.html`, `404.html`, `405.html`, `500.html` → include `errors/error.html`; 429/status khác dùng master fallback | Khách và người đã đăng nhập; API trả JSON riêng | Từng mã lỗi; đăng nhập/chưa đăng nhập; có/không history cùng origin; chi tiết kỹ thuật đóng/mở; sao chép thành công/thất bại; có/không details debug |

### URL chuyển hướng và hành động không phải màn hình độc lập

| URL / endpoint | Hợp đồng giữ khi đổi giao diện |
|---|---|
| `GET /logout` · `logout` | Kết thúc phiên và chuyển login; không có template |
| `GET /ai-reports` · `ai_reports` | Alias chuyển class/individual tùy `student_id`; giữ `course_id`, `student_id`, `view`, `refresh`, `skill`, `source`, `question_type` |
| `GET /analytics/teacher` · `teacher_analytics` | Alias chuyển `/teacher/practice/<student_id>` nếu chọn student; ngược lại `/teacher/practice`; còn trong route contract/tests |
| `POST /courses/<id>/delete` · `delete_course` | Admin; CSRF; xác nhận; thành công quay courses |
| `POST /enrollments` · `add_enrollment` | Admin; `student_id`, `course_id`, CSRF; mã/tên không có, trùng active, kích hoạt lại, thành công; không tạo thêm chức năng hủy ghi danh |
| `POST /users` · `add_user` | Admin; fields `role`, `username`, `fullname`, `user_code`, `phone`, `position`, `password`; backend chỉ nhận student/teacher |
| `POST /users/<id>/delete`, `/reset-password` | Admin; không xóa chính mình/admin; không reset admin; POST CSRF; mật khẩu trống dùng mặc định hiện có |
| `GET /api/ai-reports/<course_id>` · `ai_report_data` | Quyền theo lớp và học sinh; bộ lọc `skill/source/question_type`; `analysis=1`, `include_archive=1`; `Cache-Control: private, no-store` |
| `GET /courses/<id>/lesson4-report` | API báo cáo hiện có; vẫn là nguồn server được báo cáo riêng sử dụng |
| `POST /courses/<id>/lesson4-report/generate` | Chỉ teacher phụ trách phát sinh AI; JSON/form `force`; xử lý 202 processing, failed, stale; admin không có quyền phát sinh |
| `POST /courses/<id>/lesson4-report/<report_id>/review` | Admin/teacher có quyền lớp; `status` confirmed/rejected/unreviewed, `review_note`; stale hoặc chưa hoàn tất có thể 409; UI hiện chỉ gửi confirmed |
| `POST /teacher/ai-settings/keys` | `keys`, CSRF; lưu và kiểm tra batch; hạn mức/lỗi phải thể hiện đúng, không in raw key |
| `/teacher/ai-settings/keys/<id>/test`, `/retry` (`GET/POST`), `/delete` (`POST`) | Chủ teacher; UI hiện dùng POST retry/delete; giữ endpoint test tương thích nếu không có UI tương ứng |
| `POST /admin/ai-groups/<id>/disable` | Admin; không phải màn hình cài đặt nhóm/khóa của giáo viên; không thêm UI xem khóa cho admin |
| `POST /teacher/practice/<student_id>/ai-analysis` | Teacher thực sự và đúng lớp; fields `subject`, `course_id`, `force`; endpoint tồn tại, template detail hiện hướng người dùng sang báo cáo riêng |
| `POST /teacher/practice/<student_id>/errors/<observation_id>/review`, `/reports/<report_id>/review` | Endpoint còn đăng ký; review lỗi nhận `status/teacher_note`, review báo cáo nhận `review_note/correction_text`; không thấy form gọi chúng trong template detail hiện tại. Không mặc định xóa mã nghiệp vụ chỉ vì thiếu UI |
| `POST /teacher/practice/<student_id>/generate` | Tạo bản nháp bài củng cố; form nằm trong trang detail; chi tiết bản nháp thuộc nhóm học tập/kiểm tra |

## 3. Quyền và dấu vết vai trò cũ

1. `helpers.py:13` chỉ khai báo nhãn admin/teacher/student; `forms.py` và `routes/auth.py` chỉ cho tự đăng ký student/teacher. `User.role` là chuỗi trong `models.py`, không phải bằng chứng mọi chuỗi đều là vai trò đang hỗ trợ.
2. `role_required` trong `services/access_control.py:838` luôn cho admin cùng vai trò khai báo. Vì vậy `@role_required("teacher")` chưa đủ kết luận "chỉ teacher"; phải đọc kiểm tra bên trong. `teacher_ai_settings`, phát sinh báo cáo lớp và phát sinh AI cá nhân có kiểm tra teacher thực sự riêng.
3. `manager` còn ở `index.html`, `courses.html`, `components/navigation.html`; nút tạo lớp/quản lý người dùng không tương ứng quyền backend. Đây là backlog dọn điều kiện UI cũ; không tự mở rộng quyền.
4. Comment Student/Parent trong `index.html` không có nhánh parent trong `routes/academic.py` hay phạm vi học sinh phụ thuộc parent trong `services/dashboard.py`. Chưa có màn hình phụ huynh có thể khẳng định hoạt động.
5. `manage_users.html` và `edit_user.html` có option admin, nhưng backend chỉ tạo/sửa student/teacher và chặn đổi admin. UI mới phải phản ánh hợp đồng này.
6. Route `/my-students` kiểm tra `current_user.role != "teacher"` trực tiếp; không coi admin được vào trang này như `/teacher/practice`.
7. Chi tiết lớp dùng active enrollment; danh sách lớp student hiện dùng enrollment mọi trạng thái. Không đổi truy vấn nghiệp vụ trong redesign; cần kiểm chứng và làm rõ trạng thái hiển thị ở phase triển khai.

## 4. Hợp đồng HTML, form, JavaScript cần giữ hoặc chuyển cùng nhau

### Tài khoản, hồ sơ, CRUD

- Login: `#login-form`, `[data-password-toggle]`, `aria-controls` trỏ đúng input password; `static/js/login.js` đổi type, `aria-pressed`, nhãn và trả lại ẩn khi `pagehide`. Giữ `autocomplete=username/current-password`, lỗi liên kết `username-errors/password-errors`, WTForms hidden CSRF và `next`.
- Register: field names `user_code`, `fullname`, `username`, `role`, `phone`, `position`, `password`, `confirm_password`; WTForms render lỗi từng trường; password mới cho password manager. Thông điệp giới thiệu Toán 9 hiện có là nội dung cần rà soát cùng phạm vi môn học thật.
- Profile: hai form POST độc lập với `submit_profile` và `submit_password` quyết định nhánh xử lý; form avatar `multipart/form-data`; `#avatar-preview`, `previewImage(event)` + FileReader. Giữ liên kết trường/lỗi và các hidden fields của từng WTForm.
- Course form: names `course_name`, `subject`, `classroom`, `start_date`, `end_date`, `description`, `teacher_id`, `is_active`; `#teacher_id`, `#teacher-preview`, `#t-avatar/#t-name/#t-code/#t-position/#t-phone` dùng bởi inline `updateTeacherPreview`. Khi tách JS mới phải chuyển dữ liệu `teachersData` an toàn cùng template; không bỏ xem trước giáo viên.
- Course detail ghi danh: giữ `course_id` hidden, `student_id`, CSRF. `#lesson4-ai-report` hiện **chỉ là anchor của card dẫn sang báo cáo riêng**, vẫn được link từ `teacher_practice_list.html`; không xóa id trước khi đổi link.
- User modal: Alpine `x-data={addOpen,role}`, `x-show`, click overlay, `x-model`; thêm/sửa cần chuyển cùng logic role-dependent fields. Template hiện chưa có semantics/focus trap/Escape/return focus của dialog đầy đủ; đây là yêu cầu thiết kế mới.
- Hành động xóa/reset đang dùng `onsubmit=confirm(...)`; UI mới có thể thay bằng dialog dùng chung nhưng phải giữ POST/CSRF và không biến thành GET.

### Theo dõi học tập và báo cáo

- Teacher list: query `course_id`, `#course-select` tự submit; liên kết học sinh giữ `course_id` để không mất phạm vi lớp. Thiếu lớp đang chỉ là select trống; cần empty state rõ.
- Teacher detail: `#learning-course` chọn phạm vi; matrix dùng `components/practice_skill_matrix.html`; `#learning-history`, `#learning-support` là mốc điều hướng; form tạo bài củng cố giữ `course_id`, `total_questions=22`, `bank_ids` lặp, `chapters`, `sections`, `topics`, `cognitive_levels`, `mix_weak/mix_middle/mix_strong`.
- `static/js/modules/teacher_practice_detail.js`: `#adaptive-course`, `.adaptive-bank`, `data-subject`, `data-course-counts`, `.bank-count`; tự ẩn/disable/uncheck ngân hàng không dùng được trong lớp đang chọn. Đây là tương tác gắn quyền nguồn, không chỉ trang trí.
- Báo cáo AI: `ai_reports.html` + `static/css/ai-reports.css` + `static/js/modules/ai_reports.js` phải được chuyển đồng bộ. CSS hiện dùng nhiều `--pop-*`, `--ink`, viền 2px, shadow cứng; JS còn chứa palette chart trực tiếp nên chỉ thay CSS không thể xóa hết phong cách cũ.
- Root `#ai-report-workspace` mang `data-api-url`, `data-page-url`, `data-personal-url`, `data-refresh`, `data-student-id`, `data-detail`, `data-generate-url`, `data-review-url`. `#ai-initial-data` nhúng JSON số liệu; overview dùng dữ liệu server ngay, không chờ AI.
- Các form/controls JS hiện dùng: `#ai-context-form`, `#ai-course`, `#ai-person`, `#ai-filters`, `#ai-skill`, `#ai-source`, `#ai-type`, `#ai-reset`, `#ai-outcome`, `#ai-reload`, `#ai-generate`, `#ai-review`, `#ai-detail-link`.
- Các vùng JS render: `#ai-status`, `#ai-updated`, `#ai-message`, `#ai-content`, `#ai-kpis`, `#ai-bars`, `#ai-donut`, `#ai-distribution`, `#ai-skill-table`, `#ai-student-table`, `#ai-roster-count`, `#ai-summary`, `#ai-progress-section/#ai-progress`, `#ai-cause-list`, `#ai-risk-list`, `#ai-recommendation-list`, `#ai-archive-section/#ai-archive`, `#ai-meta`, `#ai-evidence/#ai-evidence-pagination`.
- Interactions: click `[data-skill]` lọc dạng; `[data-outcome]` lọc bằng chứng và `aria-pressed`; `[data-page]` phân trang bằng chứng; đổi bộ lọc cập nhật URL bằng `history.replaceState` và giữ context form/tab links; mở details gọi `window.renderFormulas`.
- Phân biệt **bộ lọc số liệu** với **phạm vi phân tích AI cả lớp/cá nhân**. Detail không dùng filter để thu hẹp bản AI. Các nguồn `standalone/initial_diagnostic/practice` và kết quả `correct/wrong/partial` là hợp đồng dữ liệu, không đổi chỉ vì đổi nhãn.
- JS báo cáo dùng meta CSRF cho POST JSON, sequence chống phản hồi tải cũ đè mới, disable trong lúc xử lý, polling 5 giây tối đa theo cửa sổ 6 phút. Điều hướng vào detail với `refresh=1` hiện có thể gọi phân tích AI nếu teacher và có bằng chứng; cần làm rõ hành động này trong bản thiết kế, giữ đúng quyền và không phát sinh lời gọi ngoài chủ ý.
- Formula/image trong bằng chứng là nội dung nghiệp vụ; `.katex-render` và `window.renderFormulas` là hook, không được xóa như class theme cũ. Biểu đồ có số liệu/bảng tương đương và nhãn tương tác; UI mới phải giữ cách đọc không chỉ dựa màu.
- Settings AI: `#teacher-ai-keys`, name `keys`, `#teacher-ai-key-table`, rows `data-key-id`; giá trị chỉ `masked_key`. Giữ phân biệt khóa đã xác minh nhưng chờ quota với khóa chưa xác minh; không gộp hết thành "lỗi".
- Error master: `goBackOrHome`, `toggleDiagnostics`, `copyDiagnosticInfo`, `#diag-body/#diag-chevron/#ref-id/#copy-toast`; history fallback, clipboard, request id; đưa inline CSS/JS về cấu trúc mới khi tới phase trang lỗi. API JSON không đổi thành HTML.

## 5. Những phần cũ cần dọn và phần phải giữ

| Đối tượng | Bằng chứng tĩnh / quyết định sau khi chuyển |
|---|---|
| `templates/teacher_analytics.html` | Không tìm thấy `render_template/include/extends` tới file; route analytics chỉ redirect tại `routes/practice.py:1018`. Ứng viên xóa sau kiểm tra tham chiếu toàn repo; không tái dựng thành một màn hình riêng dư thừa |
| `/analytics/teacher` | Còn route tại `routes/practice.py:1134`, fixture và test compatibility; giữ redirect dù xóa template cũ |
| `static/js/modules/class_learning_report.js` | Không tìm thấy nơi tải script trong templates/routes; UI nhúng `lesson4-report-*`/dataset mà script đòi không còn trong course detail. Ứng viên xóa; root anchor `lesson4-ai-report` vẫn có link dùng |
| `lesson4-report` API và service | Được `ai_reports.js`/`routes/ai_reports.py` sử dụng; giữ, không đồng nhất với JS nhúng cũ |
| `lesson4_report` biến route course detail | Route vẫn lấy latest, template hiện không đọc biến này; ứng viên dọn context/query thừa sau kiểm tra chức năng, không phải lệnh xóa dữ liệu/báo cáo lịch sử |
| `ai_analyses/learning_reports/error_observations` context trong teacher detail | Route còn xây dữ liệu nhưng template hiện chủ yếu dẫn sang workspace riêng; cần đối chiếu chính xác từng biến trước dọn, tránh xóa endpoint/service báo cáo |
| Auth và error tải `main.css` + `neo-pop.css` riêng | Phải chuyển cả HTML độc lập, không chỉ base. Register còn `pop-study.svg`, sticker/tag, font Nunito; login còn stylesheet riêng; error master có nhiều inline CSS và SVG theo mã |
| `static/css/ai-reports.css`, palette JS AI | Thay quy tắc cũ bằng token/thành phần mới; chart colors và SVG stroke trong JS cũng phải chuyển. Không xóa logic biểu đồ/bằng chứng |
| Inline styles/preview code CRUD | Di chuyển và thay khi rebuild từng page; giữ names/actions/id contracts hoặc cập nhật đồng bộ module/test |
| Điều kiện manager/parent, option admin không hợp lệ | Là dấu vết/inconsistency cần loại khỏi UI phù hợp quyền thật; không sửa role dữ liệu hoặc mở rộng quyền như một phần trang trí |

Chưa xóa đối tượng nào trong Phase 1. Việc khẳng định "không còn code chết" ở Phase 9 cần kiểm tra build/runtime, toàn bộ tham chiếu, DOM mới và luồng quyền; tìm kiếm tĩnh chỉ tạo danh sách ứng viên.

## 6. Yêu cầu thiết kế mới theo từng nhóm

| Nhóm | Nhu cầu bố cục/nội dung cho Modern White Academy |
|---|---|
| Login/register | Khung xác thực đồng bộ; nội dung giới thiệu vừa đủ; form dễ quét; lỗi tại trường và tóm tắt nếu nhiều lỗi; kích thước nhỏ không bị cắt; giữ paste/password manager |
| Profile | Hồ sơ và bảo mật phân khu rõ; preview ảnh dễ hiểu; actions gắn từng form; tên dài/ảnh lỗi có fallback; đồng bộ form validation |
| Dashboard | Ưu tiên task theo role; giảm diện tích logo/trang trí; KPI đúng nguồn dữ liệu; không dựng danh sách “việc cần làm” nếu backend chưa cung cấp; empty state có lối vào phù hợp |
| Courses | Danh sách quản lý gọn; trạng thái hoạt động bằng chữ và màu; thao tác chính/phụ rõ; khả năng đọc bảng trên mobile; thống nhất gọi “lớp học/khóa học” theo chức năng thực tế |
| Course form/detail | Đưa thông tin lớp, giáo viên, danh sách học sinh và thao tác theo mức ưu tiên; không lặp tiêu đề lớn; vùng AI chỉ hiện cho ngữ cảnh cần; ngày và mô tả đủ đọc |
| Users/my-students | Danh bạ đọc nhanh; roles đúng backend; modal có semantics/focus/keyboard; mobile dùng vùng scroll/card thích hợp; trạng thái khóa rõ; phân biệt xóa/reset với sửa |
| Teacher learning | Chọn lớp trước, học sinh sau; điểm tự luyện/đầu vào và bằng chứng đề kiểm tra giữ nghĩa riêng; lịch sử và hỗ trợ có phân cấp; matrix “chưa dữ liệu” không biến thành 0% |
| AI reports | Context lớp/học sinh cố định rõ; tổng quan dẫn tới điểm cần xem; chi tiết có điều hướng tới bằng chứng; loading/stale/failed không che số liệu sẵn có; cảnh báo/hypothesis khác fact; metadata thu gọn; bảng/biểu đồ nhẹ và cùng palette token |
| AI settings | Form khóa ngắn, rõ thao tác kiểm tra/lưu; bảng masked keys và status nhất quán; nêu hành động khắc phục theo lỗi; không hiển thị raw key hoặc mở quyền admin |
| Errors | Trang lỗi gọn, hướng quay lại phù hợp người dùng; không đưa khách/student vào đường dẫn ngân hàng không có quyền; kỹ thuật thu gọn; mã sự cố dễ sao chép; màu/typography theo hệ thống mới |

Áp dụng skill `ui-ux-pro-max` cho audit: truy vấn `data table empty states --domain ux -n 3` trả về Empty States (Feedback, All), Table Handling (Responsive, Web), Bulk Actions (Data Entry, Web). Hai kết quả đầu phù hợp các bảng quản lý: empty state có hành động, bảng có chiến lược mobile. Kết quả bulk chỉ là gợi ý, **không tự bổ sung hành động hàng loạt khi backend chưa có**. Chốt token/palette/font và mockup thuộc Phase 2, chưa thực hiện trong tài liệu này.

## 7. Kiểm chứng cần chạy ở phase triển khai

Các test dưới đây chỉ được đọc để lập kế hoạch, **chưa chạy trong Phase 1**. Nhiều test import `app` và tạo/xóa schema; trước chạy phải xác nhận fixture/config dùng DB thử nghiệm tách biệt.

| Phần | Bằng chứng test có sẵn / phạm vi cần bổ sung bằng kiểm tra thực tế |
|---|---|
| URL/endpoints/methods | `tests/test_route_contract.py`, `tests/fixtures/route_contract.json`; giữ alias analytics và endpoints lâu dài |
| Learning list/detail | `tests/test_learning_workspace.py`: học sinh chưa làm, analytics redirect, course ngoài quyền 403, đọc detail không ghi mastery |
| Class report | `tests/test_class_lesson4_report.py`: phạm vi lớp, bằng chứng, no-data roster, cache/stale, generate/review/owner; một số assert text đang phản ánh nội dung lớp cũ cần đối chiếu contract cuối cùng trước cập nhật |
| AI report evidence | `tests/test_phase5_reports.py`, `tests/test_personalization_mvp.py`: diagnostic làm nguồn, snapshot revision, lỗi provider không lộ khóa, quyền qua analytics |
| AI settings | `tests/test_teacher_ai_simplified.py`, `tests/test_teacher_keys_phase3.py`, `tests/test_teacher_keys_phase4.py`, `tests/test_teacher_keys_phase5.py`, `tests/test_ai_gateway_review.py`: owner, encryption, quota, masking, default group, lớp chuyển giáo viên |
| Error HTML/JSON | `tests/test_error_pages.py`: 404/405 HTML, 403/500 helper, API JSON và request id; text assertion thay đổi phải vẫn giữ ý nghĩa điều hướng/lỗi |
| Auth/profile/course/user UI | Chưa tìm thấy test chuyên biệt đủ phủ cả nhóm; cần kiểm tra form lỗi, CSRF, upload avatar, quyền, create/edit/delete/reset/ghi danh bằng DB test và dữ liệu giả |
| Accessibility/responsive | Kiểm tra thủ công 375/768/1024/1440, landscape, zoom/text expansion, keyboard, focus modal, screen reader labels, contrast; report chart có bảng tương đương; print report |
| Cleanup | Tìm lại tham chiếu template/JS/CSS/asset, thăm tất cả route và trạng thái/role trước xóa; mở network/console xác nhận không file 404, selector null hoặc style từ hệ thống cũ |

## 8. Đầu vào cho các phase sau

- Phase 2: dùng danh mục MG-01…MG-21 và hợp đồng phần 4 để làm wireframe, thành phần và trạng thái; chưa chốt thiết kế tại Phase 1.
- Phase 3: tài khoản, hồ sơ, lỗi và khung chung; các template độc lập cũng phải chuyển.
- Phase 7: teacher learning list/detail, phối hợp luồng bài củng cố và kết quả từ nhóm học tập/kiểm tra.
- Phase 8: ba dashboard, classes/users/my-students, cả bốn biến thể AI report và settings.
- Phase 9: xác minh/xóa ứng viên giao diện cũ; giữ endpoint, dữ liệu và service còn dùng; chốt quyền thật cho từng liên kết mới.

