# Ngân hàng câu hỏi — tối ưu giai đoạn 2

## Công thức theo vùng nhìn thấy

- Trang chi tiết dùng `IntersectionObserver` với vùng đệm 240 px. Đề bài,
  dữ kiện, đáp án, lời giải và bản xem trước khi sửa được xử lý khi gần vùng
  nhìn thấy; trình duyệt thiếu API này dùng sự kiện cuộn/đổi kích thước.
- Hàng đợi xử lý từng khối bằng `requestIdleCallback` (dự phòng bằng timer).
  Công thức nhập và TeX thông thường dùng chung hàng đợi MathJax; tài nguyên
  nhập được thay vào trước khi quét phần TeX còn lại.
- Dấu nhận diện dựa trên nội dung gốc, tài nguyên được sử dụng và trạng thái
  engine giúp bỏ qua những lần gọi lặp cho khối đã hiển thị. Nội dung hoặc
  công thức thay đổi được xử lý lại, kể cả khi Alpine cập nhật `x-text`.
- MathJax khởi động/quét toàn trang cũng đi qua bộ điều phối, tránh xử lý các
  câu ngoài vùng nhìn thấy. Văn bản thường không cần một lượt MathJax.
- Thu gọn/xóa khối chi tiết hoặc chuyển sang khung sửa gỡ các phần tử đã tách
  khỏi observer/hàng đợi. Rời trang dừng công việc đang chờ; trở lại bằng
  lịch sử trình duyệt phục hồi observer.
- Nút xem trước câu nhập thủ công xử lý trực tiếp yêu cầu của người dùng.

## Truy vấn thống kê

- Danh sách ngân hàng dùng một truy vấn `GROUP BY` theo ngân hàng, mức độ,
  phạm vi và các chủ thể sở hữu. Quyền truy cập vẫn được quyết định bằng
  `can_view_question`; câu riêng của giáo viên khác không vào thống kê.
  Không đọc `bank.questions`, nội dung câu hoặc đáp án cho mỗi card.
- Creator của các ngân hàng được nạp theo lô. Trang chi tiết lấy vai trò
  creator/owner bằng JOIN thay cho truy vấn từng tài khoản.
- Kiểm tra sẵn sàng chỉ đọc đáp án của câu đã duyệt, có đề bài, được sử dụng
  và thuộc loại/mức độ hỗ trợ. Một truy vấn gộp đếm cấu trúc đáp án; khóa số
  được đọc thêm trong một truy vấn với giới hạn 81 ký tự. Các validator hiện
  có quyết định sẵn sàng từ dữ liệu cấu trúc tương đương.
- Ma trận độ phủ lập chỉ mục trong một lượt duyệt thay cho việc lọc lại mọi
  câu ở từng ô. Số tổng vẫn tính trên phạm vi được phép xem trước bộ lọc.
- Tập ID lớn được truyền bằng một tham số tập hợp trên SQLite/PostgreSQL,
  tránh giới hạn số biến của truy vấn `IN`.

## Index và triển khai

Model và `initialize_database` bổ sung hai index:

- `ix_bank_question_bank_id`;
- `ix_bank_question_option_question_id`.

Index còn thiếu được tạo bằng `checkfirst=True` khi ứng dụng khởi động lại;
không cần viết lại câu hỏi hoặc dữ liệu đáp án. Trong lượt thực hiện này,
chưa khởi động ứng dụng hoặc chạy tạo index trên cơ sở dữ liệu đang dùng.

Metadata phục vụ quyền legacy/danh mục vẫn được duyệt theo số câu của ngân
hàng trên server. Chưa dùng cache thống kê xuyên request; tối ưu sâu bước
này cần số liệu đo trên bộ dữ liệu thực tế.

## Kiểm tra

Đã kiểm tra cú pháp Python bằng AST, các file JavaScript bằng `node --check`
và template bằng bộ phân tích Jinja. Chưa chạy kiểm thử chức năng/trình duyệt,
truy vấn cơ sở dữ liệu hoặc benchmark; chưa có số đo mức cải thiện tốc độ.
