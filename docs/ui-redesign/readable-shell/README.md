# Khung nội dung và chữ dễ đọc · 19/10/2026

Theo ảnh tham chiếu thứ hai của người dùng: giữ sidebar xanh với active lõm, đưa nội dung bên phải vào khung sáng bo góc lớn và tăng kích thước chữ. Áp dụng bằng token và CSS hiện có, thay rule tại nguồn; không thêm theme hoặc lớp giao diện cũ dự phòng.

## Thiết kế áp dụng

- Desktop: khung xanh12px bao quanh panel canvas, bo góc36px; sidebar104px. Header cùng nền với panel, cao tối thiểu80px. Tablet dùng khung8px/bo góc24px; điện thoại bỏ viền ngoài để dành chỗ cho nội dung.
- Một font UI Be Vietnam Pro400/500/600/700 lưu cục bộ. Nội dung/bảng/form/nút16px; chú thích14px; tiêu đề phần18–22px; tiêu đề trang30px, mobile26px; vùng đọc câu hỏi18–20px.
- Control chính46px, button phụ38px desktop và tối thiểu44px mobile; hàng bảng rộng hơn, header bảng đậm hơn. Font monospace cho mã kỹ thuật và font công thức giữ đúng vai trò riêng.
- Gỡ các cỡ chữ nhỏ đặt riêng trong hồ sơ, biên soạn đề, ngân hàng, làm bài, bước import mobile và lỗi. Biểu đồ dùng cùng font và cỡ chữ14px từ token, kể cả tooltip.
- Sticky toolbar và anchor dùng khoảng cách tính theo header/khung mới. Màn hình làm bài giữ vùng đọc tập trung và viền cân hai bên. Print xóa khung, khoảng đệm và màu nền ngoài.
- CSS chung và CSS trang thay đổi được cập nhật cache version; báo cáo AI tiếp tục dùng hash nội dung asset đang có.

## Kiểm chứng

- [Python](python-tests.json):15 passed,0 failed; CSRF, tài khoản/hồ sơ, menu theo quyền và route contract. SQLite memory, thư mục tạm, không nạp `.env`, không request/socket ngoài. [Log](python-tests.log).
- [Kiểm tra tĩnh](static-qa.json):31 CSS và49 template parse thành công; không token thiếu, không asset literal thiếu. Cú pháp shell và2 module biểu đồ đạt `node --check`. Review độc lập kiểm tra font, cache, sticky và cascade bản in; đã sửa reset print riêng cho màn hình làm bài.
- **Browser QA bổ sung chưa hoàn tất:** đã chạy290 bước trước khi assertion focus ngay sau resize desktop→mobile không đạt. Cần xác minh focus sau khi sự kiện `matchMedia.change` hoàn tất; chưa kết luận là lỗi giao diện hoặc nghiệm thu cả lượt. Lượt chạy lại đã bổ sung chờ sự kiện nhưng không được thực thi vì hệ thống duyệt timeout, rồi model duyệt quá tải. [Trạng thái](browser-status.json), [kết quả dừng](failure.json) và [script QA](qa-readability.cjs). Ảnh trong thư mục screenshots là ảnh của lượt chưa hoàn tất, không phải bằng chứng nghiệm thu toàn giao diện.

Bản xem trước dùng dữ liệu giả lập: `python3 scripts/preview_ui_phase9.py --port 8771`. Tài khoản `qa_teacher`, `qa_admin`, `qa_student`, mật khẩu `Academy123!`.
