# Phase 8 · Tổng quan và người dùng

Đã thay toàn bộ S21, S25, S26, S27 theo Modern White Academy. Tổng quan giữ hai KPI và hoạt động thật theo từng vai trò; bỏ hero/logo lớn và shortcuts không đúng nhiệm vụ. Danh bạ giáo viên chỉ đọc, quản trị tài khoản chỉ dành cho admin.

Danh sách người dùng giữ tên đăng nhập trong vùng identity, mã, vai trò, số điện thoại, vị trí, trạng thái và thao tác; mobile chuyển thành card có nhãn. Hộp thoại tạo dùng native dialog với Escape, trả focus, body cuộn và actions luôn hiện. Hai vai trò có thể tạo/sửa là học sinh và giáo viên. Đổi vai trò không làm mất vị trí. Xóa và đặt lại mật khẩu dùng xác nhận native ghi rõ tên tài khoản; reset là form riêng, giữ mặc định 123456 hiện có. Tài khoản admin chỉ đọc, không có form lưu/reset.

Avatar mặc định/thiếu dùng SVG cục bộ trực tiếp, custom avatar giữ endpoint hiện có cùng fallback. Toàn bộ CSS riêng dùng token đang có; không thêm framework hay tài nguyên ngoài. Gỡ 29 inline style, 2 handler onsubmit và 12 directive Alpine trong các template sở hữu; dashboard CSS cũ được root dọn trong workspaces.css.

Kiểm chứng cuối: **281 kiểm tra trình duyệt**, **24 isolated Jinja renders**, 19 screenshot, 0 lỗi JS, 0 asset thiếu, 0 script/font/CSS ngoài, 0 token CSS chưa định nghĩa. Bao gồm 375/768/1024/1440, viewport thấp 375×667 và ngang 667×375, hoạt động rỗng/time thiếu/tên dài, danh bạ rỗng, active/locked, admin protected, native validation, focus/Escape, vị trí sau đổi role, cancel/confirm. Chỉ authentication gửi POST vào preview memory; create/delete/reset được intercept để xác minh POST và CSRF. Test CRUD thật do root tích hợp riêng.

Bằng chứng: [browser QA](people-dashboard-qa.json), [static QA](people-dashboard-static-qa.json), [browser script](qa/qa-people-dashboard.cjs), [static script](qa/qa-people-dashboard-static.py), ảnh trong [screenshots](screenshots/). Static script kiểm chứng cleanup dựa trên snapshot tạm /tmp/linhedu-phase8-source-before đã tạo trước thay đổi, không import app/DB/provider.
