# Thu gọn hệ thống học tập

Phạm vi hiện tại gồm quản trị viên, giáo viên và học sinh; quản lý lớp, ngân hàng câu hỏi, đánh giá đầu vào và luyện tập cá nhân hóa.

Luồng nhập chỉ có ba hình thức: trắc nghiệm, Đúng/Sai THPT và trả lời ngắn. Tự luận cũ được chuyển sang trả lời ngắn, giữ nội dung và đáp án hiện có. Câu thiếu đáp án vẫn cần giáo viên bổ sung trước khi dùng để chấm tự động.

Danh mục ID6 chỉ giữ Chương 6 Toán lớp 9, Bài 4 **Phép thử ngẫu nhiên và không gian mẫu. Xác suất của biến cố**, với 8 dạng `9C6-4-1` đến `9C6-4-8`. Chủ đề **Thống kê và xác suất** vẫn được giữ để phục vụ cá nhân hóa; bảng ID6 không còn cột chủ đề và phiên bản. Nhãn mã trên bảng là ID CÂU HỎI.

Các chức năng học phí, bảng lương, nhật ký giảng dạy, phụ huynh, manager và staff được gỡ khỏi các luồng hoạt động. Khi nâng cấp dữ liệu cũ, tài khoản thuộc vai trò đã bỏ không được tự nâng quyền sang quản trị viên.

Cơ sở dữ liệu cục bộ được sao lưu trong thư mục `backups/` trước khi áp dụng thay đổi. Thư mục sao lưu và `.env.local` được bỏ qua bởi Git.
