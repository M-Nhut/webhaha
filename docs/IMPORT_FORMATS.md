# Hợp đồng định dạng nhập ngân hàng câu hỏi

Cập nhật 14/09/2026: luồng nhập ngân hàng chỉ nhận tệp nguồn LaTeX có phần mở
rộng `.tex` hoặc `.latex`. `services/import_service.py` là điểm kiểm tra cuối;
`services/latex_parser.py` là parser duy nhất được gọi sau khi upload.

Các parser và route tạo mẫu DOC/DOCX/PDF đã được gỡ. Giao diện import cũng chỉ
hiển thị hướng dẫn LaTeX và từ chối các phần mở rộng còn lại trước khi tạo
`ImportSession` hoặc ghi tệp tạm.

## Ranh giới với công thức và tài liệu hiện có

- Ảnh, MathML, LaTeX và SVG cache đã được lưu từ trước vẫn được hiển thị theo
  đường generic của question bank; không xóa asset, thư mục upload hoặc dữ liệu
  câu hỏi trong thay đổi này.
- Bộ render TeX vẫn có thể tạo PDF trung gian rồi chuyển sang SVG. PDF ở đây là
  chi tiết nội bộ của render LaTeX, không phải định dạng upload.
- Các cột metadata converter legacy còn lại trong `FormulaAsset` không được đưa
  ra API. Cột binary MathType `mtef_data` đã được loại khỏi model; việc DROP
  COLUMN đã được áp dụng cho SQLite local sau khi xác nhận cột hoàn toàn trống.
- Dữ liệu phiên import cũ không phải TeX vẫn có thể đọc phần preview đã lưu,
  nhưng không được chỉnh sửa hoặc xác nhận nhập thêm vào ngân hàng.

## Kết quả dọn dữ liệu local

- Ngày 14/09/2026, đã chuyển 7 file DOCX nguồn tạm không được DB tham chiếu
  sang `backups/tex-only-import-20260914T024730Z/`; có manifest và bản sao
  SQLite trước thay đổi. File TeX nguồn được giữ nguyên.
- Đã chuyển cache của các parser bị gỡ và folder cache MathType vào cùng bản
  sao lưu. Không xóa tài liệu Word do người dùng yêu cầu xuất.
- Đã xóa cột trống `formula_asset.mtef_data`; giữ 185 câu hỏi và 182 công thức
  LaTeX. Kiểm tra toàn vẹn và khóa ngoại SQLite đạt.
- Python compileall và 12 kiểm thử mục tiêu về nhập file, ba loại câu và công
  thức đạt. Không chạy toàn bộ bộ kiểm thử hoặc kiểm thử giao diện thủ công.

## Tiêu chí kiểm tra

- Upload `.tex` và `.latex` gọi parser LaTeX, giữ ID6 C8 i/suffix web, ba loại
  câu D/T/S, ngân hàng, tự luyện và chấm tự động.
- Upload `.doc`, `.docx` hoặc `.pdf` trả lỗi định dạng và không tạo phiên.
- Không còn import-time hoặc runtime import tới parser DOCX/PDF/Word,
  MathType worker/converter; không còn route tải mẫu DOCX.
- Kiểm tra cú pháp Python/JavaScript và các test import/formula/route mục tiêu
  phải đạt; không dùng kết quả của full suite cũ làm tiêu chí hồi quy cho phạm
  vi đã thay đổi.
