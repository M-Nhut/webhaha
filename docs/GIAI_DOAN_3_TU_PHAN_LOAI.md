# Giai đoạn 3 — Tự phân dạng Chương 6 và mức độ

Triển khai local ngày 08/09/2026.

Sau khi giáo viên chọn phạm vi file, hệ thống phân tích nội dung câu, ngữ cảnh, phương án hoặc mệnh đề bằng bộ quy tắc có phiên bản `math9-c6-rules-v1`. Bộ quy tắc dùng danh mục `math9-c6-v4`, chỉ gồm 8 dạng của Chương 6 Bài 4 **Phép thử ngẫu nhiên và không gian mẫu. Xác suất của biến cố**, trong chủ đề **Thống kê và xác suất**.

Nó phân biệt yêu cầu toán học trước bối cảnh: ví dụ “lập không gian mẫu” khi tung đồng xu là Bài 4 dạng 1, còn “tính xác suất” với đồng xu là Bài 4 dạng 3. Tám dạng không gian mẫu/xác suất của Bài 4 có nhánh nhận diện riêng. Mức NB–TH–VD–VDC dựa trên việc đọc trực tiếp, chuyển biểu diễn/tính trực tiếp, kết hợp bước giải và ràng buộc đồng thời; không dựa vào độ dài hay số lớn.

Mỗi kết quả lưu mã dạng đề xuất, mức độ, căn cứ, độ tin cậy, phiên bản danh mục và fingerprint nội dung. Sửa nội dung làm fingerprint thay đổi nên kết quả được tính lại. Với Đúng/Sai, hệ thống lưu mức và căn cứ cho từng mệnh đề; chỉ tổng hợp mức toàn câu khi đủ căn cứ cho cả bốn ý.

Thiếu hình/công thức cần đọc, dạng ngoài phạm vi, hoặc căn cứ không đủ được gắn **Cần kiểm tra phân loại**. Hệ thống không tự coi các câu đó là Nhận biết. Câu có gợi ý rõ được nối tới nút danh mục và khi lưu sử dụng bộ cấp ID6 hiện hữu; bộ cấp số vẫn chống trùng. Nhãn ID6 đã có trong file được giữ. Giáo viên gán lại trên màn hình ID6 sẽ khóa kết quả bằng trạng thái `teacher_confirmed` và không bị tự ghi đè.

Hai cột audit mới của `bank_question` là `classification_status` và `classification_data`. Ứng dụng bổ sung cột khi khởi động; với SQLite có thể dùng:

```sh
python3 scripts/migrate_question_classification.py tutoring_center.db
```

Kiểm thử mới phủ xác suất nhiều bước, không gian mẫu, các bối cảnh trò chơi, ca mơ hồ ngoài phạm vi, fingerprint nội dung, thiếu hình và bốn mệnh đề Đúng/Sai. Bộ phân loại là quy tắc giải thích được, chưa gọi mô hình AI bên ngoài; dữ liệu câu mẫu có nhãn giáo viên vẫn cần thiết trước khi đặt ngưỡng tự gán rộng hơn.
