# Giai đoạn 4 — Duyệt phân loại và khóa ID6

Hoàn thành và kiểm tra local ngày 08/09/2026.

Màn hình **Ngân hàng câu hỏi → Phân loại ID6** có thêm các bộ lọc: gợi ý chờ duyệt, cần kiểm tra và giáo viên đã xác nhận. Mỗi dòng hiển thị mã dạng, mức độ, căn cứ và trạng thái của kết quả tự phân loại.

Giáo viên chọn một hoặc nhiều dòng có trạng thái gợi ý rồi bấm **Xác nhận gợi ý đã chọn**. Hệ thống kiểm tra lại fingerprint nội dung và tình trạng nút danh mục ngay lúc xác nhận. Nếu hợp lệ, hệ thống gán nút danh mục/mức độ, giữ hoặc cấp số ID6 qua bộ cấp số dùng chung, rồi lưu trạng thái `teacher_confirmed` và khóa nhãn. Nội dung đã thay đổi hoặc nút danh mục không còn hợp lệ không được xác nhận bằng kết quả cũ.

Nút **Gán ID6 cho câu đã chọn** vẫn dùng cho các ca cần giáo viên chọn thủ công. Thao tác này cũng lưu lý do giáo viên xác nhận và khóa kết quả. Quyền chỉ cho phép giáo viên xử lý ngân hàng của mình; mọi ID6 tiếp tục dùng số thứ tự chung theo dạng, chống trùng khi lưu đồng thời.

Kiểm thử bao phủ xác nhận gợi ý hợp lệ, kết quả cũ sau khi sửa nội dung, phân quyền ngân hàng, xác nhận thủ công, giữ nội dung/ID nguồn và chống cấp số trùng.
