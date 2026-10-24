# Prompt chẩn đoán sai lầm Bài 4

## Phạm vi

Áp dụng yêu cầu báo cáo 4 phần của giáo viên: tổng quan, lỗi quan sát/giả thuyết nguyên nhân, nguy cơ có điều kiện, can thiệp nhanh. System prompt và user template nằm tại `services/diagnostic_report_contract.py`. Báo cáo cá nhân dùng phiên bản `lesson4-diagnosis-v4-grounded-four-sections`. Báo cáo lớp dùng cùng nguyên tắc chẩn đoán, giữ cấu trúc tổng hợp lớp/từng học sinh hiện có và phiên bản cache riêng.

## Điều chỉnh để không kết luận vượt bằng chứng

- Đáp án không khớp là quan sát; nguyên nhân (khái niệm, tính toán, đọc hiểu) luôn là giả thuyết. Có nhãn `insufficient_evidence` khi thiếu căn cứ. Ý a–d không mặc nhiên là chuỗi bước giải.
- Tối đa 3 nguy cơ/can thiệp, không ép tạo đủ nếu thiếu dữ liệu. Nguy cơ cá nhân phải có điều kiện kích hoạt, bằng chứng và câu hỏi kiểm chứng; không đưa xác suất tự ước lượng.
- JSON có kiểm tra schema/ref được web trình bày thành 4 phần; không nhận HTML/Markdown từ mô hình để chèn trực tiếp.
- Báo cáo cá nhân lấy thống kê từ đề blueprint 22 câu đã chấm gần nhất. Mẫu số các phần là 12 câu, 16 ý, 6 câu; tách bỏ trống/chờ chấm khỏi sai. Không dùng điểm Đúng/Sai phi tuyến làm tỉ lệ đúng.
- Khi có đề phù hợp, bằng chứng cá nhân được giới hạn về đúng bài nộp đó. Khi chưa có đề 22 câu phù hợp, dùng lịch sử lỗi Bài 4 và hiển thị rõ không có thống kê toàn đề.

## Thay đổi dữ liệu gửi AI theo yêu cầu mới

Trước đây chỉ gửi bản sao lỗi không đáp án. Nay bổ sung đáp án đã đóng băng, nội dung lựa chọn và ngữ cảnh các ý Đúng/Sai cùng câu để đối chiếu. Không gửi đáp án của các câu chưa làm trong ngân hàng. Không gửi mastery, quota hay trạng thái bộ sinh đề. AI vẫn không được cập nhật các dữ liệu này.

Các số liệu và cột câu/ý/đáp án hiển thị lấy lại từ dữ liệu hệ thống, không tin bản sao do AI trả. Phản hồi ngoài schema, ref lạ, ý đúng/trống bị quy là lỗi, nguy cơ không có điều kiện hoặc bị đánh dấu đã xác nhận sẽ bị từ chối. Khi API thất bại, vẫn hiển thị 4 phần với sự thật đối chiếu; không tự bịa nguy cơ dự phòng.

## Vận hành

Không đổi API key, không chạy migration và không gọi AI thật trong kiểm thử. Báo cáo đã lưu trước đây vẫn đọc được theo giao diện cũ; lần phân tích mới dùng prompt/cache mới. Cần kiểm chứng thực nghiệm với giáo viên trước khi coi chẩn đoán là chính xác; kiểm tra cấu trúc không chứng minh tính đúng đắn của mọi câu văn do AI tạo.
