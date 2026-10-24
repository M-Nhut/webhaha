# Kiểm chứng bản LaTeX và giao diện

- 43 tests đạt, 16 subtests đạt; chi tiết trong `latex-v3-tests.xml`. Có cảnh báo thư viện/SQLAlchemy; không coi đây là kiểm thử toàn bộ ứng dụng.
- D1/D2/D5: 60 câu, 30 bảng, 6 hình; không có lỗi biên dịch. Chi tiết `latex-v3-real-files.json`.
- Đối chiếu chỉ đọc D1 với ngân hàng thật: đủ 14 danh tính trùng sau khi chuẩn hóa giãn cách/cỡ ngoặc; không cập nhật dữ liệu thật.
- Trình duyệt: 6/6 hình vòng quay tải thành công, tâm hình trùng tâm vùng nội dung; không cần bấm thử lại. Kiểm tra trực quan chữ “Tấm bìa A/B”, “Hình 1”.
- Trình duyệt D1: 4 bảng, không có mjx-merror; các đáp án ngắn dùng tập hợp hiển thị bằng MathJax.
- Bộ lọc câu trùng, đối chiếu từng câu và bản xem trước nhập thủ công hoạt động trên bản xuất từ dữ liệu kiểm thử cô lập.
- Khung sửa lời giải cao tối thiểu 240 px, có thể kéo giãn; bộ lọc danh mục cao 42 px.
- Dữ liệu cũ đã mất mã hình trong lúc nhập cần dùng lại file nguồn; không thể khôi phục hình từ văn bản đã bị cắt.
