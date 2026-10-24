# Ngân hàng câu hỏi — tối ưu giai đoạn 1

## Phân trang server

- Mặc định 25 câu/trang; cho phép chọn 50 câu/trang.
- Quyền truy cập, phạm vi, dạng kiến thức và các bộ lọc được áp dụng trước
  khi đếm và đọc nội dung bằng `ORDER BY`, `LIMIT`, `OFFSET`.
- Thứ tự hiện có được giữ, với ID làm tiêu chí cuối để chuyển trang ổn định.
- URL lưu bộ lọc, phạm vi, `page` và `per_page`. Đổi bộ lọc/phạm vi trở về
  trang đầu; lưu/sửa/xóa giữ URL đang xem. Trang vượt giới hạn được đưa về
  trang cuối còn hợp lệ.
- Số câu, độ phủ và số sẵn sàng vẫn tính trên toàn bộ phạm vi được phép xem.

## Chi tiết theo yêu cầu

- Dữ liệu ban đầu chỉ gồm đề bài, dữ kiện, ảnh, nhãn, quyền thao tác và tài
  nguyên công thức xuất hiện trong đề bài/dữ kiện của trang hiện tại.
- `GET /api/question-banks/<bank_id>/questions/<question_id>` trả dữ liệu đầy
  đủ của một câu. API kiểm tra lại quyền ngân hàng, quyền câu hỏi và quan hệ
  câu hỏi–ngân hàng; phản hồi dùng `Cache-Control: private, no-store`.
- Bấm **Xem chi tiết** mới tải và tạo giao diện đáp án/lời giải/thiết lập.
  Bấm **Sửa** cũng tải chi tiết trước khi tạo biểu mẫu chỉnh sửa.
- Có trạng thái đang tải, báo lỗi và thử lại. Các lần mở đồng thời cùng một
  câu dùng chung yêu cầu; mở lại dùng dữ liệu của trang hiện tại.
- Thu gọn gỡ giao diện chi tiết khỏi DOM. Chuyển trang hủy các yêu cầu còn
  chạy; trang mới khởi tạo lại dữ liệu. Sửa đáp án giữ trạng thái đang mở.

## Phạm vi và phần tiếp theo

Giai đoạn này chưa thay đổi schema, index hoặc bộ render công thức. Thống kê
và chính sách legacy vẫn đọc metadata toàn ngân hàng trên server, nhưng
không dựng toàn bộ đối tượng câu hỏi và đáp án. Kiểm tra sẵn sàng dùng cờ có
nội dung/đáp án và khóa chấm số giới hạn 81 ký tự, rồi gọi lại các validator
hiện có. Nội dung đầy đủ của các câu ngoài trang không được đưa vào HTML.

Các bước sau tiếp tục tối ưu render công thức theo vùng nhìn thấy, truy vấn
tổng hợp, thống kê danh sách ngân hàng và cache/index.

## Kiểm tra đã thực hiện

Đã kiểm tra cú pháp Python bằng AST, JavaScript bằng `node --check` và các
template bằng bộ phân tích Jinja. Chưa chạy kiểm thử chức năng, kiểm thử trên
trình duyệt hoặc đo tốc độ thực tế; chưa khởi động host.
