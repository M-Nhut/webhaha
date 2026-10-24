# Phase 1 — Khung chung, tài nguyên và kế hoạch dọn giao diện cũ

Ngày kiểm kê: 13/10/2026. Đây là quan sát mã nguồn và yêu cầu chuyển đổi; chưa chạy ứng dụng hoặc kiểm tra trực quan trong trình duyệt. Không có tài nguyên giao diện nào bị sửa/xóa trong Phase 1.

## 1. Cách giao diện hiện tại được ghép

`templates/base.html` dựng shell qua `components/navigation.html`, `header.html`, `flash_messages.html`, rồi vùng `#main-content`; `components/footer.html` thực chất là nơi nạp thư viện và chạy khởi tạo. Không coi file footer là một footer nội dung cần thiết kế mới.

Thứ tự stylesheet của shell hiện tại:

1. `main.css`: nền tảng và theme Modern White Academy cũ.
2. `learning.css`: style học tập nhưng có cả quy tắc shell/mobile toàn ứng dụng.
3. `question-document.css`: style câu hỏi, nội dung toán và nhiều quy tắc trình bày.
4. Nội dung block `head` của trang con: một số stylesheet chức năng được nạp tại đây.
5. `neo-pop.css`: ghi đè theme chung và cả nhiều thành phần theo trang.

Không phải mọi trang đều có cùng thứ tự: `question_bank_detail.html` và một số trang ngân hàng nạp stylesheet trong block `scripts`, nằm sau footer và theme. `login.html` độc lập nạp `main.css → neo-pop.css → login.css`; `register.html` và layout lỗi cũng tự nạp style. Vì vậy không thể chỉ xóa `neo-pop.css` rồi coi việc thiết kế đã hoàn tất.

Các layout độc lập cần chuyển riêng: đăng nhập, đăng ký và lỗi HTTP. Mọi màn hình nghiệp vụ kế thừa base cũng cần được thiết kế lại cả phần nội dung.

## 2. Đo lường mã giao diện hiện có

| Hạng mục | Số lượng | Ý nghĩa |
|---|---:|---|
| File CSS ứng dụng | 12 | Tổng 3.305 dòng nguồn; một số file bị nén trên rất ít dòng |
| `!important` trong CSS | 173 | Trong đó `question-document.css`: 99, `neo-pop.css`: 45 |
| File JavaScript ứng dụng | 17 | Tổng 2.998 dòng, không tính thư viện vendor |
| `style=` trong template | 788 | Đếm từ mã nguồn, gồm cả template chưa thấy dùng trong runtime |
| Khối `<style>` trong template | 2 | `question_bank_import.html`, `errors/error.html` |
| Khối script inline trong template | 16 | Gồm cả cấu hình và bootstrap dữ liệu; không phải tất cả đều cần xóa |

Các file nhiều style trực tiếp: `question_bank_import.html` (138), `question_bank_detail.html` (137), `components/diagnostic_report.html` (61, script/test còn dùng), `exam_result.html` (53), `course_detail.html` (42), `practice_progress.html` (42). Đây là chỉ số ưu tiên chuyển đổi, không chứng minh lỗi hiển thị bằng số lượng.

## 3. Danh mục CSS và trách nhiệm chuyển đổi

| File hiện tại | Bên dùng trực tiếp | Hướng xử lý khi triển khai |
|---|---|---|
| `static/css/main.css` | Base, login, register, layout lỗi | Thay nền tảng và thành phần theo hệ thống mới; không giữ nguyên bộ theme cũ vì có màu trắng |
| `static/css/neo-pop.css` | Base, login, register, layout lỗi | Loại bỏ toàn bộ khi các trang đã có style mới; xóa mọi link và selector đi kèm |
| `static/css/learning.css` | Base, được tải toàn ứng dụng | Tách phần học tập khỏi shell/mobile; viết lại theo token mới, bỏ ghi đè theme cũ |
| `static/css/question-document.css` | Base, được tải toàn ứng dụng | Tách quy tắc bố cục/math cần thiết và style trang; thiết kế lại vùng đọc câu hỏi, đáp án, lời giải |
| `static/css/login.css` | Login | Viết lại layout đăng nhập; bỏ bóng cứng, viền đậm và token theme riêng |
| `static/css/question-bank.css` | Chi tiết ngân hàng | Viết lại ma trận, phân trang, toolbar, loading/error và vùng chi tiết |
| `static/css/id6.css` | Chi tiết ngân hàng, phân loại, nhập câu hỏi | Chuẩn hóa bộ chọn kiến thức theo hệ thống form mới |
| `static/css/import_scope.css` | Trang nhập câu hỏi | Kiểm tra phần scope đã bỏ và phần `.import-steps` vẫn dùng; chỉ giữ style còn có chức năng |
| `static/css/import_duplicates.css` | Trang nhập câu hỏi | Thiết kế lại đối chiếu trùng và thao tác nhập; giữ trạng thái nghiệp vụ |
| `static/css/diagnostic-wizard.css` | Tạo đánh giá đầu vào | Chuyển stepper, chọn câu, trạng thái review sang thành phần mới |
| `static/css/assessments.css` | Biên soạn đề nhập, ma trận | Viết lại layout editor/ma trận và bổ sung thiết kế đồng bộ các màn hình đề khác |
| `static/css/ai-reports.css` | Báo cáo AI | Viết lại bố cục, bảng bằng chứng, tabs và trạng thái phân tích |

Tất cả 12 CSS đều có template gọi hiện tại. Không đánh dấu một CSS là file chết chỉ vì nó ngắn hoặc tên cũ. Việc giữ tên file sau chuyển đổi là quyết định kỹ thuật Phase 2–3; tiêu chí là chỉ còn hệ thống style mới, không chồng theme.

## 4. Danh mục JavaScript và hợp đồng cần bảo toàn

| File | Bên dùng/trách nhiệm hiện tại | Yêu cầu khi đổi markup |
|---|---|---|
| `ui-shell.js` | Base: menu mobile, fallback avatar, `aria-current` | Giữ hoặc cập nhật đồng bộ `.sidebar`, `.sidebar-toggle`, `.nav-item.active`, `aria-controls/expanded`, breakpoint JS/CSS |
| `login.js` | Login: hiện/ẩn mật khẩu | Bảo toàn `data-password-toggle`, `aria-controls`, password input, trạng thái khi rời trang |
| `formula_renderer.js` | Base: công thức, bảng TeX, ảnh câu hỏi | Bảo toàn `window.renderFormulas`, `window.FormulaRenderer`, MathJax, API công thức và các placeholder |
| `bank_formula_scheduler.js` | Chi tiết ngân hàng và tạo đánh giá đầu vào | Giữ cơ chế xử lý công thức theo vùng nhìn thấy, `data-bank-lazy-formulas`; tránh render toàn bộ ngân hàng cùng lúc |
| `id6_picker.js` | Chi tiết/phân loại/nhập ngân hàng | Giữ bộ chọn ba hình thức câu hỏi, data bootstrap và nhãn kiến thức |
| `manual_question.js` | Thêm câu thủ công trong ngân hàng | Giữ preview TeX và hợp đồng với form/Alpine |
| `import_scope.js` | Trang nhập, còn có test JS | Có logic scope cũ; đối chiếu method còn gọi trước khi loại bỏ mixin/file |
| `import_duplicates.js` | Trang nhập, còn có test JS | Giữ session, đối chiếu câu trùng, đổi đích và chọn câu nhập |
| `modules/import_wizard.js` | Wizard nhập `.tex` | Giữ step/state, file/session, payload và xử lý lỗi; chuyển UI từng bước có kiểm chứng |
| `modules/question_bank_detail.js` | Mở/đóng chi tiết câu hỏi và chỉnh sửa | Giữ lazy fetch, trạng thái bận/lỗi, edit/delete/answer actions và data attributes |
| `modules/assessment_editor.js` | Biên soạn đề nhập | Giữ xem trước, lưu nội dung/điểm, thông báo lỗi và link ma trận |
| `modules/exam_take.js` | Làm bài dùng chung | Giữ thời gian hiện có, submit guard và field đáp án; không quảng cáo autosave nếu backend chưa có |
| `modules/diagnostic_wizard.js` | Tạo đánh giá đầu vào | Giữ fetch lựa chọn câu, review đề, counts và điều kiện tạo đề |
| `modules/practice_progress.js` | Tiến độ tự luyện | Giữ tabs/filter/data và liên kết chi tiết; kiểm tra render công thức sau cập nhật |
| `modules/teacher_practice_detail.js` | Chi tiết học tập học sinh | Giữ các nút phân tích và trạng thái loading/failure |
| `modules/ai_reports.js` | Báo cáo AI lớp/cá nhân | Giữ chọn lớp/học sinh, request/polling, quyền generate/review, phân biệt observed/AI |
| `modules/class_learning_report.js` | Không thấy template hoặc loader nguồn gọi file | Ứng viên dọn sau xác minh; không xóa các API/service báo cáo còn hoạt động |

Chi tiết các ID, `data-*`, field names và directive Alpine theo từng template được ghi trong `phase-1-inventory.json`. Danh sách đó là điểm xuất phát cho kiểm tra tương thích; cả JS và template phải được đọc cùng nhau vì nhiều node được tạo động.

## 5. Thành phần chung cần thiết kế lại

| Nhóm | Phạm vi | Trạng thái bắt buộc |
|---|---|---|
| Shell | Navigation, page header, tài khoản, breadcrumb nếu cần | Active, mobile mở/đóng, tiêu đề dài, phân quyền |
| Nút và thao tác | Primary/secondary/quiet/destructive, icon button, menu hành động | Hover, focus, pressed, disabled, busy |
| Form | Input, textarea, password, select, checkbox/radio, file upload | Label/hint, error, readonly, disabled, submit thành công/thất bại |
| Dữ liệu | Table, list, filters, search, tabs, pagination, chọn nhiều | Có dữ liệu, rỗng, không có kết quả, đang tải, lỗi, chọn toàn trang/phạm vi rõ |
| Nội dung toán | Câu hỏi, đáp án, Đúng/Sai, trả lời ngắn, lời giải, hình/bảng | Công thức dài, pending/fallback/error, preview và kết quả |
| Overlay | Modal thêm/sửa/chọn câu, xác nhận thao tác | Mở/đóng, focus vào/ra, Escape, lỗi không mất dữ liệu |
| Phản hồi | Flash, inline status, cảnh báo, xác nhận | Success/warning/error/info, thời gian đọc đủ, đóng có tên truy cập |
| Tiến trình | Wizard/stepper, trạng thái lưu/chấm/phân tích | Current/completed, bận, thử lại, bị khóa theo nghiệp vụ |
| In/xuất | Ma trận, kết quả và nội dung đề | Màu trắng, ngắt trang, ẩn điều hướng và nút không phục vụ in |

Những trạng thái có trong thiết kế mục tiêu không có nghĩa tất cả đã được backend hỗ trợ. Chức năng mới phải được tách khỏi phạm vi thay đổi UI.

## 6. Kế hoạch loại bỏ có chứng cứ

| Ứng viên | Chứng cứ hiện có | Điều kiện trước khi xóa | Phase |
|---|---|---|---|
| Theme Neo-Pop, biến `--pop-*`, bóng cứng, logo float | `neo-pop.css` đang được nạp ở 4 layout; nhiều class/selector nằm trong template | Mọi layout/partial được chuyển; xóa tất cả link, selector và markup chỉ phục vụ theme; không xóa logic cùng tên có chức năng | 3–8, kết thúc 9 |
| Phần theme cũ trong `main.css` | Base còn dùng, reset/layout/form/table vẫn phụ thuộc | Thay bằng nền tảng mới rồi rà soát người dùng; không xóa toàn file trước khi thay | 2–8 |
| `teacher_analytics.html` | Không thấy render/include; endpoint `/analytics/teacher` hiện redirect | Kiểm tra không có bên dùng ngoài route; giữ endpoint redirect tương thích, gỡ template/tests chỉ dành cho màn hình cũ nếu có | 9 |
| `components/diagnostic_report.html` | Không có route/include trực tiếp; script preview và test vẫn render | Chuyển hoặc loại script preview/test tương ứng có chủ đích; giữ contract/service báo cáo còn dùng | 7 + 9 |
| `components/import_scope.html` | Không thấy include trong template runtime | Đối chiếu scope hiện tại với wizard, test, JS mixin; không nhầm UI scope cũ với phân quyền/session scope backend | 5 + 9 |
| `modules/class_learning_report.js` | Không thấy literal loader; các node con `#lesson4-report-*` mà script cần không còn trong template. `#lesson4-ai-report` vẫn là anchor card liên kết sang báo cáo riêng | Xác nhận trang AI hiện tại đã bao phủ nhiệm vụ; giữ anchor/link và các endpoint lesson4-report còn phục vụ báo cáo mới | 8 + 9 |
| HTMX và listener `htmx:afterOnLoad` | Footer tải HTMX; không thấy `hx-*` hoặc lệnh gọi HTMX trong template/JS ứng dụng hiện tại | Xác minh không có nội dung động sử dụng HTMX trước khi gỡ loader/listener; Alpine vẫn đang dùng | 3 + 9 |
| `static/images/pop-study.svg` | Đang được trang đăng ký dùng | Thiết kế lại trang đăng ký, gỡ tham chiếu rồi mới xóa asset phong cách cũ | 3 |
| `static/images/pop-avatar.svg` | Base và sidebar dùng làm fallback | Cung cấp fallback avatar mới và sửa cả HTML/JS trước khi xóa | 3 |
| `static/images/logo.png` | Chưa thấy literal reference trong nguồn ứng dụng đã quét | Đối chiếu dữ liệu/tham chiếu ngoài code và ý nghĩa thương hiệu trước khi gỡ; giữ logo-transparent hiện dùng | 9 |
| `static/favicon.ico`, `static/images/favicon.ico` | Không được template gọi; `/favicon.ico` trả PNG logo-transparent | Xác minh không còn deployment/browser asset URL phụ thuộc; tên favicon vẫn có thể được gọi trực tiếp | 9 |
| CSS `style=` và `<style>` inline | 788 `style=`/2 khối `<style>` trong template | Chuyển style tĩnh sang thành phần/trang; xử lý riêng style động phụ thuộc dữ liệu; không xóa hàng loạt bằng regex | Theo màn hình |
| Tài liệu `docs/neo-pop-design.md`, `docs/login-logo-edit.md` | Mô tả thiết kế trước chuyển đổi | Chuyển thông tin cần giữ sang tài liệu mới và xóa tài liệu hướng dẫn theme đã bỏ ở phase dọn cuối, tránh hai nguồn hướng dẫn trái nhau | 9 |

Các ứng viên trên chưa bị xóa trong Phase 1. Tài nguyên vendor, `uploads`, avatar người dùng, ảnh lớp/câu hỏi và TeX cache là thư viện hoặc dữ liệu; không coi là rác giao diện theo tên hoặc vì không có link tĩnh trong template.

## 7. Tài nguyên và hành vi cần giữ khi chuyển giao diện

- Logo `static/images/logo-transparent.png` hiện dùng trong shell, tổng quan, login/register, trang lỗi và route favicon. Giữ tỉ lệ và nguồn ảnh; bỏ animation thuộc theme cũ khi triển khai.
- Alpine local phục vụ nhiều `x-data/x-model/x-show` và modal, không được gỡ như tài nguyên theme.
- MathJax local và 26 file vendor hiện có cần được kiểm tra theo dependency; không xóa font toán vì không thấy URL trong HTML.
- Font Nunito từ Google Fonts, Lucide `@latest`, HTMX và Chart.js ở trang progress từ CDN là các dependency hiện tại. Chart.js chưa cố định version. Font mới, cách lưu cục bộ/pin version là quyết định Phase 2–3; Phase 1 chưa thay dependency. Inventory ghi URL ngoài cùng template/line sử dụng, tách preconnect khỏi file JS/CSS theo mục đích của tag.
- Meta `csrf-token`, token trong form và header `X-CSRFToken` của fetch phải đồng bộ.
- `window.MathJax` được cấu hình trước script thư viện, `renderFormulas` được gọi sau startup và sau các vùng nội dung thay đổi. Không phá thứ tự này khi tách JS.
- Breakpoint shell JS đang ở 800px, CSS có nhiều mốc 540/600/680/700/720/768/800/850/900/992/1024/1180/1200. Cần thống nhất theo layout thực tế ở Phase 2; chưa kết luận có lỗi vỡ layout khi chưa xem trình duyệt.
- Print và reduced-motion có rule hiện tại. Thiết kế mới phải có hành vi tương ứng, không mất khi xóa theme cũ.

## 8. Áp dụng ui-ux-pro-max trong kiểm kê

Đã đọc skill `ui-ux-pro-max` và dùng tìm kiếm cục bộ `keyboard focus modal --domain ux`; kết quả đúng nhóm Interaction/Accessibility, phù hợp với modal và thanh cố định của web hiện tại. Yêu cầu đưa vào kiểm chứng: focus nhìn thấy; overlay/sticky không che hoàn toàn phần tử đang focus; ưu tiên giữ toàn bộ phần tử focus trong vùng nhìn thấy. Skill là nguồn hướng dẫn UX, không thay thế việc đọc contract hiện có.

Không áp dụng máy móc các quy tắc dành riêng iOS/Android như safe-area/Dynamic Type hay thay icon theo khuyến nghị native. Thiết kế web mới tiếp tục dùng Lucide và hướng Modern White Academy theo yêu cầu người dùng. Hệ thống token và bản mẫu thuộc Phase 2.
