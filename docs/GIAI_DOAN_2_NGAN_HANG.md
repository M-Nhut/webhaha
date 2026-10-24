# Giai đoạn 2 — Ba hình thức và phạm vi file import

Hoàn thành và kiểm tra local ngày 07/09/2026.

> Cập nhật 14/09/2026: tài liệu này giữ lại kết quả lịch sử của giai đoạn 2.
> Theo hợp đồng hiện hành tại [IMPORT_FORMATS.md](IMPORT_FORMATS.md), upload
> ngân hàng chỉ còn `.tex`/`.latex`; các mô tả DOC/DOCX/PDF/MathType bên dưới
> không còn là chức năng được hỗ trợ.

## Kết quả

- Tạo, sửa, nhập câu hỏi và tạo đề mới dùng **Trắc nghiệm một đáp án (T), Đúng/Sai (D), Trả lời ngắn (S)** trong quy chuẩn ID6. Trắc nghiệm cần bốn phương án, một đáp án đúng; Đúng/Sai có bốn mệnh đề và đáp án từng ý; trả lời ngắn nhận đáp án mẫu, hỗ trợ các giá trị cách nhau bằng `|`.
- API kiểm tra hình thức và cấu trúc đáp án. Câu tự luận/nhiều đáp án đọc từ file được báo lỗi để giáo viên chuyển đổi hoặc loại khỏi lô. Dữ liệu lịch sử vẫn đọc được, bộ đọc vẫn hiểu mã TL; bộ cấp mã mới chỉ dùng D/T/S. Bộ chọn câu cho đề mới loại câu không đủ đáp án và các hình thức cũ.
- Sau khi đọc file, bảng **Tệp → Lớp → Chương → Bài → Chủ đề** cho chọn phạm vi. Thay chương hoặc lớp xóa lựa chọn con. Chương 6 hiện chỉ có Bài 4 và đúng một chủ đề **Thống kê và xác suất**.
- Phạm vi được lưu trong `ImportSession.scope_data`, gồm chữ ký danh mục. Tải lại trang giữ phạm vi và ngân hàng đích. Danh mục thay đổi thì yêu cầu lưu lại phạm vi; phiên hết hạn hoặc đã đóng không được chỉnh sửa/xác nhận.
- Chỉ điền metadata khi phạm vi cho kết quả duy nhất. Chọn nhiều bài không ép tất cả câu vào một bài. Metadata tường minh ngoài phạm vi được báo lỗi; nội dung, ảnh và công thức được giữ nguyên.
- Loại câu trong preview được lưu lên máy chủ, giữ số câu nguồn; câu đã loại không quay lại khi tải lại trang hoặc xác nhận.
- Tệp LaTeX hiện hành vẫn có thể biểu diễn ba loại câu D/T/S; parser DOC/DOCX/PDF
  và mẫu DOCX của snapshot lịch sử đã được gỡ.
- Tạo đề thủ công hỗ trợ cả ba hình thức. Mở lại để sửa giữ đáp án từng ý và đáp án ngắn. Đề đã có bài làm được chặn sửa cấu trúc để giữ lịch sử.

## Sử dụng

1. Mở Ngân hàng câu hỏi → Import; tải tệp `.tex` hoặc `.latex`.
2. Chọn lớp 9, Chương 6, Bài 4 và chủ đề; bấm **Lưu phạm vi và xem câu hỏi**.
3. Kiểm tra ba hình thức, đáp án và lỗi; sửa hoặc loại câu cần thiết.
4. Bấm **Xác nhận lưu**, chọn ngân hàng hoặc nhập tên ngân hàng mới, rồi xác nhận import. Nếu mở từ ngân hàng có sẵn, ngân hàng đó được giữ cố định trong phiên.

Chương chưa có nhãn chủ đề hiển thị “Chưa có chủ đề trong danh mục”. Lớp chưa có danh mục cần bổ sung danh mục trước khi chọn phạm vi. Hiện danh mục chuẩn của dự án là Toán 9.

## Kiểm tra

- `python3 -m unittest discover -s tests`: **203 kiểm thử đạt**, gồm hồi quy DOC/DOCX/PDF/TEX, MathType/công thức, cấp ID6 đồng thời và phạm vi Bài 4.
- `node tests/test_id6_picker.js`: đạt; ba hình thức, giữ đáp án khi chuyển loại, chống phản hồi ID cũ ghi đè.
- `node tests/test_import_scope.js`: đạt; kiểm tra chính hàm ghép wizard để bảo đảm danh sách chương/bài/chủ đề cập nhật động, giữ một chủ đề C6 và khôi phục phiên.
- Trình duyệt: chọn Chương 6 → Bài 4 → một chủ đề → lưu phạm vi → tải lại → xác nhận nhập thành công ba câu vào ngân hàng kiểm thử. Tạo đề thủ công có Đúng/Sai và trả lời ngắn thành công; mở sửa vẫn giữ đúng các đáp án.
- Mẫu DOCX được render, kiểm tra trực quan một trang và nhập lại qua API; lưu đủ 4 phương án, 4 mệnh đề, 1 đáp án ngắn.
- `git diff --check`: đạt.

## Cơ sở dữ liệu

Startup bổ sung cột nullable `import_session.scope_data`; không chuyển đổi câu hỏi cũ. Công cụ SQLite độc lập:

```sh
python3 scripts/migrate_import_scope.py tutoring_center.db
```

Công cụ sao lưu trước khi thêm cột, không import ứng dụng hoặc chạy seed; chạy lại không đổi dữ liệu. Tại lần kiểm tra ngày 07/09/2026, DB local đã có cột nên công cụ trả `already_applied`, không tạo bản sao mới. `PRAGMA integrity_check` trả `ok`. Xem `docs/reports/phase2-import-scope-applied.json` và `docs/reports/phase2-verification.json`.

Khi chạy trên một tiến trình ứng dụng cũ, khởi động lại tiến trình để nạp mã Python mới. Không có triển khai remote trong giai đoạn này. Kiểm thử tích hợp đã chạy trên SQLite; PostgreSQL chưa được kiểm thử thực tế trong đợt này.

## Phần tiếp theo theo kế hoạch

Giai đoạn **2a** thực hiện đối chiếu, chỉ số câu trùng và bỏ qua câu trùng khi import bổ sung. Cảnh báo trùng cũ hiện chưa phải cơ chế tự loại trùng. Giai đoạn **3** thực hiện tự phân dạng bài và đánh giá NB–TH–VD–VDC; cơ chế mặc định mức độ cũ chưa được thay thế ở giai đoạn 2. Giai đoạn **4** hoàn thiện duyệt phân loại và cấp ID. Phạm vi file hiện là dữ liệu đầu vào cho các bước tiếp theo, chưa phải kết quả tự phân loại.
