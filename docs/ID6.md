# Chuẩn ID6 Ngân hàng câu hỏi Toán 9

Chuẩn ID duy nhất:
```text
9C8{mức độ}i-{dạng kiến thức}{loại câu}.{số thứ tự}

Mức độ: N / H / V / C
Dạng kiến thức: 1–8
Loại câu: T = Trắc nghiệm, D = Đúng/Sai, S = Trả lời ngắn
```

Ví dụ:
```text
9C8Ni-1T.12
9C8Hi-2D.5
9C8Vi-3S.8
```

## 1. Quy ước thành phần
- **Mức độ nhận thức**:
  - `N`: Nhận biết (`nhan_biet`)
  - `H`: Thông hiểu (`thong_hieu`)
  - `V`: Vận dụng (`van_dung`)
  - `C`: Vận dụng cao (`van_dung_cao`)
- **Phạm vi kiến thức**: Lớp 9, Chương 8, bài kết hợp `i` (Bài 25 + 26 gộp). Dạng kiến thức từ `1` đến `8`.
- **Loại câu hỏi**:
  - `T`: Trắc nghiệm 4 phương án, 1 đáp án đúng (`single`)
  - `D`: Đúng/Sai 4 mệnh đề (`true_false`)
  - `S`: Trả lời ngắn (`short_answer`)
- **Số thứ tự**: Số nguyên dương (`1, 2, 3...`), được cấp tự động bởi bộ đếm `ID6Counter` theo phạm vi `9C8-i-{dạng}` khi xác nhận lưu vào ngân hàng câu hỏi.

## 2. Luồng xử lý import TeX
1. **Đọc ID từ .tex**: Tiền tố hoặc mã đầy đủ được ghi chú trong file `.tex`, ví dụ:
   ```latex
   %[9C8Ni-1T]
   %[9C8Hi-2D]
   %[9C8Vi-3S]
   ```
2. **Kiểm tra cấu trúc và loại câu**: Parser xác thực định dạng ID và đảm bảo cấu trúc nội dung câu hỏi khớp với loại câu (`T`, `D`, hoặc `S`).
3. **Giáo viên xem, chỉnh và xác nhận import**: Giao diện preview hiển thị rõ ràng nhãn `T · Trắc nghiệm`, `D · Đúng/Sai`, `S · Trả lời ngắn`.
4. **Cấp số thứ tự**: Bộ đếm nguyên tử `ID6Counter` cấp số thứ tự tăng dần theo scope dạng kiến thức `(id6_scope, id6_sequence)`.
5. **Lưu câu hỏi**: Câu hỏi được lưu vào `bank_question` với `source_id`, `id6_scope`, `id6_sequence`.

## 3. Nội bộ hệ thống
- Các thuật toán sinh đề 22 câu, chấm điểm thi và cá nhân hóa học tập tiếp tục sử dụng các mã nội bộ: `single`, `true_false`, `short_answer`.
- Database chỉ lưu `source_id`, `id6_scope`, `id6_sequence`, không còn các trường hay bảng tương thích cũ.
