# Phase 3 — Luồng tự luyện kiến thức thống nhất

## Đã triển khai

- Học sinh dùng một mục **Tự luyện kiến thức** cho lớp 9, Chương 8, bài kết
  hợp 25 + 26 và tám dạng `9C8-i-1` đến `9C8-i-8`. URL danh sách đánh giá cũ
  của học sinh chuyển về cùng điểm vào này; màn hình giáo viên tạo đánh giá
  vẫn chỉ nhận lớp và ngân hàng như Phase 2.
- Học sinh phải chọn một lớp đang ghi danh. Nếu chưa có bằng chứng đã chấm và
  hoàn tất trong đúng môn/phạm vi, hệ thống chỉ cho mở bài đầu vào chung đang
  hoạt động, đã giao cho chính học sinh và còn khớp bộ câu hỏi đóng băng.
  Trạng thái `completed` đơn lẻ không được dùng để dựng hồ sơ.
- Khi hồ sơ đã khởi tạo, bộ chọn thích ứng hiện hữu vẫn quyết định đề 22 câu.
  Khi học sinh tự tạo, các em không chọn ngân hàng hay mức nhận thức. Ngân hàng duy nhất được
  phép là `Exam.question_bank_id` của đánh giá đầu vào mới nhất đã giao trong
  lớp, phải đang hoạt động, đúng môn/lớp 9 và thuộc giáo viên phụ trách lớp.
- POST giả mạo ngân hàng khác bị từ chối. Thiếu đánh giá, bộ câu hỏi không đủ
  cấu trúc 22 câu/tám dạng, hash đóng băng sai, hoặc ngân hàng nguồn mất quyền
  đều tạo thông báo có hành động cho giáo viên; hệ thống không lấy ngân hàng
  của lớp/giáo viên khác làm dự phòng.
- Đề đã phát hành cho chính học sinh, đúng lớp, đúng scope và đúng ngân hàng
  nhưng chưa nộp được mở lại thay vì tạo đề mới. Phiên đã chấm ở trạng thái
  chờ quyết định vẫn quay về màn hình kết quả để học sinh chọn tiếp tục/kết
  thúc; không âm thầm supersede phiên đó.
- Bài giáo viên đã duyệt/phát hành vẫn xuất hiện riêng trong lớp đã chọn. Các
  phiên này có thể tiếp tục với một hoặc nhiều ngân hàng nếu toàn bộ ngân hàng
  còn hoạt động, đúng môn và vẫn thuộc giáo viên phụ trách lớp; chúng không
  trở thành lựa chọn ngân hàng cho nút học sinh tự tạo.
- Quyền mở bài đầu vào trực tiếp cần active enrollment và assignment hợp lệ.
  Kết quả lịch sử đã hoàn tất của chính học sinh vẫn đọc được dù dữ liệu cũ
  chưa có assignment, để không làm mất bằng chứng lịch sử.

## Giới hạn có chủ ý

- Không thêm schema hay migration, không sửa công thức adaptive/AI, không thêm
  autosave hoặc timer, và không thực hiện công việc Phase 4/5.
- Bằng chứng hồ sơ đã hoàn tất tiếp tục được tái sử dụng theo môn và scope;
  assignment đang chờ, nguồn ngân hàng và phiên resume luôn bị giới hạn theo
  lớp đang chọn.
- Nếu giáo viên đổi ngân hàng nguồn bằng một đánh giá đầu vào mới, phiên cũ
  dùng ngân hàng khác không tự được resume/continue. Phiên được giữ để kiểm
  tra thay vì âm thầm dùng nguồn không còn được lớp cho phép.

## Kiểm tra

`tests/test_unified_practice_phase3.py` có bốn ca DB SQLite cô lập: điểm vào
thống nhất và không lộ ngân hàng khác; quyền assignment khi làm bài đầu vào;
khóa bank nguồn/chặn override; và resume đề chưa nộp không tạo bản trùng.
