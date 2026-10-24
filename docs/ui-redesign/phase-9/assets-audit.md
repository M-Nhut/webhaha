# Phase 9 — tài nguyên, bản xem thử và hướng dẫn

Kiểm kê bắt đầu 18/10, hoàn tất 19/10/2026. Phạm vi này không import ứng dụng, đọc `.env`/DB thật, gọi AI hoặc thay dữ liệu người dùng. Chi tiết máy đọc được nằm trong [assets-audit.json](assets-audit.json); kiểm chứng hệ thống và nghiệm thu giao diện nằm trong báo cáo Phase 9 chính.

## Đã gỡ

| Tệp | Chứng cứ và phần thay thế |
|---|---|
| `scripts/preview_assessment.py` | Bản xem đề tạm thời import test fixture; không có consumer runtime. Dùng fixture kiểm tra/import Phase 5–6 và bản xem thử tổng hợp Phase 9. |
| `scripts/preview_duplicate_review.py` | Bản xem dò trùng đơn lẻ import test fixture; không có consumer runtime. Fixture Phase 5 hiện có đầy đủ đối chiếu, resume và receipt. |
| `scripts/preview_general_bank.py` | Xuất HTML vào `tmp/general-preview`, sửa URL của vùng báo cáo cũ. Bản xem thử hiện tại render template và API hiện hành trực tiếp. |
| `scripts/preview_latex_v3.py` | Đọc tài liệu giáo viên ngoài repo, xuất HTML vào `tmp/v3-preview`, chèn hook wizard `QA_PREVIEW`/`acceptDuplicateData` cũ. Tham chiếu hướng dẫn duy nhất trong tài liệu LaTeX đã chuyển sang fixture tổng hợp. |
| `docs/neo-pop-design.md` | Hướng dẫn theme đã gỡ: `neo-pop.css`, palette, minh họa, Nunito/Google Fonts và hành vi trang cũ. Quy chuẩn hiện hành là MASTER được duyệt. |
| `docs/login-logo-edit.md` | Prompt sửa logo và mô tả CSS đăng nhập cũ. Logo thương hiệu hiện dùng vẫn giữ nguyên; hướng dẫn hiện hành trỏ MASTER. |

Không giữ bản sao CSS/template cũ trong thư mục chạy. Tài liệu kiểm kê, prototype được duyệt, ảnh và báo cáo Phase 1–8 được giữ làm bằng chứng có mốc thời gian, theo chú thích trong README. Những văn bản lịch sử nhắc tên tệp đã xóa không phải consumer của ứng dụng.

## Quyết định giữ

| Tài nguyên | Lý do |
|---|---|
| `static/images/logo-transparent.png` | Logo hiện tại của shell, tài khoản, trang lỗi; `/favicon.ico` trả PNG này. |
| `static/images/avatar-default.svg` | Fallback hiện hành cho avatar mặc định và filename từ dữ liệu người dùng. |
| `static/images/logo.png` | Nguồn logo thương hiệu và URL công khai cũ; không phải lớp theme. |
| `static/favicon.ico`, `static/images/favicon.ico` | Giữ tương thích URL tài nguyên công khai; trình duyệt có thể gọi trực tiếp ngoài literal template. |
| `static/avatars`, `static/course_images`, `static/uploads`, `uploads` | Media và nguồn nhập có tên được lưu động trong DB. Không dùng phép tìm literal để quyết định xóa. |
| `static/fonts`, `static/vendor`, `vendor/tex`, `node_modules` | Font, MathJax/Alpine/Lucide/Chart.js, giấy phép và worker TeX/WASM cục bộ còn hoạt động. Font MathJax được tải động theo công thức nên giữ trọn bộ. |
| `scripts/preview_ui_phase3.py` đến `preview_ui_phase8.py` | Còn consumer test/helper/QA; dùng fixture tổng hợp nhưng render template hiện hành. Ví dụ Phase 8 nhập seed Phase 7, Phase 7 nhập seed Phase 4 và isolation Phase 5. JSON ghi từng consumer. |
| `legacy/latex_renderer_service` | Backend compiler cũ được README đánh dấu lưu trữ, không thuộc giao diện và không được web hiện tại import. Giữ phạm vi thay đổi không liên quan. |
| `outputs/matrix7991` | File Excel và ảnh xác minh trước đây; không phải bản giao diện thay thế. |

52 tệp font/vendor/brand/TeX không phải metadata trong baseline có SHA-256 giữ nguyên tại lần kiểm kê. `.DS_Store` chỉ là metadata Finder, không thuộc tài nguyên chức năng; quyết định dọn được ghi riêng trong báo cáo tổng.

## Kiểm tra tài nguyên và hướng dẫn hiện hành

`scripts/build_local_assets.cjs --check` xác minh 26 tệp quan trọng gồm nền tảng CSS, JS shell/dialog/toán, logo/avatar, bốn độ đậm font và giấy phép, thư viện cục bộ và package worker. Chế độ này không sao chép vendor, không ghi `.latex-node-path` và không tải thư viện. Chế độ build thông thường vẫn giữ hành vi cập nhật MathJax/Alpine từ `node_modules` nếu có và ghi vị trí Node đã xác minh.

Lệnh kiểm tra đạt, exit code 0. Đối chiếu 106 checksum tệp static không phải upload và `.latex-node-path` trước/sau lệnh không có thay đổi. README gốc và tài liệu LaTeX đã trỏ bản xem thử tổng hợp hiện hành ở cổng 8771; bản này không yêu cầu tài liệu giáo viên ngoài repo.

## An toàn khi khám phá bộ kiểm thử

[Inventory 59 module đầu vào](test-safety-inventory.json) ghi import, marker mạng và marker cô lập; marker chỉ phục vụ kiểm kê, không chứng minh một module an toàn khi chạy riêng. `test_error_pages.py` import ứng dụng trực tiếp, `test_route_contract.py` chỉ đặt mặc định DATABASE_URL; không được dựa vào thứ tự pytest để tránh đọc cấu hình thật.

Runner toàn hệ thống cần đặt DB bộ nhớ, chặn nạp môi trường cục bộ và chuyển thư mục ghi sang thư mục tạm trước lần import ứng dụng đầu tiên; xác nhận URI trước khi collection. Dùng guard chặn HTTP thật, giữ fake session của các test AI. Các test migration gọi CLI với đường dẫn DB tạm chỉ định rõ; test công thức dùng worker Node/WASM cục bộ và cần chuyển `latex_renderer.ASSET_DIR`, thư mục ảnh và import tạm trước collection. Kết quả chạy thực tế và các sai lệch baseline do runner chính báo cáo, không suy ra từ inventory tĩnh này.
