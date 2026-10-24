# Phase 5 — Báo cáo AI cho giáo viên

## Phạm vi

Báo cáo chỉ dùng Toán 9, Chương 8, bài kết hợp 25 + 26 (`9C8-i-1` đến
`9C8-i-8`). AI là lớp diễn giải có thể kiểm tra; không ghi mastery, không chọn
câu, không tạo quota và không quyết định luồng tự luyện.

- Báo cáo cá nhân chỉ do giáo viên phụ trách lớp có enrollment active khởi tạo.
- Báo cáo lớp chỉ dùng roster active của chính lớp; dữ liệu ra ngoài dùng token
  giả danh, không có tên, mã học sinh hay khóa AI.
- Nguồn là answer facts của submission đã finalized/graded và frozen
  question/key. Câu bỏ trống, chưa chấm và dữ liệu lớp khác bị loại.

## Evidence và cách đọc

Mỗi lỗi quan sát phải dẫn `evidence_ref`, câu/ý thực tế và đáp án frozen. Lỗi
quan sát chỉ nói đáp án đã chấm không khớp, không tự kết luận misconception.
Rủi ro tương lai luôn là `validation=not_validated`, phải có evidence refs,
kịch bản kích hoạt và câu hỏi kiểm chứng. Không có phần trăm/xác suất dự báo.

Báo cáo cá nhân nhận cả assessment đầu vào chung 22 câu và tự luyện fixed 22
câu có đúng phạm vi/type contract. Thống kê phần chỉ thuộc submission mới nhất;
lỗi lịch sử tối đa 12 submissions/80 evidence refs để có thể nhận ra lặp lại mà
không làm request vô hạn.

## Freshness, lỗi nhà cung cấp và duyệt

Fingerprint gồm evidence finalized (kể cả bài mới toàn đúng và lần chấm lại),
roster/cấu hình cho báo cáo lớp; báo cáo cá nhân giữ source revision đã chụp
trước khi gọi AI. Evidence hoặc cấu hình AI mới làm bản cũ không thể duyệt.
Packet lớp còn giữ identity/revision giới hạn của submission finalized trong
phạm vi, nên một bài hoàn toàn bỏ trống (không có answer-event) vẫn làm báo cáo
cũ stale mà không gửi nội dung đáp án mới ra AI.
Nếu submission mới hoàn tất trong lúc gọi AI, endpoint đánh dấu snapshot vừa
tạo là stale thay vì hiển thị như hiện hành.

Khi provider lỗi/không có cấu hình, hệ thống chỉ hiển thị fallback từ dữ liệu
quan sát, không bịa hypothesis/risk và không chặn practice. Fallback không thể
được xác nhận là báo cáo AI. Thông báo lỗi không phản chiếu exception/provider
body tùy ý, nên không làm lộ header hay secret.

Kiểm thử cô lập: `python3 -m unittest tests.test_phase5_reports`.
