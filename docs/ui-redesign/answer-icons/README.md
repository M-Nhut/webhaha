# Biểu tượng đáp án khi xem lại bài · 19/10/2026

Đã thay chữ “Bạn chọn” / “Học sinh chọn” và “Đáp án đúng” trong từng phương án bằng biểu tượng:

- ✓ xanh cho đáp án đúng; khi học sinh chọn đúng chỉ hiện một dấu ✓.
- ✕ đỏ cho phương án học sinh đã chọn sai.
- Biểu tượng trung tính cho lựa chọn chưa chấm; các phương án còn lại không có biểu tượng.

Biểu tượng nằm ở mép phải, kích thước28px trong vùng32px. Bỏ vùng nhãn190px và quy tắc xuống dòng cũ trên mobile để dành thêm chỗ cho nội dung. Màu dùng token thành công/lỗi hiện có, card và vòng tròn chữ cái giữ kiểu chung. Nhãn trợ năng vẫn mô tả đáp án và lựa chọn của học sinh. SVG được render trực tiếp nên vẫn hiện khi tắt JavaScript và khi in.

Đã xóa selector badge cũ, tăng phiên bản cache CSS kết quả và cập nhật các kiểm tra badge trong script QA dùng chung. Không đổi chấm điểm, dữ liệu bài làm hay nút thao tác ngân hàng.

Kiểm chứng: [142 kiểm tra browser đạt](browser-qa.json) trên375/768/1024/1440px, gồm nhãn trợ năng, màu, vị trí, bản in và tắt JavaScript; [kiểm tra cú pháp, control và nhánh chưa chấm](static-semantic-qa.json) đạt. Đã xem ảnh đáp án đúng/sai trên desktop và mobile. Các lượt kiểm tra dùng preview/dữ liệu SQLite memory riêng; không truy cập dữ liệu vận hành.

Ảnh: [mobile](screenshots/incorrect-375.png), [desktop](screenshots/incorrect-1440.png).
