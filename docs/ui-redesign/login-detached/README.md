# Đăng nhập tách khối · LMath · 19/10/2026

Theo yêu cầu mới nhất: bên trái chỉ giữ logo chuyển động, tên LMath và dòng “Không gian học tập và giảng dạy” trực tiếp trên nền trang. Bỏ nền khối, viền và đường chia giữa. Form bên phải thành card trắng độc lập có viền, bo góc và shadow nhẹ.

**Điều chỉnh kích thước mới nhất:** logo192px và tên56px trên laptop; tablet128/44px, điện thoại88/36px. Dòng mô tả vẫn14px.

Desktop/laptop cách hai vùng64px; tablet chuyển thành một cột cách32px, mobile24px. Logo/tên/dòng mô tả và reduced-motion giữ như cập nhật thương hiệu trước. Auth layout chung chỉ giữ cấu trúc grid; phần khung liền cũ được giới hạn cho trang đăng ký còn sử dụng, không giữ lớp ghi đè hoặc theme đăng nhập cũ.

## Kiểm chứng

- [Browser QA](browser-qa.json):**100 kiểm tra đạt** ở1440/1366/1024/768/375px, gồm tách vùng, nền/viền, cỡ logo, caption, tên LMath, không tràn ngang, reduced-motion, hiện mật khẩu, đăng nhập thực tế bằng tài khoản giả lập, tên trong shell/trang lỗi, no-JS và bố cục đăng ký. Không lỗiJS hoặc asset.
- [Kiểm tra tĩnh](static-qa.json): CSS/Jinja không lỗi; template đăng nhập/đăng ký chỉ đổi cache version, form giữ nguyên.
- Đã xem ảnh laptop [1366px](screenshots/login-1366.png) và mobile [375px](screenshots/login-375.png). Các ảnh [1440px](screenshots/login-1440.png), [1024px](screenshots/login-1024.png), [768px](screenshots/login-768.png) cùng được chụp trong reduced-motion; hiệu ứng được kiểm tra riêng khi bật chuyển động.

[Script QA](qa-detached.cjs) dùng preview giả lập cục bộ8771, không dữ liệu hoặc tài khoản thật. Lượt này đồng thời xác minh các cập nhật LMath đã chờ browser ở lượt trước. Không xác nhận thay cho lượt kiểm tra focus sidebar còn mở trong readable-shell.
