# Logo lớn trên trang đăng nhập · 19/10/2026

Theo yêu cầu người dùng: thay toàn bộ nội dung giới thiệu bên trái bằng logo thương hiệu hiện có và chữ **LinhEdu**. Bỏ logo nhỏ lặp phía trên của riêng trang đăng nhập. Form, CSRF, lỗi nhập liệu, thông báo server, hiện mật khẩu, link đăng ký và native submit giữ nguyên.

Desktop có logo220–320px và tên36–48px, căn giữa khối trái; trang được căn giữa theo chiều cao. Tablet/mobile chuyển khối nhận diện thành hàng gọn phía trên form, logo100/80px; không ẩn nhận diện. Trang đăng ký chỉ đổi cache version CSS dùng chung, markup và bố cục của trang đó được giữ nguyên.

Chỉ logo chuyển động dọc±10px (tablet/mobile±6px), chu kỳ5giây ease-in-out, không thay đổi layout. Tên thương hiệu đứng yên. Reduced-motion và print tắt chuyển động. Dùng CSS hiện có, không thêm JavaScript hoặc thư viện; logo PNG không bị chỉnh sửa. CSS khối giới thiệu còn consumer ở trang đăng ký nên được giữ.

## Kiểm chứng

- [Browser QA](browser-qa.json):48 kiểm tra đạt ở1440/1024/768/375px; logo tải đúng, cỡ lớn, vị trí desktop/mobile, animation, reduced-motion, hiện mật khẩu, không cuộn ngang, fallback không JavaScript, trang đăng ký và không lỗiJS/asset.
- [15 kiểm tra Python đạt](python-tests.json), [log](python-tests.log): CSRF, tài khoản/hồ sơ, quyền menu và route contract; SQLite memory, file tạm, không nạp`.env` hoặc request ngoài.
- [Kiểm tra tĩnh](static-qa.json): CSS/Jinja parse không lỗi, form hooks giữ đủ, nội dung trái cũ đã gỡ, trang đăng ký chỉ đổi cache version. Đã xem ảnh desktop và mobile.

Ảnh: [1440px](screenshots/login-1440.png), [1024px](screenshots/login-1024.png), [768px](screenshots/login-768.png), [375px](screenshots/login-375.png). Ảnh chụp trong chế độ giảm chuyển động để giữ logo đứng yên; animation được kiểm tra riêng khi không bật chế độ đó.

Script: [qa-login-brand.cjs](qa-login-brand.cjs). Preview giả lập tại`http://127.0.0.1:8771/login` qua`scripts/preview_ui_phase9.py`.
