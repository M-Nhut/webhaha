# Phase 4 — vòng lặp chấm và học từ bằng chứng

## Phạm vi hoàn tất

- Bài tự luyện và đánh giá đầu vào trong phạm vi `9C8-i-1` đến `9C8-i-8`
  được chấm tự động theo hợp đồng 22 câu / 40 phút: 12 câu chọn một (0,25
  điểm), 4 câu Đúng/Sai (4 mệnh đề, bảng 0 / 0,1 / 0,25 / 0,5 / 1), và 6 câu
  trả lời ngắn (0,5 điểm).
- Một POST thành công lưu trong cùng một giao dịch: bài nộp và đáp án đã
  chấm, `LearningHistory`, quan sát đáp án sai/hồ sơ lỗi, snapshot mastery,
  và completion của assignment đầu vào hoặc trạng thái quyết định phiên.
  Nếu bất cứ bước nào lỗi, rollback giữ nguyên cả dữ liệu học tập lẫn trạng
  thái claim tạm để học sinh có thể nộp lại.
- Phiên đề cố định mới claim bền vững `active -> submitting` trước khi tạo
  bài nộp; chỉ phiên giữ đúng `last_exam_id` mới chuyển
  `submitting -> awaiting_decision`. Vì vậy double-click / POST đồng thời
  không thêm bản nộp hay ghi đè binding của phiên. Assignment đầu vào dùng
  claim tương đương `assigned -> grading -> completed`.
- Bản nháp đầu vào cũ, chưa nộp được dùng lại, nhưng toàn bộ đáp án cũ bị xóa
  trước khi ghi lại từ POST hiện tại. Một bài đầu vào đã finalized không thể
  tạo thêm attempt.
- Màn hình kết quả hiển thị câu trả lời thực tế so với đáp án đã đóng băng,
  gồm đủ nhãn mệnh đề `a`–`d` của Đúng/Sai. Kết quả đầu vào dẫn rõ về điểm vào
  **Tự luyện kiến thức** để sinh đề theo bằng chứng mới vừa hoàn tất.
- Nút Tiếp tục/Kết thúc và trang kết quả dùng chung một điều kiện sẵn sàng:
  bài nộp finalized/graded, snapshot mastery của chính submission, binding
  `last_exam_id`/`last_submission_id`, session đúng scope và enrollment còn
  active trong lớp còn active. Tiếp tục vẫn dùng guards provenance ngân hàng
  lớp/giáo viên hiện hữu.

## Không thay đổi

- Không thay đổi công thức adaptive, trọng số, tách biệt AI quan sát/dự đoán,
  hay quy trình giáo viên duyệt import/phân loại.
- Không thêm schema/migration và không sửa dữ liệu sản xuất.
- Các practice row lịch sử không có `PracticeSession` vẫn được giữ khả năng
  xem/chấm theo hợp đồng cũ; chúng không thể được trang bị claim đồng thời
  mới nếu không thay đổi dữ liệu lịch sử. Một đề mới có `practice_session_id`
  nhưng không tìm thấy session sẽ fail closed.

## Kiểm tra cô lập

`python3 -m unittest tests.test_learning_loop_phase4` kiểm tra bốn hợp đồng:

1. Replay tuần tự một POST đề cố định không tạo thêm submission, đồng thời có
   snapshot và observed wrong-answer evidence. Claim có điều kiện là cơ chế
   xử lý POST đồng thời; test cô lập này không mô phỏng hai kết nối DB song song.
2. Lỗi khi cập nhật evidence rollback submission và claim `submitting`.
3. Đúng/Sai đúng ba mệnh đề nhận 0,5 điểm và tạo quan sát; bài bỏ trống không
   trở thành lỗi quan sát.
4. Diagnostic draft được dựng lại sạch, và Continue/End bị chặn khi snapshot
   bị thiếu.
