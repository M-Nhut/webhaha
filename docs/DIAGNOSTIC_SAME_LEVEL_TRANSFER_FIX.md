# Sửa lỗi tạo đề đầu vào khi một dạng thiếu câu

Ngày: 07/10/2026.

## Nguyên nhân lỗi trong ảnh

Thông báo “thiếu 3 câu kiến thức 9C8-i-6 (cần 3, có 0)” phát sinh ở `POST /diagnostics/new`. Các phase trước nối bộ phục hồi vào đề luyện tập cá nhân hóa, nhưng `common_diagnostic_selection` vẫn gọi riêng `select_fixed`, bắt buộc đúng quota từng dạng. Ngoài ra, kiểm tra đầu vào của học sinh và nguồn lớp vẫn yêu cầu đề có đủ 8 dạng, kể cả khi ngân hàng thiếu hoàn toàn một dạng. Các kiểm thử phase trước chưa tái hiện luồng POST này với một dạng trống.

## Hành vi đã sửa

1. Đề đầu vào dùng chung và đề cá nhân hóa thử quota dạng ban đầu trước. Nếu không ghép được, chúng dùng bộ chọn dạng thay thế cùng mức độ.
2. Các luồng sản xuất truyền `SystemRandom` để xáo thứ tự các dạng thay thế trong từng nhóm hình thức × mức độ. Xáo theo dạng, không cấp thêm lượt chọn cho dạng có nhiều câu hơn. Không cam kết mọi đề khả thi có cùng xác suất.
3. Giữ chính xác quota mức độ và ba hình thức câu hỏi; không đổi nhãn câu, không trùng nội dung. Nguồn thay thế vẫn là các câu đã duyệt mà giáo viên của lớp được phép dùng trong ngân hàng đã chọn.
4. Đề đầu vào vẫn có 22 câu: NB/TH/VD/VDC = 9/7/4/2; chọn đáp án/Đúng–Sai/trả lời ngắn = 12/4/6. Quota mức của đề cá nhân hóa giữ theo hồ sơ riêng, không đổi sang phân bố đầu vào.
5. Nếu thiếu toàn bộ một dạng, đề phủ các dạng có câu hợp lệ, tối đa 5 câu/dạng theo hợp đồng hiện tại. Phần ghi nhận lưu dạng nguồn, dạng nhận, mức độ, hình thức và ID câu thay thế. Bước kiểm tra đề đối chiếu thông tin này với bản câu hỏi đã đóng băng để học sinh được mở đề hợp lệ.
6. Chỉ chọn một bộ đề chung khi giáo viên tạo; cả lớp và học sinh ghi danh sau nhận cùng bộ câu, cùng hash. Không chọn lại ngẫu nhiên cho mỗi học sinh.
7. Trang tạo đề giải thích quy tắc mới; thông báo thành công và danh sách đề hiển thị số câu thay thế, độ phủ thực tế.

Nếu mọi dạng đều thiếu câu ở mức cần lấy, không thể bù bằng mức khác. Hệ thống vẫn thông báo thiếu câu thực tế hoặc giới hạn tìm kiếm, không tạo đề thiếu câu hay hạ độ khó.

Các lời gọi bộ chọn phục hồi trực tiếp không truyền RNG vẫn giữ thứ tự theo ưu tiên để chạy đánh giá ngoại tuyến có thể lặp lại. Hai luồng tạo đề thực tế đều đã bật chọn ngẫu nhiên khi phục hồi.

## Kiểm chứng đúng trường hợp đang lỗi

Kiểm tra trên bản sao tạm của `tutoring_center.db`, không sửa dữ liệu gốc và không gọi AI:

- Nguồn của lớp có 129 câu đủ điều kiện, thiếu toàn bộ `9C8-i-6`.
- POST tạo đề thành công: đủ 22 câu, chuyển 3 vị trí sang dạng khác, phủ 7/8 dạng.
- Mức độ thực tế = 9/7/4/2; hình thức thực tế = 12/4/6; không trùng nội dung.
- Manifest hợp lệ; toàn bộ 3 học sinh được giao cùng hash và đều mở `/practice/<exam_id>/take` với HTTP 200.
- 10 lượt có seed để đối chiếu đều tạo đủ 22 câu. Có 10 tổ hợp dạng nhận câu thay thế khác nhau.
- SHA-256 dữ liệu gốc trước/sau không đổi.

Dữ liệu kiểm chứng: `docs/reports/diagnostic-same-level-real-source.json`.

Công cụ chạy lại kiểm tra nguồn thực tế trên bản sao tạm:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/evaluate_common_diagnostic_transfer.py \
  --database tutoring_center.db \
  --output /private/tmp/diagnostic-transfer-check.json
```

## Kiểm thử hồi quy

**105 passed, 4 subtests passed**. Thêm 7 kiểm thử về tạo đề thiếu dạng 6, học sinh mở đề, bộ đề cố định cho cả lớp và ghi danh sau, dạng thay thế ngẫu nhiên, thiếu ô vận dụng cao, thiếu toàn bộ mức khó, thông tin phục hồi sai và việc giữ bộ lọc nguồn. Kiểm thử mới dùng request thật qua Flask test client thay vì chỉ gọi bộ chọn.

Các nhóm kiểm thử bao gồm sinh đề, phân bổ APTGA, nguồn lớp và quyền sử dụng ngân hàng, chu trình luyện tập, tạo đề đầu vào, báo cáo và xóa đánh giá. Log: `docs/reports/diagnostic-same-level-regression.txt`.
