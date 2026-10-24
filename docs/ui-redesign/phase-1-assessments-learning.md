# Phase 1 — Kiểm kê kiểm tra, đánh giá đầu vào và học tập

Ngày kiểm kê: 13/10/2026. Phạm vi: chuẩn bị thiết kế lại toàn bộ giao diện Modern White Academy, ưu tiên ngân hàng và kiểm tra. Tài liệu này chỉ ghi nhận mã nguồn và yêu cầu thiết kế; chưa thay đổi giao diện, hành vi nghiệp vụ hoặc dữ liệu.

## 1. Mức độ xác minh và quy ước

- **Hiện trạng tĩnh:** đã đọc route, template, CSS, JavaScript và các kiểm thử liên quan. Các đường dẫn trong tài liệu là tương đối so với thư mục gốc dự án.
- **Đề xuất thiết kế:** hướng cho Phase 2 và các phase triển khai sau, chưa phải màn hình đã làm.
- **Chưa xác minh runtime:** chưa khởi chạy Flask, chưa đăng nhập từng vai trò, chưa có ảnh chụp trình duyệt, chưa kiểm tra dữ liệu thật và chưa chạy bộ kiểm thử. Không suy ra rằng test hiện tại đang xanh.
- Không import `app.py`, không mở/sửa cơ sở dữ liệu hoặc `.env` trong việc kiểm kê này.
- Đã đọc skill `ui-ux-pro-max` ở `/Users/mac/.agents/skills/ui-ux-pro-max/SKILL.md`; áp dụng cách kiểm kê theo nhiệm vụ, trạng thái, khả năng truy cập và nền tảng Flask/Jinja hiện có. Chưa chốt token/font/bố cục chi tiết trước Phase 2.

## 2. Danh mục màn hình và biến thể bắt buộc thiết kế lại

Có **13 template trang được route sử dụng trong phạm vi này**, nhưng số màn hình cần thiết kế lớn hơn do cùng template có nhiều vai trò và trạng thái.

| ID | Trang / template | Biến thể phải có trong thiết kế mới | Phase triển khai |
|---|---|---|---|
| A01 | `assessment_list.html` — danh sách đề | Giáo viên/admin: nháp và đã giao; học sinh: đề lớp được giao; rỗng | 6 |
| A02 | `assessment_from_bank.html` — tạo đề từ ngân hàng | Chưa chọn lớp; chọn ngân hàng; nguồn không đủ; chọn thủ công; chọn ngẫu nhiên theo hình thức; tổng điểm hợp lệ/không hợp lệ | 5 |
| A03 | `assessment_import.html` — biên soạn/đối chiếu đề | Đề từ file LaTeX và từ ngân hàng; nội dung/đáp án/nhãn/trọng số; chưa lưu/đang lưu/lỗi/đã lưu; xác nhận giao | 5 |
| A04 | `assessment_matrix.html` — ma trận | Tổng hợp theo chương/kiến thức/hình thức/nhận thức; thiếu nhãn; chi tiết câu; Excel; đề nháp và đã khóa | 6 |
| E01 | `exam_take.html` — làm kiểm tra lớp | `assessment_purpose=standalone`; thang 10; thời gian; đáp án đơn/nhiều/Đúng-Sai/ngắn; chưa mở/đóng/đã nộp | 6 |
| E02 | `exam_take.html` — làm đầu vào | `assessment_purpose=initial_diagnostic`; quyền assignment; đề chung đóng băng; khởi tạo hồ sơ sau nộp | 7 |
| E03 | `exam_take.html` — tự luyện cá nhân | Fixed practice `aptga.version=practice-22-v1`; 12 + 4 + 6 câu; giải thích lựa chọn; một lần nộp/đề | 7 |
| E04 | `exam_take.html` — bài luyện lịch sử | Các bài `exam_type=practice` chưa theo fixed blueprint; không tự giả định tất cả đề đều 22 câu | 7 |
| R01 | `exam_result.html` — kết quả cá nhân | Học sinh xem bài mình; giáo viên/admin xem một bài; đúng/sai/đúng một phần/bỏ trống; có/thiếu lời giải; lịch sử chưa chấm | 6–7 |
| R02 | `exam_result.html` — danh sách bài nộp | Giáo viên/admin; chưa có lượt nộp; điểm, tỷ lệ, thời gian, trạng thái và liên kết chi tiết | 6 |
| R03 | `exam_result.html` — quyết định sau tự luyện | `can_decide`; tiếp tục được/nguồn không còn hợp lệ; kết thúc phiên; thông báo đầu vào hoàn tất | 7 |
| D01 | `diagnostic_list.html` — quản lý đầu vào | Admin tạo/xóa/xem; giáo viên thấy đề do mình tạo, xóa trong phạm vi; học sinh được redirect sang Tự luyện | 7 |
| D02 | `diagnostic_form.html` — wizard đầu vào | Admin; chọn ngân hàng → chọn 22 câu/8 dạng → đối chiếu toàn bộ và chọn lớp → tạo; khôi phục bộ câu đang chọn | 7 |
| P01 | `practice_home.html` — điểm vào học tập | Chưa có lớp; cần đầu vào; chưa có đầu vào hợp lệ; nguồn chưa sẵn sàng; tạo mới; mở lại đề chưa nộp; chờ tiếp tục/kết thúc; bài giáo viên giao | 7 |
| P02 | `practice_progress.html` — tiến bộ | Bộ lọc môn; chưa đủ bằng chứng; hồ sơ có dữ liệu; biểu đồ điểm/thành thạo; độ chính xác; lịch sử; ma trận 8 dạng × 4 mức | 7 |
| T01 | `teacher_practice_list.html` — theo dõi lớp | Giáo viên/admin; chọn lớp; lớp chưa có học sinh; học sinh chưa làm bài; số lượt và điểm TB | 7; phối hợp báo cáo Phase 8 |
| T02 | `teacher_practice_detail.html` — quá trình học một học sinh | Lọc lớp; tổng hợp theo môn; bằng chứng kiểm tra riêng; lịch sử bài; liên kết AI; tạo bài luyện củng cố | 7; phối hợp báo cáo Phase 8 |
| T03 | `practice_draft.html` — duyệt bài luyện cá nhân | Giữ nguyên 22 câu; sửa tiêu đề/thời gian/phát hành; nguồn không còn hợp lệ; đã có bài làm nên không được sửa | 7 |

Template còn tồn tại nhưng **không có route đang render trực tiếp**: `teacher_analytics.html`; `/analytics/teacher` hiện redirect tới T01 hoặc T02. Đây là ứng viên dọn sau kiểm tra tham chiếu toàn repo, không phải trang mới cần dựng lại chỉ vì có file.

## 3. Route, URL và quyền thực tế

Tất cả handler dưới đây yêu cầu đăng nhập. `role_required("teacher")` trong `services/access_control.py:838` còn cho phép **admin**; các handler tự kiểm tra `current_user.role` có thể hạn chế thêm. Không suy luận quyền chỉ từ tên decorator hoặc nhãn menu.

### 3.1. Kiểm tra lớp và ma trận

Nguồn: `routes/assessments.py` và `routes/practice_runtime.py`.

| Endpoint | URL, method | Quyền và ràng buộc chính |
|---|---|---|
| `assessment_list` | `GET /assessments` | Student: enrollment active, đề active; teacher: lớp do mình phụ trách; admin: tất cả đề standalone |
| `assessment_from_bank` | `GET/POST /assessments/from-bank` | Teacher/admin; lớp active; nguồn ngân hàng phải hợp lệ theo giáo viên hiện tại của lớp |
| `assessment_import` | `GET/POST /assessments/import/<session_id>` | Teacher/admin **và đúng `ImportSession.user_id`**; scope `document_kind=assessment`; xác thực lớp; đề active hoặc có submissions thì redirect kết quả, không mở editor |
| `assessment_matrix` | `GET /assessments/<exam_id>/matrix` | Teacher phụ trách lớp/admin; chỉ standalone; `?download=xlsx` xuất Excel; private/no-store |
| `assessment_take` | `GET/POST /assessments/<exam_id>/take` | Chỉ student; `standalone=True`; đúng lớp đang học, nguồn còn hợp lệ, đề `status_label=open`; một lần nộp |
| `assessment_result` | `GET /assessments/<exam_id>/result` | Student xem bài mình; teacher phải phụ trách lớp và bài nằm trong quyền xem submission; admin; `?submission_id=` chọn một bài |

Đường vào đề từ LaTeX đi qua `GET /question-banks/import` và `POST /question-banks/import/upload`, với `document_purpose=assessment` hoặc kết quả nhận diện scope assessment. Import trả `redirect_url` sang editor A03. Giao diện import dùng chung được kiểm kê trong nhóm ngân hàng; cần giữ liên kết chuyển tiếp đúng, không dựng một luồng upload rời không nối service hiện tại.

### 3.2. Đầu vào và runtime học sinh

Nguồn: `routes/diagnostics.py`, `routes/practice_runtime.py`, `services/practice_runtime.py`.

| Endpoint | URL, method | Quyền và ràng buộc chính |
|---|---|---|
| `diagnostic_list` | `GET /diagnostics` | Admin: tất cả đầu vào; teacher: `created_by=current_user.id`; student: redirect `/practice` |
| `create_diagnostic` | `GET/POST /diagnostics/new` | **Chỉ admin**; POST cuối xác nhận digest, câu, lớp, `confirmed=yes`; đóng băng và giao cohort |
| `diagnostic_question_choices` | `GET /api/diagnostics/question-choices` | **Chỉ admin**; bank, phân trang 25 câu, tìm kiếm/loại/mức/dạng; trả lý do không đủ điều kiện |
| `review_diagnostic` | `POST /api/diagnostics/review` | **Chỉ admin**; chỉ đọc và kiểm tra toàn bộ bộ câu, trả lớp hợp lệ + `review_digest`; chưa tạo đề |
| `delete_diagnostic` | `POST /diagnostics/<exam_id>/delete` | Teacher/admin; teacher phải là người tạo hoặc giáo viên hiện tại của lớp; xóa có dữ liệu liên quan nên giao diện cần xác nhận cụ thể |
| `practice_take` | `GET/POST /practice/<exam_id>/take` | Chỉ student; practice hoặc initial_diagnostic; enrollment active; fixed paper đúng `student_id`; đầu vào cần assignment đủ điều kiện; nguồn live khi mở làm |
| `practice_result` | `GET /practice/<exam_id>/result` | Student chỉ bài mình; teacher theo `teacher_can_access_submission`; admin; `?submission_id=` xem bài cụ thể |

`practice_take` không phải đường làm đề standalone thứ hai: `_get_practice_exam()` từ chối sai loại bằng 404. Khi đọc kết quả không yêu cầu nguồn live như lúc bắt đầu làm, để giữ bằng chứng lịch sử có thể đọc được; quyền học sinh vẫn cần enrollment và các kiểm tra tương ứng.

### 3.3. Tự luyện, tiến độ và theo dõi giáo viên

Nguồn: `routes/practice.py`.

| Endpoint | URL, method | Quyền và ràng buộc chính |
|---|---|---|
| `practice_home` | `GET /practice?course_id=` | Student; lớp active có enrollment active; course_id ngoài quyền → 403; vai trò khác redirect trang chính |
| `practice_generate` | `POST /practice/generate` | Student; hoàn tất đầu vào; chỉ nguồn được đầu vào lớp xác định; nếu đã có đề chưa nộp hoặc đang chờ quyết định thì mở lại đề/kết quả |
| `practice_progress` | `GET /practice/progress?subject=` | Student; hồ sơ/lịch sử theo môn; vai trò khác redirect trang chính |
| `practice_continue` | `POST /practice/submissions/<submission_id>/continue` | Student sở hữu bài/phiên; graded + snapshot + awaiting_decision; nguồn lớp và quyền được xác thực lại |
| `practice_end` | `POST /practice/submissions/<submission_id>/end` | Student sở hữu bài/phiên; ghi trạng thái kết thúc, không cho lựa chọn cũ mở lại phiên |
| `teacher_practice_list` | `GET /teacher/practice?course_id=` | Teacher lớp mình/admin tất cả lớp; active roster; course_id ngoài quyền → 403 |
| `teacher_practice_detail` | `GET /teacher/practice/<student_id>?course_id=` | Teacher phải có lớp active enrollment của học sinh/admin; subject và submissions giới hạn theo các lớp được chọn |
| `teacher_generate_adaptive_practice` | `POST /teacher/practice/<student_id>/generate` | Teacher phụ trách lớp/admin; đã hoàn tất đầu vào; bank cùng môn và được giáo viên hiện tại của lớp dùng; tạo fixed draft |
| `teacher_practice_draft` | `GET/POST /teacher/practice/drafts/<exam_id>` | Teacher người tạo/admin; chỉ fixed practice; khi phát hành teacher còn phải phụ trách lớp và nguồn còn hợp lệ; có submission thì khóa chỉnh sửa |
| `teacher_analytics` | `GET /analytics/teacher?student_id=` | Teacher/admin; redirect detail nếu có student_id, ngược lại redirect list; không render template analytics cũ |
| `teacher_run_ai_analysis` | `POST /teacher/practice/<student_id>/ai-analysis` | **Teacher thực sự phụ trách lớp**, admin bị 403 trong handler; cần subject/course_id đúng. Hiện T02 dẫn sang workspace AI khác, không có form gọi trực tiếp endpoint này |
| `teacher_review_error` | `POST /teacher/practice/<student_id>/errors/<observation_id>/review` | Teacher/admin trong phạm vi lớp; trạng thái observed/reviewed/dismissed + ghi chú; không có form tương ứng trong T02 hiện tại |
| `teacher_review_report` | `POST /teacher/practice/<student_id>/reports/<report_id>/review` | Teacher/admin trong phạm vi; report theo course, còn mới so với bằng chứng/cấu hình; không có form tương ứng trong T02 hiện tại |

Ba POST AI/review cuối là **hành vi backend còn tồn tại nhưng chưa thấy control tương ứng trong template T02 hiện tại**. Không tự khôi phục toàn bộ UI cũ trong redesign; cần đối chiếu workspace AI và quyết định đích ở Phase 2/8. Kiểm kê báo cáo AI chi tiết thuộc tài liệu nhóm báo cáo.

## 4. Hợp đồng form/DOM/JavaScript cần bảo toàn hoặc chuyển đổi đồng bộ

### 4.1. Chọn câu và editor kiểm tra

- A02 GET: `course_id`, nhiều `bank_ids`; POST: `course_id`, `bank_ids`, `mode=manual|auto`, nhiều `question_ids`, `count_<kind>`, `budget_<kind>`, `csrf_token`. Backend còn nhận `quantity` cho tương thích; UI hiện dùng số câu theo hình thức.
- `kinds` hiện gồm single/true_false/short_answer, điểm toàn đề bằng 10. Manual lấy số câu thực chọn; auto lấy quota theo phần. Không thiết kế reorder hay thêm/xóa câu trong editor như chức năng đã có: editor hiện giữ thứ tự nguồn.
- A03 thông tin: `title`, `course_id`, `duration_minutes` (1–240), `budget_<kind>`, `action=draft|publish`, `reviewed=yes` khi giao.
- Mỗi câu đánh số từ 0, prefix `q<i>_`: `context`, `question_text`, `answer` cho ngắn; `option<j>`, `truth<j>` hoặc `correct`; `report_category`, `report_chapter`, `report_code`, `difficulty_level`, `report_confirmed`, `weight`, `explanation`.
- `assessment_editor.js`: `.assessment-editor`, `#assessment-save-status`, `#assessment-points-status`, `#assessment-matrix-link`, `[data-question-index]`, `[data-question-kind]`, `[data-formulas]`, `[data-preview-field]`, `.assessment-render`, `[data-item-points]`, button `name=action`. Đổi markup phải sửa cùng JS.
- Editor dùng fetch FormData Accept JSON; response có `success`, `message`, `matrix_url`, `redirect_url`; error hiển thị và giữ nội dung trong DOM. Có dirty flag, phiên bản edit để phát hiện chỉnh tiếp trong khi lưu, cảnh báo rời trang. **Chưa thấy autosave định kỳ hoặc khôi phục editor từ browser storage.**
- Preview công thức cập nhật debounce 220 ms, gọi `window.renderFormulas` và `MathJax.typesetClear`; ảnh/formula mapping phải đi theo câu khi thay template.

### 4.2. Wizard đầu vào

- `#diagnostic-wizard`, `#dw-config` JSON (userId, total, quotas, labels, skills, duration, choicesUrl, reviewUrl), `[data-step]`, `[data-progress-step]`, `[data-quota]` và toàn bộ ID `dw-*` đang là hợp đồng chặt với `diagnostic_wizard.js`.
- Nguồn 1 ngân hàng; phải đủ 22 câu = 12 single + 4 true_false + 6 short_answer, bao phủ 8 dạng; thời gian mặc định **40 phút** theo `practice_blueprint.DURATION_MINUTES`. Không biến các thông số cố định thành điều khiển sửa tự do khi backend chưa hỗ trợ.
- API choices chỉ tải một trang; đáp án/chi tiết qua `detail_url` tải khi mở details; `AbortController`, phiên bản request và debounce giúp tránh kết quả tìm kiếm cũ ghi đè.
- Review gửi `question_bank_id`, nhiều `question_ids`; publish thêm `review_digest`, `title`, `course_id`, `confirmed=yes`, CSRF. Nếu nội dung thay đổi sau review thì backend từ chối, cần kiểm tra lại.
- sessionStorage key `linhedu:diagnostic-wizard:<userId>` giữ bank và metadata lựa chọn tối đa 1 giờ; **không giữ toàn bộ đáp án/review payload**. Restore quay về chọn câu và tái xác minh; pageshow từ back-forward cache làm vô hiệu review cũ.
- Có loading list/detail, retry detail, empty filter, reason blocked, hết phiên 401/redirect, 403, dữ liệu sai định dạng, lỗi review/publish; các thông báo/focus/disabled không được mất khi thay visual.

### 4.3. Làm bài và kết quả

- Form `#exam-form`, CSRF, hidden `time_spent_seconds`/`#time-spent-seconds`; mỗi `.tracked-question[data-question-id]` có `time_q_<q.id>`/`#time-q-<q.id>`; anchor `#q-<số thứ tự>` và nhãn `#question-label-<q.id>`.
- Single/multi: `q_<question_id>` với giá trị answer ID (multi gửi nhiều); Đúng/Sai: `q_<question_id>_ans_<answer_id>` giá trị `1|0`; ngắn: `q_<question_id>_text`. Không có upload bài làm; backend chủ động từ chối file.
- Alpine: `remaining`, `answered`, `totalQ`, `formattedTime`, `isWarning`; cảnh báo khi dưới 5 phút; mỗi GET khởi tạo countdown từ `duration_minutes`. `exam_take.js` chứa `confirmSubmit`, beforeunload và IntersectionObserver ghi thời gian nhìn câu.
- Kết quả truyền `single_view`, `submission|submissions`, `diagnostic_complete`, `can_decide`, `can_continue`; endpoint quay lại phụ thuộc standalone/practice. Lời giải toggle bằng `toggleExplanation`, `#exp-<id>`, `.btn-text`, gọi renderFormulas/MathJax và Lucide khi mở.
- Khi tiếp tục/kết thúc: POST CSRF đến route tương ứng, không dùng liên kết GET thay POST.
- Không nhầm `submission.is_graded=False` của dữ liệu lịch sử với một hàng đợi chấm tự luận hiện đang được hỗ trợ: template ghi rõ lịch sử không hỗ trợ chấm lại.

### 4.4. Tiến độ và theo dõi

- P01 chọn lớp GET `course_id`; tạo bài POST chỉ lớp và nguồn backend cho phép; CTA theo `profile_state`, `source_state`, `pending_decision_exam`, `resume_exam`, `teacher_papers`.
- P02 GET `subject`; canvas `#scoreChart`, `#accuracyChart`; `window.practiceProgressConfig` (history, masteryHistory, các accuracy); `initPracticeProgressCharts` tạo line/bar qua Chart.js CDN.
- T01 GET `course_id`; T02 GET `course_id`; anchors `#learning-results`, `#learning-support`, `#learning-history` đang có thể là đích điều hướng.
- T02 tạo draft POST: `course_id`, `bank_ids`, `chapters`, `sections`, `topics`, nhiều `cognitive_levels`, `mix_weak`, `mix_middle`, `mix_strong` (tổng phải 100), CSRF. `total_questions=22` hiển thị readonly; backend dùng blueprint, không tin giá trị sửa từ client.
- `teacher_practice_detail.js`: `#adaptive-course` với option `data-subject`, `.adaptive-bank[data-subject][data-course-counts]`, `.bank-count`; đổi lớp thì ẩn/disable/bỏ chọn bank ngoài quyền. Không chỉ lọc theo tên môn mà bỏ mất phạm vi lớp.
- T03 draft POST: `title`, `duration_minutes` (5–180), `is_active`, CSRF. Chỉ sửa thông tin phát hành; câu/nhãn/lý do lựa chọn đã đóng băng. Nội dung copy hiện nói “chỉnh sửa” cần làm rõ đúng giới hạn này trong UI mới.

## 5. Trạng thái nghiệp vụ cần phản ánh chính xác

| Luồng | Trạng thái đã thấy trong code | Ý nghĩa thiết kế |
|---|---|---|
| Kiểm tra standalone | Nháp → giao/active → có bài nộp; nội dung khóa khi active hoặc có submissions | Hiện trạng đơn giản này chưa phải hệ thống lịch giao đề nhiều trạng thái. `Exam.status_label` còn hỗ trợ upcoming/open/closed từ start/end nhưng editor hiện không có form lịch |
| Fixed practice | `active → submitting → awaiting_decision → generating → active` hoặc `ended`; phiên cũ có `superseded` | `submitting/generating` chủ yếu là trạng thái claim trong giao dịch, chưa có API polling UI trạng thái dài. Thiết kế loading theo request, không tự hứa nền xử lý async |
| Đầu vào | Assignment `assigned → grading → completed` theo service/runtime; graded submission + snapshot | Nộp/chấm/hồ sơ commit cùng giao dịch; lỗi rollback và yêu cầu nộp lại |
| Submission | Chưa nộp; graded/finalized; lịch sử không đủ điều kiện làm bằng chứng | “Có điểm” không đủ để mở Tiếp tục; `practice_decision_is_ready` còn đòi snapshot cùng bài, phiên/roster/course hợp lệ |
| Nguồn thay đổi | Bank/câu không còn được giáo viên hiện tại cho phép, thiếu nguồn hoặc thiếu quota | Chặn tạo/mở/phát hành phù hợp; kết quả lịch sử còn khả năng đọc theo quyền. Cần thông báo hành động cụ thể |
| Mở lại đề | P01/PGenerate tìm latest active session, đúng lớp/ngân hàng/student, chưa có submission đã nộp | **Có mở lại đề chưa nộp, chưa thấy lưu/khôi phục đáp án đang nhập.** Không dùng câu “đã lưu tiến trình làm bài” |
| Bằng chứng thiếu | `cold_start`, cell chưa đủ/sufficient, mastery absent | “Chưa biết” khác “Yếu”; không chuyển ô trống thành 0% hoặc kết luận yếu |

## 6. CSS, tài nguyên và thành phần dùng chung

Tất cả các template active kế thừa `base.html`: `main.css → learning.css → question-document.css → block head của trang → neo-pop.css`. A03/A04 thêm `assessments.css`; D02 thêm `diagnostic-wizard.css` trong block head, nên Neo Pop vẫn được tải sau các stylesheet này. Block scripts phía cuối cũng có thể tải stylesheet ở các trang khác. Do vậy không thể chỉ xóa `neo-pop.css` rồi coi là hoàn tất thiết kế mới.

| Nguồn | Tác dụng và điểm phải xử lý khi di chuyển |
|---|---|
| `main.css` | Card/form/button/table/score-ring và biến toàn cục; cần thay/chuẩn hóa, không giữ nguyên mọi phần vì trông gần theme đích |
| `neo-pop.css` | Đang cung cấp phần lớn bố cục/đáp án/timer/câu hỏi review; viền dày, bóng cứng; phải thay đủ hành vi responsive/focus trước khi bỏ file |
| `learning.css` | Audit selection/metrics/hero/report; có selector toàn cục `.main-area`, `.page-content` và media query thay cả shell; phải tách trách nhiệm trong CSS mới |
| `question-document.css` | Không chỉ câu hỏi/ngân hàng; còn `.learning-course-filter`, `.learning-details`, report và responsive. Không xóa theo tên file khi vẫn có consumer |
| `assessments.css` | Editor, sticky toolbar, ma trận; ma trận 7991 có `min-width:1500px` cần vùng cuộn rõ và xem nhỏ phù hợp |
| `diagnostic-wizard.css` | Stepper, selected bank/cards, loading/blocked và mobile; dùng trực tiếp biến `--ink`/`--pop-*`, cần thiết kế lại cùng wizard |
| Inline CSS/Jinja | Nhiều layout grid, màu trạng thái, font 10px và khoảng cách nằm trong E/R/P/T và component matrix; phải chuyển về component/token, không sót sau dọn stylesheet |
| `components/selection_audit.html` | Active trong take/result/draft; có conditional algorithm_version, explanation, quota/transfer/source limits. Có thể gọn UI nhưng phải giữ khả năng xem lý do thật |
| `components/practice_skill_matrix.html` | Active ở home/progress/detail; 8 dạng × 4 mức; distinct_count, session_count, sufficient/state; có màu inline và min-width 640px |
| `components/diagnostic_report.html` | Chưa thấy route/include active; còn được script `scripts/preview_personalization_v2.py` render và `tests/test_diagnostic_report_contract.py` kiểm tra. Chỉ dọn sau khi di chuyển hoặc cập nhật các consumer này |
| Formula + Alpine + icons | `formula_renderer.js`, MathJax/global renderFormulas, Alpine và Lucide từ base; cần giữ công thức, hình và thao tác khi thay markup |
| Chart.js | Riêng progress tải CDN chưa cố định version; JS còn hard-code màu, cần cập nhật theo hệ thống mới; dữ liệu điểm và mastery khác chuỗi cần rà soát trục |

## 7. Phát hiện cần ưu tiên trong thiết kế mới

Đây là quan sát/giả thuyết từ mã nguồn, chưa phải kết quả kiểm tra bằng mắt trên browser.

1. **Editor đề quá dài và phân cấp yếu:** toàn bộ câu/lời giải/nhãn nằm cùng một form dài với details lồng. Cần vùng thông tin đề, tổng quan điểm, điều hướng câu và khu vực biên soạn/preview dễ đối chiếu; action Lưu/Giao rõ.
2. **Tạo đề từ ngân hàng còn bảng lựa chọn thô:** thiếu bộ lọc nội dung/mức/kiến thức ngay ở A02, chưa thấy counter chọn/summary bám theo. Thiết kế phối hợp Phase 4; nếu thêm lọc server/paging phải lên hợp đồng mới, không làm giả chức năng.
3. **Danh sách đề chưa phản ánh hành vi người học:** học sinh dùng một CTA “Làm bài / xem kết quả”; giáo viên nháp/đã giao dùng `is_active`; chưa có phân trang/bộ lọc trong route. Cần phân cấp phù hợp dữ liệu thực và thống nhất badge trạng thái.
4. **Không gian làm bài chưa có điều hướng số câu dù có anchors:** một trang cuộn dài, lý do chọn bài có thể chen trước nội dung. Đề xuất bản đồ câu + trạng thái chưa/đang/đủ trả lời, timer gọn và nộp bài luôn dễ tìm trên mobile; giữ trải nghiệm đọc công thức rộng.
5. **Bộ đếm “Đã trả lời” hiện có khả năng sai:** Alpine chỉ set true; textarea xóa trắng/checkbox bỏ chọn không xóa key; chọn một ý Đúng/Sai đã tính cả câu. Phase triển khai cần xác định hoàn thành theo từng loại và tách trả lời một phần.
6. **Countdown và ghi thời gian cần kiểm tra:** mỗi lần tải lại countdown khởi tạo từ đầu. Hết giờ gọi `form.submit()` trực tiếp, trong khi ghi hidden thời gian nằm ở listener submit nên đường này có khả năng bỏ qua ghi time; setInterval có thể gọi submit lặp khi remaining=0. Cần kiểm chứng và xử lý đồng bộ trong phase làm bài; không gắn nhãn thời gian được bảo đảm bởi server nếu chưa có cơ chế ấy.
7. **Hướng dẫn đáp án ngắn có nguy cơ lệch cách chấm:** runtime chỉ gắn `_practice_short_rule` khi fixed practice, template dùng biến này; đầu vào/standalone vẫn chấm theo learning_metadata. Cần kiểm chứng numeric/text/tolerance ở đủ ba ngữ cảnh rồi thống nhất nguồn hiển thị.
8. **Nộp bài đang dùng browser confirm và chưa có nút submitting riêng:** cần tổng quan câu bỏ trống, xác nhận rõ ràng, phản hồi đang gửi/thành công/lỗi; backend đã có guard chống double-post và rollback. Không quảng bá autosave hoặc khôi phục đáp án khi chưa có.
9. **Kết quả cá nhân và danh sách nộp cùng template:** phải thiết kế hai bố cục; giải thích “tỷ lệ điểm đạt” khác “tỷ lệ câu đúng”, điểm một phần Đúng/Sai và bỏ trống cần nhãn không chỉ màu. Lịch sử chưa chấm cần tách khỏi kết quả hoàn tất.
10. **Tiến bộ đang trộn trình bày điểm và mastery:** Chart.js ghép masteryData vào trục nhãn theo history bài, chưa thấy join timestamp; empty score vẽ `[0]`. Cần thể hiện thiếu dữ liệu đúng và xác minh mapping, không biến chưa làm thành điểm 0.
11. **Theo dõi giáo viên cần ưu tiên hành động:** chọn lớp → học sinh cần hỗ trợ → evidence/lịch sử → liên kết báo cáo AI → tạo bài luyện. T01 điểm trung bình hiện loại standalone, trong khi số kiểm tra riêng vẫn hiển thị; UI phải ghi rõ cách tính.
12. **Toàn bộ CSS cũ phải được di chuyển có owner:** shadow/viền của Neo Pop, hero gradient, inline grid, sticky offsets 64/110px và responsive shell nhiều nơi đều là phạm vi thay. Kiểm tra small screen, focus không bị sticky che, tên dài, công thức/hình rộng, bảng ma trận lớn.

Các chuẩn review từ skill áp dụng cho web: label và lỗi rõ; trạng thái selected/disabled/expanded có ngữ nghĩa; trạng thái không chỉ dùng màu; focus không bị che; thông báo bất đồng bộ được đọc hợp lý; chiều rộng nội dung đọc và breakpoint nhất quán. Không áp dụng máy móc các quy tắc native về haptic/safe area/icon framework vào Flask web.

## 8. Kiểm thử hiện có và kế hoạch kiểm chứng sau

| Nhóm | File hiện có / trách nhiệm cần giữ |
|---|---|
| Kiểm tra standalone | `tests/test_standalone_assessment.py`: import/bank draft, lưu JSON, khóa/giao, quyền lớp, nộp một lần, bằng chứng standalone không thay adaptive mastery |
| Thang điểm/ma trận | `tests/test_assessment_scoring.py`, `tests/test_assessment_matrix.py`: tổng 10, budget/trọng số, legacy scale, missing labels, Excel/quyền, read-only |
| Học tập thống nhất | `tests/test_unified_practice_phase3.py`: một điểm vào, đầu vào theo assignment, đúng nguồn lớp, mở lại đề không tạo thêm |
| Giao dịch nộp | `tests/test_learning_loop_phase4.py`: double-post, rollback evidence failure, Đúng/Sai một phần, rebuild draft diagnostic, snapshot mới cho phép quyết định |
| Blueprint/tiếp tục | `tests/test_practice22.py`, `tests/test_practice_same_level_transfer.py`: 22 câu/điểm, continue/end, nguồn không còn hợp lệ, không hạ mức/đổi loại khi thiếu câu |
| Theo dõi | `tests/test_learning_workspace.py`, `tests/test_class_lesson4_report.py`: học sinh chưa có dữ liệu, evidence quan sát, giới hạn lớp/lịch sử và liên kết |
| Đầu vào/xóa/lời giải | `tests/test_diagnostic_delete_and_explanation.py`, `tests/test_diagnostic_report_contract.py`; các test diagnostic cũ cần đối chiếu route hiện tại |
| Route contract | `tests/test_route_contract.py`: fixture không tự coi là chính xác. Inventory toàn dự án đã phát hiện drift giữa fixture 79 endpoint và AST 94 endpoint; cần cập nhật baseline đúng scope trước khi dùng làm gate |

**Mâu thuẫn tĩnh cần xác minh:** `tests/test_diagnostic_phase2.py` còn POST `/diagnostics/new` bằng teacher và kỳ vọng thành công, trong khi handler hiện chỉ admin. Đây có thể là test theo cơ chế tác giả cũ; không thiết kế lại quyền theo test cũ khi chưa quyết định nghiệp vụ. Dữ liệu lịch sử/decorator/admin cũng cần giữ tương thích có chủ ý.

Các test trên chưa được chạy trong Phase 1. Khi thực hiện giao diện, chạy trong DB test riêng sau khi kiểm tra fixture/setup, không dùng DB thật. Test cần bảo vệ hành vi/ngữ nghĩa, tránh buộc giữ class trang trí cũ hoặc ảnh snapshot theme cũ.

Checklist runtime cần làm ở các phase triển khai:

- Ba ngữ cảnh take: standalone, initial_diagnostic, fixed practice; dữ liệu lịch sử và submission chưa chấm.
- Đủ vai trò, lớp trong/ngoài quyền, teacher chuyển lớp, nguồn private/shared bị thay đổi, enrollment hết hiệu lực.
- Câu đơn/nhiều/Đúng-Sai partial/bỏ trống/ngắn numeric/text, công thức, ảnh, nội dung dài; hướng dẫn và điểm khớp backend.
- Giao/khóa/lưu lỗi/dirty; review digest bị thay đổi; loading/retry/khôi phục selection wizard; submit lỗi, double click, hết giờ.
- Tiếp tục/kết thúc/mở lại đề; không ngụ ý lưu đáp án nếu không có; kết quả historical vẫn đọc theo quyền.
- 375/768/1024/1440px, keyboard/focus/zoom/reduced-motion, bảng cuộn và nội dung in/Excel.

## 9. Đầu ra chuyển sang Phase 2

1. Wireframe ưu tiên: A02 chọn câu từ ngân hàng, A03 editor, A01 danh sách đề, E01/E02/E03 workspace làm bài, R01/R02 kết quả.
2. Hợp đồng thành phần: page header, filter toolbar, list/table, question content, choice group, truth group, short answer, state badge, sticky actions, confirmation, async feedback, result breakdown, knowledge matrix.
3. Trạng thái mẫu có dữ liệu và thiếu dữ liệu ở đủ vai trò; tuyệt đối bao gồm màn hình đã dùng `main.css`, không chỉ phần Neo Pop.
4. Quyết định cần chốt trong thiết kế: cách điều hướng nhiều câu; phân cấp editor và review; phân biệt câu trả lời partial; dữ liệu trục biểu đồ; cách biểu thị đề lịch sử/chưa chấm. Các thay đổi API/khôi phục đáp án hoặc lịch giao bài phải được ghi là scope chức năng bổ sung nếu cần.
5. Bản đồ xóa/migrate: stylesheet + selector + DOM hook + include + script/test consumer tương ứng, để Phase 9 có thể xóa sạch code giao diện cũ mà vẫn giữ luồng nghiệp vụ.

Phase 1 kết thúc ở việc kiểm kê và tài liệu này; chưa xây mockup hoặc viết UI mới.
