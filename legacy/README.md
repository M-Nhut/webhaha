# Mã triển khai cũ

`latex_renderer_service/` là dịch vụ Docker/API trước đây, được lưu lại để tra cứu và giữ các thay đổi cũ. FNWEB2 không import hoặc gọi thư mục này. Không cần chạy dịch vụ này khi khởi động web.

Luồng hiện tại: `services/latex_parser.py` → `services/tex_table.py` hoặc `services/latex_renderer.py` → `services/local_tex.py` → `scripts/render_tex.cjs`. Xem `docs/LATEX_CUC_BO_VA_NGAN_HANG.md` để cài đặt và kiểm thử.
