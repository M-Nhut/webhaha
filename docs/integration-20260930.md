# Tích hợp FNWEB2 vào bản gọn — 30/09/2026

## Phạm vi đã hoàn thành

Chuyển các phần còn thiếu từ `FNWEB2` sang `FNWEB2-GỌN HƠN NHƯNG THIẾU`:

- Tạo đề từ ngân hàng: chọn câu thủ công hoặc ngẫu nhiên theo số lượng từng hình thức.
- Chỉnh sửa, xem trước, lưu nháp và giao đề; bảo toàn quyền truy cập và khóa đề đã có bài làm.
- Phân bổ tổng 10 điểm, điểm từng phần và trọng số từng câu; quy đổi hiển thị bài cũ mà không ghi lại kết quả gốc.
- Giao diện xem ma trận, xuất Excel, mẫu bảng và bảng đối chiếu câu; liên kết ma trận xuất hiện sau khi lưu đề.
- Các thay đổi tương ứng ở kết quả bài làm, trang theo dõi của giáo viên và kiểm thử.

Đối chiếu toàn bộ `routes`, `services`, `templates`, `static/js`, `static/css`, `resources`: không còn tệp ứng dụng nguồn nào thiếu ở bản gọn. Các khác biệt còn lại là chỉnh lý có chủ đích: tách tính điểm mặc định khỏi route, định dạng CSS, đưa CSS ma trận ra tệp riêng, giữ mẫu LaTeX có bình luận đã được người dùng tinh gọn. Chi tiết máy đọc được: `reports/integration-parity.json`.

## Tổ chức mã và tài nguyên

- `assessment_scoring.py` chịu trách nhiệm phân bổ và điểm mặc định; route tập trung xử lý yêu cầu và quyền.
- Bộ đọc thông số từng phần dùng chung trong route, giữ tương thích với biểu mẫu cũ.
- CSS đề kiểm tra được trình bày thành từng khối đọc được; CSS ma trận chuyển khỏi HTML.
- Thêm README làm bản đồ mã và hướng dẫn kiểm tra.
- Giữ bản MathJax/Alpine tối giản đã đóng gói. Bổ sung các phụ thuộc JavaScript bị thiếu của bộ TikZ từ bản nguồn, đúng phiên bản cần thiết; không chép toàn bộ thư viện của bản nguồn.
- Build kiểm tra tài nguyên và khả năng nạp bộ TikZ trước khi báo thành công. Cập nhật đường dẫn Node cho máy Windows hiện tại.

Không thay đổi cơ sở dữ liệu thật hoặc các tệp môi trường. Không khôi phục các chức năng thừa đã bị dọn khỏi bản gọn. Mã nguồn FNWEB2 không bị sửa.

## Kiểm chứng

- 76 kiểm thử Python và 9 kiểm thử con đạt: ma trận, thang điểm, đề riêng, cá nhân hóa, ngân hàng tổng quát, bộ TeX, hiển thị LaTeX, báo cáo sai lầm, trang theo dõi học tập.
- Biên dịch TikZ thực tế thành SVG tại máy thành công, không dùng dịch vụ bên ngoài.
- Build tài nguyên và kiểm tra cú pháp JavaScript trình sửa đề thành công.
- Kết quả chi tiết: `reports/integration-verified.xml`.

Giới hạn: chưa thử giao diện trực tiếp trên trình duyệt trong lượt tích hợp này. Không khẳng định toàn bộ bộ kiểm thử lịch sử đều đạt. Nhóm `test_import_duplicates.py` còn 10 lỗi ở cả bản nguồn lẫn bản gọn (đã chạy đối chiếu), liên quan luồng duyệt/phạm vi danh mục cũ; kiểm thử JavaScript ID6/scope cũng có giả định cũ và thiếu đối tượng DOM. Đây là việc cần cập nhật riêng, không được bỏ qua để tuyên bố hệ thống hoàn toàn không còn lỗi. Nhật ký lượt kiểm tra đầu ở `reports/integration-tests.xml` còn ghi lỗi TikZ trước khi sửa; lượt kiểm chứng cuối dùng tệp `integration-verified.xml`.

## Sao lưu

Các tệp đích bị thay thế khi chuyển tính năng đã được lưu tại `backups/integration-20260929-231443`; `manifest.json` ghi tên tệp và SHA-256 trước khi thay. Không khôi phục cả thư mục sao lưu một cách tự động vì có thể ghi đè các thay đổi mới.

Ma trận hiện là bản mô tả đề đã lưu; chưa triển khai nhập ngược ma trận để sinh đề hoặc AI tự bổ sung câu thiếu. Cơ chế này giữ nguyên giới hạn của bản nguồn.
