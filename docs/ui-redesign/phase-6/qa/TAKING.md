# Làm bài · S12

Ba tệp runtime: `templates/exam_take.html`, `static/js/modules/exam_take.js`, `static/css/pages/exam-taking.css`.

- Shell tập trung dùng token Modern White Academy; một đồng hồ trong cột hỗ trợ sticky trên desktop, chuyển lên header trên tablet/mobile. Điều hướng câu gọn trước nội dung ở mobile; native dialog giữ Escape và trả focus.
- Tiến độ đọc trực tiếp native controls: xóa văn bản hoặc bỏ checkbox trừ tiến độ; Đúng/Sai thiếu ý là một phần. Tên field, CSRF, anchors và dữ liệu theo dõi thời gian giữ nguyên.
- Một guard dùng cho xác nhận đủ/thiếu/trống và tự nộp khi hết giờ. POST FormData giữ toàn bộ đáp án; chỉ chuyển trang khi URL kết quả đúng ngữ cảnh. Mất kết nối, timeout, lỗi HTTP hoặc redirect về trang làm bài giữ DOM để thử lại. Không thêm autosave/khôi phục đáp án.
- Countdown dùng wall clock trong lượt mở hiện tại; mở lại vẫn bắt đầu thời lượng theo hành vi runtime trước Phase 6. Không thêm deadline, submission nháp hoặc thay quy tắc chấm.
- Ảnh lỗi có retry; yêu cầu tải lại chuyển sang eager để ảnh đang ẩn vẫn tải được. Hình có native zoom dialog; FormulaRenderer cục bộ tiếp tục xử lý công thức, bảng và placeholder ảnh.

`taking-qa.json` ghi **62 kiểm tra cuối đã đạt**, không lỗi JavaScript. Lần nghiệm thu cuối dùng riêng bài lịch sử: bốn width 375/768/1024/1440; xóa short answer; TF partial; xác nhận đủ/thiếu/trống; Escape/focus; POST lặp và payload; lỗi giữ đáp án; anchor; reduced motion; cảnh báo dưới 5 phút; hết giờ một POST; ảnh lỗi, retry hidden-lazy và zoom. Hai POST đáp án đều bị chặn bằng Playwright, chỉ trả HTTP giả để kiểm tra lỗi. Không sửa seed mà root dùng cho kiểm thử nộp thật.

Trước đó đã chụp toàn bộ bốn ngữ cảnh standalone/fixed22/diagnostic22/lịch sử tại 375 và 1440, kiểm bốn width không tràn ngang; ảnh còn trong `../screenshots`. Kiểm thử root tổng hợp xác minh lại các ngữ cảnh và POST thật trên database nhớ cô lập; xem báo cáo Phase 6 chung cho số liệu chính thức.

Lệnh chạy khi seed còn chưa nộp:

```sh
PLAYWRIGHT_MODULE=/path/to/playwright node docs/ui-redesign/phase-6/qa/qa-taking.cjs
```

Chỉ dùng bài lịch sử và các POST bị chặn: thêm `TAKING_LEGACY_ONLY=1`. Tệp JSON ghi chính xác ngữ cảnh của lần chạy hiện tại.
