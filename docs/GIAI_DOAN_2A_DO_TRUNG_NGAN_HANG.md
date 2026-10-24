# Giai đoạn 2a — Nhập bổ sung và dò câu trùng

Hoàn thành và kiểm tra local ngày 08/09/2026.

Khi giáo viên nhập file vào một ngân hàng có sẵn, hệ thống dò toàn bộ câu của ngân hàng đó, kể cả câu chưa có mã ID6, đồng thời dò các câu lặp ngay trong file. Mỗi dòng giữ nhãn nguồn ổn định như phần/trang/câu gốc hoặc thứ tự trích xuất.

Nội dung, ngữ cảnh, phương án/mệnh đề, số liệu, ký hiệu toán, công thức và hình được chuẩn hóa bảo thủ trước khi so sánh. Thay đổi số liệu, dấu toán, số mũ, bất đẳng thức, hình hoặc công thức không bị tự gộp. Phương án được phép đảo thứ tự chỉ khi không có tham chiếu vị trí như A/B, “ý trên”, “cả hai phương án”. Câu có tài sản hình/công thức không xác minh được hoặc gần giống được đưa vào **Cần đối chiếu**, không tự loại.

Giao diện hiển thị số câu mới, câu trùng bị bỏ qua, câu cần đối chiếu, nhãn nguồn và liên kết tới câu gốc trong ngân hàng. Giáo viên có thể xác nhận “trùng” hoặc “khác nhau”; có thể lưu các câu mới trước, sau đó mở lại phiên để xử lý các câu còn lại. Câu trùng nhưng khác đáp án/lời giải được báo rõ, không ghi đè câu đã có. File nguồn chỉ tải được bởi chủ phiên khi phiên còn mở.

Lần lưu cuối dò lại trong giao dịch khóa ghi: SQLite dùng `BEGIN IMMEDIATE`, PostgreSQL khóa các bảng import/ngân hàng/câu hỏi/phương án. Hai lượt nhập đồng thời vì vậy chỉ thêm một câu. Biên nhận được lưu theo mã xác nhận; gửi lại yêu cầu hoặc retry sau lỗi hậu xử lý trả về đúng biên nhận cũ, không thêm lại. Lô toàn câu trùng kết thúc với báo cáo thêm 0 câu và không cấp ID mới.

Các cột nullable mới của `import_session` là `duplicate_decisions`, `duplicate_report`, `result_data`. Ứng dụng tự bổ sung cột khi khởi động; với SQLite đang vận hành có thể dùng công cụ độc lập, công cụ sao lưu trước khi đổi schema:

```sh
python3 scripts/migrate_import_duplicates.py tutoring_center.db
```

Kiểm tra đạt: `python3 -m unittest discover -s tests` với **157 kiểm thử**, gồm 12 ca riêng cho dò trùng: lặp file, lặp nội bộ file, đảo phương án, khác số liệu/ký hiệu, công thức/hình, quyết định đối chiếu, đổi ngân hàng, quyền truy cập, nhãn DOCX, retry và hai phiên đồng thời. `node --test tests/test_import_scope.js` cũng đạt. Kiểm thử giao diện tự động qua trình duyệt cục bộ không chạy được vì trình duyệt của môi trường chặn `127.0.0.1`; các API và trạng thái giao diện được bao phủ qua kiểm thử tích hợp.

Giai đoạn 3 vẫn là bước kế tiếp: tự phân dạng Chương 6 và đề xuất NB–TH–VD–VDC. Giai đoạn 2a chỉ quyết định câu nào được đi tiếp vào bước phân loại, không tự gán dạng hay mức độ.
