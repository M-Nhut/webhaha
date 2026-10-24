# Theo dõi học tập và nhập câu hỏi — 27/09/2026

## Cách sử dụng

Khởi động lại tiến trình FNWEB2 và nhấn Ctrl+F5. Menu **Theo dõi học tập** hợp nhất danh sách theo lớp, hồ sơ học sinh và lịch sử bài làm. Trang học sinh chỉ mở số liệu tổng quát; bảng dạng kiến thức, phân tích sai lầm và giao bài được thu gọn, mở khi cần.

Trong cửa sổ đối chiếu có **Giữ bản bên trái**, **Giữ bản bên phải**, **Giữ cả hai** và **Bỏ cả hai khỏi lần nhập**. Lựa chọn cuối áp dụng khi cả hai bản nằm trong file nhập; không xóa ngầm câu đã lưu trong ngân hàng. Thay thế câu đã lưu chỉ được phép với câu giáo viên có quyền sửa; giữ nguyên ID và các đề thi đã đóng băng. Quyết định đối chiếu gắn với phiên bản nội dung; thay đổi nội dung phải kiểm tra lại.

Khi hai bản cùng file trùng nội dung, bản có đáp án hợp lệ và lời giải được ưu tiên. Nếu bản đang nhập bổ sung lời giải cho câu đã lưu, hệ thống yêu cầu đối chiếu trước khi thay thế. Thiếu đáp án được phân biệt với đáp án mâu thuẫn. Không suy luận đáp án đúng từ lời giải bằng AI.

Ngân hàng lớp/chủ đề khác không tự nhận tám dạng xác suất 9. Mẫu `docs/examples/ngan_hang_nhieu_chu_de.tex` hỗ trợ nhãn lớp, dạng và mức độ; giáo viên kiểm tra nhãn trước khi lưu. Khả năng mở rộng ngân hàng không đồng nghĩa thuật toán nghiên cứu xác suất 9 đã được kiểm chứng cho mọi chủ đề.

## Tính ổn định và giới hạn của báo cáo

Số liệu quan sát được tổng hợp từ bài đã chấm, trong phạm vi lớp giáo viên được phép xem. AI chỉ đề xuất giả thuyết nguyên nhân, câu hỏi kiểm chứng và hướng hỗ trợ. Mỗi giả thuyết phải liên kết bằng chứng thuộc đúng học sinh/kỹ năng. Không dùng số câu đúng để khẳng định nắm vững, không trình bày điểm tin cậy do AI tự đoán như xác suất đã hiệu chuẩn.

Cùng dữ liệu đầu vào, mô hình, phiên bản prompt và cấu hình sở hữu sẽ trả lại bản hoàn tất đã lưu, kể cả khi bấm phân tích lại. Bản mới được tạo khi dấu dữ liệu hoặc cấu hình thay đổi. Temperature 0 hỗ trợ giảm biến thiên; cơ chế lưu bản mới là căn cứ tái lập kết quả. Nút giáo viên đã đối chiếu chỉ ghi nhận việc xem xét, không chứng minh giả thuyết đúng.

Để báo cáo khóa luận, cần đánh giá riêng: tỷ lệ dẫn chiếu bằng chứng hợp lệ, số nhận định không được dữ liệu hỗ trợ, độ thống nhất giữa các giáo viên đánh giá, và kết quả câu hỏi kiểm chứng tiếp theo. Các kiểm thử phần mềm không phải bằng chứng về hiệu quả sư phạm hoặc độ chính xác chẩn đoán. Chưa có số liệu thực nghiệm mới để tuyên bố cải thiện học tập.

## LaTeX cục bộ

Bộ biên dịch chạy trong tiến trình WebAssembly cục bộ, không gửi đề đến dịch vụ dựng hình. Gói tkz-tab và xkeyval đã đóng gói trong `vendor/tex`; giữ thông tin giấy phép và nguồn. Gói dàn trang không liên quan bị loại khỏi ngữ cảnh dựng từng hình; khai báo bị cắt dở không được phép nuốt nội dung hình kế tiếp. Khóa bộ nhớ đệm phụ thuộc mã nguồn và preamble. Việc khôi phục hình trong ô chỉnh sửa chỉ dùng tài sản của chính câu đó, tránh lấy hình có cùng đoạn mã nhưng khác ngữ cảnh từ câu khác.

Kiểm tra file `DE 1 2.tex`: 132 câu, 36 khối hình/bảng, 35 khối biên dịch được. Câu 121 còn lỗi `No shape named N43`: khai báo ba mốc x nhưng bốn mục biến thiên. Cần tác giả xác nhận và sửa cấu trúc bảng; hệ thống không tự sửa nội dung toán học. Nhãn tiếng Việt được ghép dấu trong bộ phông cục bộ, cần đối chiếu thị giác với bản gốc khi sử dụng hình phức tạp.

Có thể chạy kiểm tra nguồn không động đến cơ sở dữ liệu:

```powershell
.venv\Scripts\python.exe scripts/check_tex_figures.py "duong-dan-file.tex"
```

## Kiểm chứng

Nhóm kiểm thử hiện hành đã chạy: 59 bài kiểm thử và 20 kiểm thử con đã qua ngày 27/09/2026; 6 kiểm thử ngân hàng được chạy lại và đều qua sau khi bổ sung số lượng câu cập nhật trên biên nhận. Bao gồm lỗi quan hệ ErrorObservation ở trang học sinh, cô lập lớp học, cache báo cáo, giữ nguyên ID khi thay bản có lời giải, phân loại ngân hàng phổ thông và hiển thị LaTeX. Năm mô-đun JavaScript liên quan cũng đã qua kiểm tra cú pháp.

Bộ `test_class_lesson4_report.py` cũ còn các giả định chương 6 và phản hồi fallback không tương thích hợp đồng chương 8/đề 22 câu hiện tại; không tuyên bố toàn bộ repository đã qua kiểm thử. Các kiểm thử này cần được chuyển đổi riêng. Kiểm tra dữ liệu thực ở trang học sinh 6 được thực hiện với kết nối SQLite chỉ đọc; không xóa, nhập lại hay sửa dữ liệu học sinh.

