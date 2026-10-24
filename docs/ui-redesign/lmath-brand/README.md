# Thương hiệu LMath · 19/10/2026

**Đã xác minh ở cập nhật tiếp theo:** [bản đăng nhập tách khối](../login-detached/README.md) có100 kiểm tra browser đạt, bao gồm tên LMath, logo/caption, các breakpoint, shell và trang lỗi. Giới hạn browser dưới đây ghi lại tình trạng của lượt đổi tên trước đó.

Theo yêu cầu người dùng: đổi tên thương hiệu hiển thị thành **LMath**, thu logo trang đăng nhập trên laptop và đặt tên bên cạnh. Dưới tên có dòng chữ nhỏ chính xác: **Không gian học tập và giảng dạy**.

- Logo128px trên desktop/laptop,100px tablet,72px điện thoại; luôn nằm cạnh khối tên/mô tả. Tên42/36/30px theo breakpoint, mô tả14px; cùng font Be Vietnam Pro.
- Logo vẫn chuyển động nhẹ chu kỳ5giây ease-in-out, biên độ±6px và±4px mobile. Reduced-motion/print tắt animation.
- Đổi toàn bộ tên hiển thị trong template: title trình duyệt, login/register, sidebar, tooltip/aria-label, trang lỗi và footer. Logo PNG hiện có được giữ.
- Biểu mẫu đăng nhập giữ nguyên. Định danh kỹ thuật dùng lưu nháp/truy vấn không phải nội dung thương hiệu hiển thị và không thay đổi.
- Thay rule logo lớn/xếp dọc ngay trong auth.css, bổ sung khối caption; cập nhật cache version stylesheet đăng nhập/đăng ký. Không giữ lớp giao diện cũ dự phòng.

## Kiểm chứng

[Kiểm tra tĩnh đạt](static-qa.json):49 template parse thành công, không còn tên thương hiệu cũ trong template; auth.css parse không lỗi, phần form và script đăng nhập giữ nguyên nội dung.

**Chưa kiểm chứng trực quan bản LMath:** hệ thống duyệt tự động chặn việc chạy Chrome trước thực thi vì model duyệt quá tải (`Selected model is at capacity`). [Script QA](qa-lmath.cjs) sẵn kiểm tra1440/1366/1024/768/375px, logo cạnh tên, caption, animation, overflow, reduced-motion, no-JS và tên hiển thị trong shell/trang lỗi. Không có ảnh mới hoặc kết quả browser đạt của bản này; ảnh/kết quả trong thư mục login-brand là phiên bản trước.
