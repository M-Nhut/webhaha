# Giai đoạn 6 — Vận hành thí điểm trong giao diện

Hoàn thành và kiểm tra local ngày 08/09/2026.

Từ màn hình **Phân loại ID6**, giáo viên mở **Đánh giá thí điểm** để thực hiện trọn luồng:

1. Tải gói câu hỏi Toán 9 Chương 6 của ngân hàng. Gói đã bỏ đáp án, lời giải, kết quả tự phân loại và các bản lặp nội dung.
2. Giáo viên độc lập điền `expected_primary_code`, `expected_difficulty_level`, tên người gán nhãn và ghi chú trong JSON.
3. Tải file JSON đã hoàn tất trở lại hệ thống. File bị giới hạn 5 MB và được kiểm tra cấu trúc/nhãn.
4. Xem trạng thái đạt/chưa đạt, số nhãn hợp lệ, độ phủ tự gán, độ đúng cặp dạng–mức độ và số nhóm nội dung lặp.

Trang dùng lại cổng chất lượng của giai đoạn 5: tối thiểu 240 nhãn, độ đúng cặp từ 95% và không có nội dung lặp. File chỉ được xử lý trong yêu cầu hiện tại, không lưu nội dung nhãn lên máy chủ. Quyền tải gói và đánh giá tuân theo quyền truy cập ngân hàng hiện có.

Kiểm thử tích hợp xác nhận gói xuất không có `is_correct`, báo cáo tập nhỏ vẫn “Chưa đạt”, file JSON sai được báo lỗi và giáo viên không thể truy cập ngân hàng ngoài quyền.
