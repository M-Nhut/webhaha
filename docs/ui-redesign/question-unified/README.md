# Đồng bộ khối câu hỏi LMath · 19/10/2026

Đã bỏ liên kết **“Đến cuối bài”** trong từng câu khi làm kiểm tra. Khu vực nộp bài cuối trang, điều hướng câu, thời gian và tiến độ vẫn hoạt động theo luồng hiện có.

Cùng kiểu Soft UI xanh LMath được áp dụng ở màn hình làm bài, xem lại bài đã làm, chi tiết ngân hàng, phân loại, xem trước thêm/sửa câu hỏi, xem trước nhập và đối chiếu câu trùng. Card trắng bo28px, đáp án bo22px có bóng hắt5px; chữ cái A/B/C/D và a–d trong vòng tròn44px trên desktop,38px trên mobile. Nội dung, đáp án và lời giải dùng font Be Vietnam Pro20px. Câu Đúng/Sai và trả lời ngắn dùng cùng viền, góc bo và khoảng cách.

Phần xem lại dùng dấu ✓ xanh cho đáp án đúng và ✕ đỏ cho lựa chọn sai; thông tin học sinh đã chọn được giữ trong nhãn trợ năng. Bài chưa chấm có biểu tượng trung tính. Trạng thái đúng/sai/một phần/bỏ trống/chưa chấm và điểm vẫn được giữ. Xem [cập nhật biểu tượng](../answer-icons/README.md). Các cột đối chiếu Đúng/Sai chuyển thành nhãn trong từng khối trên mobile; vai trò bảng vẫn được giữ. Ngân hàng giữ lazy load đáp án, sửa đáp án và quyền của từng câu.

`static/css/question-content.css` là nguồn chung cho surface, nhãn câu, dữ kiện, nội dung, đáp án, vòng tròn, trả lời ngắn và lời giải. Token hình dáng được đổi từ `--exam-*` sang `--question-*`; các rule cấu trúc trùng trong CSS trang được gỡ. CSS trang giữ bố cục và trạng thái riêng. Đã gỡ selector của liên kết cuối bài và cập nhật phiên bản cache của các tài nguyên liên quan.

## Kiểm chứng

- [82 kiểm thử chức năng đạt](python-tests.json): các bộ Phase4/5/6 về ngân hàng, nhập câu hỏi, làm bài, kết quả, quyền, CSRF và chấm điểm. SQLite memory, lưu trữ tạm; không tải dotenv hoặc gọi dịch vụ ngoài.
- [Giao diện làm bài và kết quả](browser-exam.json):461 kiểm tra trên375/768/1024/1440px. Bao gồm chọn bằng chuột/bàn phím, focus, Đúng/Sai chưa đủ ý, xóa trả lời ngắn, dialog nộp bài, no-JS, bản in, các trạng thái chấm và nhãn khi giáo viên xem bài.
- [Ngân hàng và xem trước](browser-bank.json):396 kiểm tra ở bốn kích thước màn hình, tải chi tiết, ba dạng câu hỏi, MathJax, xem trước thêm/sửa, phân loại, nhập và đối chiếu câu trùng. Các kiểm tra browser chỉ thay đổi trạng thái UI và đăng nhập trên preview giả lập.
- [Kiểm tra tĩnh](static-qa.json):49 template và31 CSS parse hợp lệ, không token thiếu; thuộc tính form/control làm bài giữ nguyên, không còn selector liên kết cuối bài hoặc token cấu trúc cũ.

Script tái kiểm tra: [exam](qa-exam.cjs), [bank](qa-bank.cjs), [syntax](qa-static.py). Browser dùng preview riêng `http://127.0.0.1:8772`, tạo bởi `scripts/preview_ui_phase6.py`; không dùng dữ liệu vận hành.

Ảnh tham khảo: [làm bài Đúng/Sai mobile](screenshots/take-truth-375.png), [xem lại trắc nghiệm mobile](screenshots/review-choice-375.png), [xem lại Đúng/Sai desktop](screenshots/review-truth-1440.png).

Đã xem ảnh desktop/mobile sau kiểm tra. Ảnh riêng từng card tạm ẩn thanh header trong lúc chụp và tăng chiều cao viewport khi cần để không che/cắt card; các quy tắc này chỉ nằm trong script chụp ảnh, không thay đổi giao diện chạy thật.
