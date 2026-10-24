# Chuyển phạm vi ID6 sang Toán 9 Chương 8, bài kết hợp `i`

Phạm vi đang hoạt động của ngân hàng câu hỏi là tám dạng `9C8-i-1` đến
`9C8-i-8`, tương ứng Chương 8 và hai bài 25 + 26 được gộp. Ký tự `i` là
chữ thường theo đúng mã nguồn; không được đổi thành `I` khi chuẩn hóa mã.
Tên tám dạng và ánh xạ NB–TH–VD–VDC, T–D–S được giữ nguyên từ danh mục hiện
có để không làm mất ý nghĩa dữ liệu đã duyệt.

## Mã nguồn và nhập file

TeX có thể ghi tiền tố phân loại trong chú thích, chẳng hạn:

```tex
%[9C8Ni-1T]  % Trắc nghiệm
%[9C8Hi-1D]  % Đúng/Sai
%[9C8Vi-2S]  % Trả lời ngắn
```

Mã đầy đủ sau khi lưu có thêm số dương, ví dụ `9C8Ni-1T.12`. Bộ phân tích
chấp nhận cả tiền tố và mã đầy đủ, giữ `i` thường, và từ chối mã Chương 6 cũ
trong luồng hoạt động. Nếu một câu có nhiều tiền tố khác nhau hoặc tiền tố
không khớp phạm vi đã chọn, bản xem trước bị đánh dấu lỗi để giáo viên sửa
file nguồn; hệ thống không đoán lại theo từ khóa, AI, thứ tự câu hay mã dạng.

Tiền tố trong file là dữ liệu phân loại có thẩm quyền. Cấu trúc đáp án do
parser nhận được phải khớp T/D/S; tag `D` không được tự biến câu lựa chọn
thành Đúng/Sai. Việc xác nhận của giáo viên vẫn được giữ, nhưng các trường
chọn thủ công không tự tạo tiền tố và không ghi đè metadata file.

## Cấp số

`ID6Counter` là high-water mark cho từng scope `grade + chapter + bài i +
dạng`, dùng chung cho mọi mức độ và hình thức. Giao dịch lưu dùng cập nhật
nguyên tử để lấy số kế tiếp; số đã xóa không được cấp lại. Hỏi số xem trước
chỉ đọc counter và không tạo dòng counter hay giữ chỗ.

Một file có mã đầy đủ vẫn lưu số do web cấp cho câu mới. Nếu câu đã tồn tại thì ID hiện
có không đổi khi sửa nội dung, đáp án, hoặc điều khiển thích ứng. Chỉ metadata
nguồn hợp lệ mới được phép đi vào biên cấp số.

## Dữ liệu lịch sử và triển khai

Các tên module cũ chứa `chapter6` được giữ làm lớp tương thích, nhưng mọi hằng
số hoạt động và danh mục mà chúng trỏ tới đều là Chương 8 bài `i`. Mã nguồn
ID cũ và bản chụp import cũ phải giữ nguyên để kiểm toán; không sửa snapshot
đã nộp hoặc lịch sử học tập theo kiểu suy đoán. Trước khi áp dụng chuyển dữ
liệu thật, chạy kiểm tra chỉ đọc, tạo backup nhất quán, rồi áp dụng migration
riêng với khóa ghi và kiểm tra toàn vẹn sau giao dịch.

## Đã áp dụng trên dữ liệu cục bộ ngày 2026-09-13

- Đã chuyển 8 node danh mục sang `9C8-i-1` đến `9C8-i-8`, giữ nguyên khóa nội bộ.
- Đã sửa chương/bài của 185 câu; nội dung, đáp án và trạng thái duyệt được giữ nguyên.
- 18 câu có ID cũ đã được đổi tiền tố, giữ số thứ tự. `original_source_id` giữ nguồn để đối soát.
- 167 câu chưa có ID vẫn chưa được gán mã; không suy luận phân loại mới.
- Bộ đếm dạng 1 vẫn là 17, dạng 2 vẫn là 1. Câu mới sẽ tiếp tục từ 18 và 2 tương ứng.
- Đã đóng 1 phiên xem trước `.tex` cũ; giữ file/payload lịch sử. Cần nhập lại file có tiền tố mới.
- 30 bảng ngoài phạm vi chuyển đổi không thay đổi, bao gồm các báo cáo AI lịch sử.
- Không có bài làm/hồ sơ năng lực lịch sử cần chuyển trong DB này.
- Backup đã kiểm tra: `backups/chapter8-i-20260913T161619652620Z/before.sqlite3`.
- Kiểm tra toàn vẹn/khoá ngoại đạt; dry-run sau chuyển không còn mục cần xử lý.

Công cụ cục bộ: `scripts/migrate_local_chapter8_i.py --database tutoring_center.db`.
Mặc định chỉ đọc. Chế độ `--apply --expect <fingerprint>` tạo backup mới, khoá
giao dịch và từ chối khi dữ liệu thay đổi hoặc có lịch sử cần kế hoạch riêng.
Không dùng công cụ này để tự chuyển DB có bài đã nộp.

Parser và bundle được kiểm tra riêng, không khởi động Flask: đủ 8 dạng, nhận
tiền tố/mã đầy đủ mới và từ chối mã Chương 6. Chưa chạy toàn bộ test suite,
trình duyệt hoặc Gemini thật. Sau khi khởi động lại web, nhập một file `.tex`
mới có `%[9C8Ni-1T]` ở từng khối câu hỏi, xem mã nhận diện và xác nhận lưu để
web cấp hậu tố; giữ bước giáo viên duyệt trước khi dùng câu trong đề tự luyện.
