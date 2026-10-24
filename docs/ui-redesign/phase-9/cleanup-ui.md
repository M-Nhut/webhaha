# Dọn giao diện và đồ thị consumer Phase 9

Ngày xác minh: **19/10/2026**. Chỉ dọn mã giao diện đã hết consumer; không đổi thiết kế Modern White Academy đã duyệt, route, quyền, dịch vụ, nguồn câu hỏi hoặc chấm điểm.

## Phần đã xóa

| Đối tượng | Chứng cứ và xử lý |
|---|---|
| `templates/teacher_analytics.html` | Không có `render_template`, include/extends/import Jinja, script preview hoặc test đọc tên file. Hàm `teacher_analytics` trong `routes/practice.py` chỉ chuyển hướng tới danh sách/chi tiết theo dõi học tập. Giữ nguyên URL tương thích `/analytics/teacher`; xóa template bỏ dùng và 26 thuộc tính style inline của nó. |
| 37 alias token chuyển tiếp cuối `tokens.css` | Toàn bộ template, CSS, JS, route và service đang dùng không còn tham chiếu. Xóa cả khối `during the phased migration`; giữ nguyên ba lớp primitive, semantic, component của bộ token mới. Danh sách từng alias và token thay thế có trong JSON. |
| 20 tên class hết consumer | Xóa alias/style cũ ở `base.css`, `components.css`, `pages/import-wizard.css`: `visually-hidden`, `text-small`, `text-success`, `text-right`, `text-center`, `btn-new-course`, `btn-success`, `card-header`, `card-title`, `panel-heading`, `table-container`, `badge-active`, `badge-open`, `badge-inactive`, `badge-closed`, `form-errors`, `warning-light-bg`, `danger-light-bg`, `success-light-bg`, `formula-zoom-control`. Tìm theo ranh giới tên đầy đủ trong cả nguồn sinh markup trước khi xóa; số tham chiếu còn lại là 0. |
| `static/js/.DS_Store` | Metadata Finder, không phải tài nguyên ứng dụng. Các metadata khác được kiểm tra trong báo cáo toàn hệ thống. |

`main.css` tiếp tục chỉ là điểm import năm lớp nền tảng mới. URL cache của CSS nền tảng trong base/login/register/error và renderer công thức được tăng lên `20261019-phase9`; CSS import wizard dùng `20261018-phase9`. Không bổ sung theme dự phòng hoặc bản sao giao diện cũ.

## Thành phần công thức và phóng to ảnh dùng chung

Lượt kiểm tra producer JS cuối phát hiện sáu phép gán style cố định còn giữ màu/lớp trình bày cũ trong `formula_renderer.js`: nền/hình lightbox, lỗi đỏ, nút thử lại và hai nhánh gạch chân cần kiểm tra. Các style này chuyển sang class có phạm vi trong `question-content.css`, dùng token của giao diện mới. Bỏ class `fst-italic` chưa có định nghĩa khỏi producer lỗi. Các kích thước intrinsic inline/block của công thức và căn ô bảng theo dữ liệu được giữ.

Lightbox hiện dùng native `dialog`, có tên truy cập, tiêu đề/nút Đóng, Tab và Shift+Tab trong dialog, Escape và click backdrop để đóng rồi trả focus về ảnh mở. `FormulaRenderer.openImageLightbox` vẫn là API mà trang ngân hàng/nhập gọi; giữ toàn bộ URL ảnh, công thức, MathJax và fallback. Thử lại vẫn POST cùng endpoint cho công thức lưu hoặc import tạm, kèm CSRF và quyền hiện có.

Đã chạy **86 kiểm tra trình duyệt đạt** ở 375/768/1024/1440px, gồm click/Enter/Space trên ảnh thực của bank, ảnh hiển thị đủ, modal keyboard/return focus, chiều rộng/chiều cao, màu token lỗi/cần kiểm tra, inline/block, MathJax, bảng TeX, control thử lại 44px trên mobile, thành công/lỗi POST, nhánh import tạm và nhánh chỉ đọc không hiện thử lại. Mười hai POST thử lại được intercept và trả dữ liệu tổng hợp trong trình duyệt; không gọi backend/provider. Không có page error. Đã xem trực tiếp ảnh chụp 375/1440px.

Chứng cứ: [QA công thức và ảnh](cleanup-formula-browser.json); ảnh ở `screenshots/cleanup-formula-zoom-{375,768,1024,1440}.png`. Dữ liệu trạng thái công thức chỉ được gắn vào DOM thử nghiệm; click ảnh dùng câu hỏi và handler ngân hàng thật trong preview cô lập.

## Phần cần giữ sau khi kiểm tra consumer động

- `flash-{{ category }}` và `auth-notice-{{ category }}` sinh class theo thông báo backend; giữ cả success/error/danger/warning dù một vài tên không có literal hoàn chỉnh.
- `badge-present`, `badge-absent`, `badge-upcoming` được JS báo cáo AI sinh theo đúng/sai/một phần; các class trạng thái Alpine, DOM, drawer và nhánh không có JS vẫn hoạt động.
- `import_scope.js` còn mixin `restoreImport` trong wizard nhập hiện tại. Không xóa helper này cùng partial form phạm vi đã bị loại ở Phase 5.
- `question-content.css`, `question-document.css`, renderer công thức, MathJax, bảng TeX, hình công thức, retry/zoom và scheduler có consumer thật. Renderer ảnh dùng `document-image-zoomable`; rule `formula-zoom-control` không còn producer nên được xóa riêng.
- Avatar tải lên, ảnh câu hỏi đã đóng băng, công thức/hình LaTeX được tạo, vendor/font và API không bị đánh giá là mã chết bằng phép dò tên file literal. Việc kiểm tra các tài nguyên động ghi riêng trong báo cáo toàn hệ thống.
- Các partial/script cũ `components/import_scope.html`, `components/diagnostic_report.html`, `class_learning_report.js` và `pages/workspaces.css` đã được dọn ở Phase 5/8. Phase 9 xác nhận chúng không xuất hiện lại; không xóa dịch vụ/API hoặc adapter dữ liệu lưu trữ liên quan.

## Kết quả kiểm chứng tĩnh

Đồ thị dùng AST Python cho handler render, AST Jinja cho include/extends/import và asset `url_for`, rồi lần theo CSS `url()`/`@import`. Đã đọc nhánh `errors/{status_code}.html` và fallback master để bổ sung consumer động, không kết luận các trang lỗi không dùng từ việc thiếu literal.

| Phạm vi | Kết quả |
|---|---:|
| Template đang dùng | 49: 32 trang, 10 component, 6 template lỗi, 1 base |
| Template không thể đi tới từ handler/include | 0 |
| Template parse/include hoặc asset literal/CSS URL bị thiếu | 0 |
| CSS ứng dụng có consumer, parse bằng tinycss2 | 31/31 đạt |
| JavaScript ứng dụng có consumer, `node --check` | 32/32 đạt |
| Biến CSS chưa có định nghĩa trong CSS ứng dụng | 0 |
| Tham chiếu token/class đã xóa | 0 |
| `style=` hoặc `<style>` trong template đang dùng | 0/0 |

Chứng cứ: [đồ thị và từng quyết định giữ/xóa](cleanup-runtime-inventory.json), [parse CSS](cleanup-css-syntax.json), [cú pháp JavaScript](cleanup-js-syntax.json). Những tài liệu kiểm kê Phase 1 là ảnh chụp lịch sử, vì vậy vẫn nhắc các tên file đã xóa.

Đồ thị nguồn không thay thế nghiệm thu tương tác. Đối chiếu báo cáo Phase 9 chính để xem kiểm tra trình duyệt toàn bộ màn hình, quyền, CSRF, bàn phím, reduced motion, công thức, bản in/Excel và hồi quy. Phần dọn selector/token đã được kiểm tra trong lượt trình duyệt toàn hệ thống; phần dialog/công thức bổ sung được kiểm tra riêng ở bốn kích thước sau đó. Runtime đã đóng băng sau lượt QA bổ sung này.
