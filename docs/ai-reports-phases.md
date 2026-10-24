# Báo cáo AI · Các phase triển khai

## Phase 1 — Dữ liệu và API

Đã triển khai:

- `services/ai_report_overview.py`: thống kê đúng/sai/chưa đủ ý, số bài, học sinh có dữ liệu, tỷ lệ, dạng cần xem lại, adapter báo cáo.
- `routes/ai_reports.py`: hai trang `/ai-reports/class` và `/ai-reports/individual`; `/ai-reports` chuyển tiếp liên kết cũ. API `/api/ai-reports/<course_id>` kiểm tra lớp phụ trách và ghi danh cá nhân; response private/no-store.
- Bộ lọc dạng kiến thức, loại câu và nguồn bài làm. Thống kê dùng dữ liệu quan sát đầy đủ trong phạm vi Bài 25 + 26, không lấy mẫu số từ bản lỗi rút gọn gửi AI.
- Hàm đọc báo cáo lớp được tái sử dụng giữa endpoint cũ và giao diện mới.

## Phase 2 — Tổng quan lớp và cá nhân

Đã triển khai:

- `templates/ai_reports.html`, `static/css/ai-reports.css`, `static/js/modules/ai_reports.js`.
- Bộ chọn lớp/học sinh, KPI, biểu đồ cột nhóm, biểu đồ tròn doughnut, bảng theo dạng và bảng học sinh.
- Menu bên trái có một mục Báo cáo AI. Bên trong trang có hai tab nhỏ Cả lớp và Cá nhân. Cả lớp chỉ chọn lớp; Cá nhân chọn lớp và học sinh, mặc định học sinh đầu tiên. Lớp không có học sinh có thông báo riêng.
- Tổng quan nhúng dữ liệu quan sát vào HTML, dựng sẵn biểu đồ bằng JavaScript mà không cần đợi fetch/API AI. Tải lại và bộ lọc chỉ đọc dữ liệu bài làm; không đọc cấu hình hay kết quả AI.
- Chọn dạng trên biểu đồ để lọc dữ liệu; chọn trạng thái trên chú giải biểu đồ tròn để lọc bài làm. Bảng/nút cung cấp thao tác bằng bàn phím.
- Biểu đồ được dựng bằng HTML/CSS và SVG trực tiếp, không cần tải thư viện biểu đồ mới. Màu sắc, viền và card theo Neo-Brutalism × Cartoon Pop.
- Giữ bộ lọc dạng/nguồn/loại câu khi đổi tổng quan/chi tiết hoặc mở học sinh.
- Không có dữ liệu thì hiển thị trạng thái thiếu dữ liệu, không 0% đúng.

## Phase 3 — Phân tích AI và chi tiết

Đã triển khai:

- Prompt `class-c8-i-v8-teacher-support` yêu cầu tóm tắt, giả thuyết nguyên nhân, nguy cơ sai lần tiếp theo và khuyến nghị hướng dạy cho lớp và từng học sinh có dữ liệu.
- Khuyến nghị giữ các trường mục tiêu cần củng cố, cách hướng dẫn của giáo viên, câu hỏi gợi mở, bài luyện gợi ý và tiêu chí kiểm tra tiến bộ; hiển thị thành các dòng riêng trong card.
- Khi có bằng chứng lỗi, báo cáo mới phải có ít nhất một giả thuyết nguyên nhân, một nguy cơ có điều kiện và khuyến nghị gắn bằng chứng. Validator kiểm tra cả cấu trúc lẫn bằng chứng; phản hồi thiếu phần bắt buộc báo lỗi để cập nhật lại, không tự viết nhận định AI thay thế.
- Khi chưa ghi nhận lỗi, không tạo giả thuyết lỗi; AI vẫn trả tóm tắt và hướng dạy kiểm tra thêm. Bộ đếm tổng quan giữ nguyên. Các ý Đúng/Sai đã trả lời sai trong câu chưa đủ ý cũng có thể làm căn cứ cho nguyên nhân và nguy cơ.
- Validator kiểm tra cấu trúc, bằng chứng, chủ sở hữu học sinh và giả thuyết chưa kiểm chứng. Nguyên nhân phải dẫn lỗi có thật, gồm ý Đúng/Sai sai trong câu chưa trả lời đủ.
- AI nhận bản sao lỗi và thống kê số lượt đúng/sai/chưa đủ ý ẩn danh. Bài làm đúng chi tiết, tên và thông tin liên hệ không được đưa thêm vào payload AI.
- Bản phân tích giữ tóm tắt, lỗi quan sát, nguyên nhân, nguy cơ, khuyến nghị và bằng chứng. Dữ liệu quan sát và dấu hiệu đúng sau sai vẫn xem được khi chưa có AI.
- Giáo viên bấm Chi tiết từ tổng quan sẽ gửi POST với `force: true`, tạo phân tích mới ngay cả khi dữ liệu không đổi; tóm tắt và nhận định AI chỉ hiển thị ở Chi tiết. Mở tổng quan không gọi AI. Sau khi bắt đầu, gỡ cờ refresh khỏi URL để tải lại trang không tự phát sinh yêu cầu mới.
- Bản lớp chứa phân tích lớp và từng học sinh; Chi tiết cá nhân hiển thị phần của học sinh được chọn, còn API tạo vẫn cập nhật bản phân tích lớp hiện có.
- Giữ coalescing của yêu cầu đang xử lý để tránh chạy trùng. Với kết quả processing, giao diện đọc lại mỗi 5 giây, tối đa 6 phút; không tạo thêm yêu cầu AI. Có nút Phân tích lại bằng AI, trạng thái chờ, lỗi và dấu thời điểm trả về.
- Phân tích cá nhân từng bài đã lưu được đọc trong mục thu gọn riêng, có thời điểm và phạm vi; không cộng vào thống kê mới.
- Bằng chứng phân trang 20 lượt, có nội dung câu hỏi, đáp án, từng ý Đúng/Sai và công thức/hình minh họa.

## Phase 4 — Điều hướng

Đã triển khai:

- Thêm một mục Báo cáo AI cho giáo viên/quản trị viên, luôn được đánh dấu đang chọn ở cả hai tab Cả lớp và Cá nhân bên trong trang. Quản trị viên vẫn chỉ đọc bản lưu, không gọi khóa AI của giáo viên.
- Trang lớp thay phần báo cáo dài bằng nút Mở Báo cáo AI, vẫn giữ anchor cũ để liên kết trước đây còn có đích.
- Trang theo dõi cá nhân có liên kết tới báo cáo riêng theo lớp.
- Giữ quyền gọi API của giáo viên phụ trách; quản trị viên xem theo quyền hiện có.

## Phase 5 — Rà soát tĩnh

- Đã kiểm tra cú pháp Python, Jinja và JavaScript của các file sửa.
- Đã đọc lại luồng phân quyền, phạm vi và cách đếm; không đếm các ý Đúng/Sai lần nữa vào mẫu số câu.
- Đã rà soát trạng thái đang tải, dữ liệu rỗng, thiếu AI, đang phân tích, báo cáo cũ và API lỗi trong mã nguồn.

Chưa chạy bộ kiểm thử chức năng, chưa khởi động host để kiểm tra trực quan và chưa gọi API AI thật. Không thay đổi cơ sở dữ liệu hoặc cần migration cho giao diện này.

## Cách mở

Khởi động ứng dụng hiện có, đăng nhập giáo viên hoặc quản trị viên và vào **Báo cáo AI → Cả lớp / Cá nhân**. Tổng quan có ngay thống kê và biểu đồ từ dữ liệu đã chấm. Giáo viên bấm **Chi tiết** để nhận phân tích mới từ AI. Giới hạn nội dung vẫn là Toán 9, Bài 25 + 26 như service hiện tại.
