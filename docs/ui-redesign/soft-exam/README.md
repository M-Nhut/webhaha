# Khối câu hỏi Soft UI · 19/10/2026

**Bản hiện tại:** Thành phần câu hỏi đã được mở rộng dùng chung cho ngân hàng và xem lại bài, đồng thời bỏ liên kết “Đến cuối bài”. Xem [báo cáo đồng bộ](../question-unified/README.md). Các kết quả phía dưới ghi lại lần triển khai màn hình làm bài ban đầu.

Mẫu người dùng gần với **Soft UI / Soft 3D**, pha **Claymorphism nhẹ**: nền pastel, card trắng bo lớn, bóng hắt xuống tạo độ nổi, nhãn dạng pill và chữ cái đáp án trong vòng tròn. Đây là mô tả hướng thị giác của ảnh, không coi là một bộ UI riêng.

Đã áp dụng cho màn hình làm bài học sinh dùng chung: kiểm tra độc lập, đánh giá đầu vào và tự luyện. Trang quản lý và trang đăng nhập giữ hệ thống màu hiện tại. Theo yêu cầu tiếp theo, toàn bộ màu dùng bảng xanh LMath: accent blue700, hover blue800, nền slate50 và xanh50/100 cho vùng nhấn. Đã gỡ các token tím không còn consumer. Primitive/component token nằm trong `tokens.css`, phạm vi `.academy-exam-focus`.

- Card câu hỏi bo28px, đáp án bo22px, nền trắng và bóng hắt5px. Nhãn câu hỏi pill; chỉ bài luyện có cấu trúc cố định mới hiện tên phần đúng dữ liệu. Điểm câu hỏi vẫn hiển thị.
- Đáp án A/B/C/D có vòng tròn chữ cái, hover/focus rõ; khi chọn có nền nhấn, viền đậm, vòng tròn tô màu và dấu tích. Input radio/checkbox vẫn native, có thể chọn bằng bàn phím và không JavaScript.
- Đúng/Sai có khối ý riêng và lựa chọn dạng pill; trả lời ngắn có ô bo lớn. Timer, tiến độ, lựa chọn câu, nộp bài, thông báo và dialog dùng cùng ngôn ngữ thiết kế.
- Giữ font Be Vietnam Pro, vùng đọc20px, renderer toán, name/value/CSRF/timing fields, rule chấm và quyền. Không thêm chức năng đánh dấu cờ chưa có trong nghiệp vụ. Print bỏ bóng và giữ ký tự đáp án đọc được khi không in nền.
- Thay các rule hiện có trong `exam-taking.css`, không thêm theme cũ hoặc lớp override trang dùng song song. Cache CSS chung và CSS màn hình đã được cập nhật.

## Kiểm chứng

- [29 kiểm tra Python đạt](python-tests.json), [log](python-tests.log): các ngữ cảnh take/result, quyền, CSRF, tính điểm, thang10, nộp một lần và transaction. SQLite memory, file tạm, không dotenv/request ngoài.
- [234 kiểm tra browser đạt](browser-qa.json):375/768/1024/1440px × standalone/fixed/diagnostic/legacy; native selection bằng chuột/bàn phím, focus, dấu chọn, TF partial, xóa short answer, dialog, một bài nộp thật trong DB giả lập đạt10điểm, no-JS, print và không lỗiJS/asset.
- [Kiểm tra tĩnh](static-qa.json): CSS/Jinja parse không lỗi, không token thiếu; toàn bộ tags form/input/textarea/select/button giữ nguyên. Review template8 biến thể và review độc lập CSS scope/contrast đã hoàn tất.
- [Tương phản](contrast.json): chữ xanh trên xanh nhạt6.16:1, trắng trên xanh6.70:1, viền control trên trắng3.51:1, chữ nội dung trên trắng17.85:1.
- Đã xem ảnh câu hỏi, Đúng/Sai và trả lời ngắn trên mobile, card câu hỏi desktop. [Bản in đáp án đang chọn](selected-print-qa.json) được kiểm tra riêng để bảo đảm selector trạng thái không ghi đè reset print.

**Cập nhật bảng xanh:** [kiểm tra palette](blue-palette-qa.json) và bản in đang chọn đạt trên375/1440px; đã chụp lại cả câu hỏi chưa chọn/đã chọn, Đúng/Sai và trả lời ngắn.234 kiểm tra tương tác phía trên là lượt chạy trước thay đổi chỉ về màu; markup, kích thước và logic tiếp tục giữ nguyên.

Ảnh: [Câu hỏi mobile](screenshots/question-card-375.png), [desktop](screenshots/question-card-1440.png), [Đúng/Sai](screenshots/true-false-375.png), [trả lời ngắn](screenshots/short-answer-375.png), [đáp án đang chọn](screenshots/selected-card-375.png).

QA dùng preview riêng tại`http://127.0.0.1:8772`, tạo bởi`scripts/preview_ui_phase6.py`; bản8771 đang có fixture phát triển tích lũy, không dùng để kiểm tra nộp bài lần này. [Script kiểm tra](qa-soft-exam.cjs) và [chụp card/in](capture-cards.cjs). Chỉ preview giả lập bị thay đổi bởi nộp bài.
