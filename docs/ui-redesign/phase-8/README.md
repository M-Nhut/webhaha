# Phase 8 — Dashboard, lớp học, người dùng và báo cáo AI

Ngày nghiệm thu: **17/10/2026**. Hoàn thành S21–S29 theo Modern White Academy và đặc tả Phase 2. Đây là phần triển khai giao diện đang hoạt động cuối cùng trong nhóm Phase 3–8; Phase 9 vẫn là bước rà soát toàn hệ thống, chưa triển khai trong yêu cầu này.

## Giao diện đã thay

| Màn hình | Kết quả |
|---|---|
| S21 · Tổng quan | Hai KPI theo vai trò, hoạt động có thời điểm và lối vào phù hợp; bỏ banner/logo lớn, không dựng lịch hay nhiệm vụ giả. |
| S22 · Danh sách lớp | Bảng desktop, thẻ mobile, thông tin giáo viên/trạng thái và thao tác đúng quyền; xác nhận xóa ghi rõ lớp. |
| S23 · Tạo/sửa lớp | Form 760px, nhóm thông tin–ngày–giáo viên, preview giáo viên, validation liên kết tới field. Giữ các field hiện có và ngữ nghĩa đổi giáo viên/nguồn khóa AI. |
| S24 · Chi tiết lớp | Summary 280px, danh sách/ghi danh là vùng chính, mobile thu gọn thông tin lớp. Liên kết theo dõi/AI giữ lớp và anchor `lesson4-ai-report`. |
| S25 · Học sinh của tôi | Danh bạ giáo viên chỉ đọc, thẻ có nhãn trên mobile, đủ tên/mã/vị trí/liên hệ và trạng thái trống. |
| S26 · Người dùng | Hai tab học sinh/giáo viên, native dialog tạo tài khoản, body cuộn và actions luôn hiện; xác nhận xóa theo tên. |
| S27 · Sửa tài khoản | Form hồ sơ, role student/teacher, khóa/mở; reset mật khẩu là form phụ riêng có xác nhận. Admin protected chỉ đọc. |
| S28 · Báo cáo AI | Đủ lớp/cá nhân × tổng quan/chi tiết. Số liệu quan sát, giả thuyết và hướng hỗ trợ tách rõ; biểu đồ cục bộ, bảng thay thế, bộ lọc, đối chiếu, phân trang và bản lưu cá nhân. |
| S29 · Khóa AI của tôi | Một cấu hình mặc định thuộc giáo viên; nhập tối đa 20 khóa, chỉ hiện dạng che. Phân biệt đã xác minh, lỗi, tạm dừng và chờ hạn mức; xác nhận xóa native. |

Tất cả dùng token/font/palette hiện có, không thêm framework hoặc tài nguyên CDN. Kiểm tra 375/768/1024/1440px; dialog còn được kiểm tra ở màn hình thấp và ngang. Avatar mặc định dùng SVG trực tiếp để tránh request ảnh mặc định bị thiếu.

## Chức năng và sửa lỗi kèm theo

- Giữ quyền và CSRF: CRUD lớp/người dùng/ghi danh thuộc admin; danh bạ thuộc giáo viên; học sinh chỉ xem trong phạm vi lớp. Admin không dùng khóa của giáo viên để phát sinh AI; quyền đối chiếu báo cáo hiện có được giữ.
- Giữ nguồn dữ liệu thật: không trộn điểm standalone vào hồ sơ luyện tập, không biến tỷ lệ thiếu dữ liệu thành 0, không dùng bản sao AI bị giới hạn làm mẫu số biểu đồ.
- API báo cáo giữ no-store, request sequence, polling, bộ lọc và phân trang 20 bằng chứng. Mở chi tiết với `refresh=1` vẫn có thể phát sinh yêu cầu mới; giao diện giải thích hạn mức/phí. Nút tải lại chỉ đọc báo cáo hiện có.
- Sửa form người dùng có thể trả 500 khi trùng username/mã: kiểm tra bắt buộc, trim, độ dài và trùng; xử lý `IntegrityError` bằng rollback/flash an toàn. Lỗi sửa giữ giá trị đã nhập, không ghi một phần vào DB. Giữ mật khẩu mặc định 123456 theo contract cũ.
- Sửa hiển thị các khuyến nghị dạng chuỗi trong bản lưu AI; khóa bị tạm dừng vẫn hiện lý do kiểm tra thất bại.

## Dọn giao diện cũ

- Thay trực tiếp `ai-reports.css` và markup sinh từ `ai_reports.js`; thêm CSS trang riêng cho dashboard, người dùng, lớp học và khóa AI.
- Gỡ **110 inline style trong 9 template**, một style sinh trong JS, cùng các handler inline của nhóm này. JSON dữ liệu và hook tương tác có consumer được giữ.
- Xóa `pages/workspaces.css`; các rule số câu/công thức còn dùng chuyển sang `question-content.css`. `main.css` chỉ nhập nền tảng và nội dung câu dùng chung.
- Gỡ **44 tên class CSS chung cũ** hết dùng; `question-document.css` chỉ giữ bảng TeX và dùng token. Những `!important` còn lại ở bảng toán phục vụ renderer, không phải lớp theme ghi đè.
- Xóa `class_learning_report.js`, partial `components/diagnostic_report.html` và preview cũ hết consumer. Test contract bản lưu chuyển sang adapter hiện có; hướng dẫn preview được cập nhật.
- Không xóa ảnh/upload, công thức, dữ liệu, API hoặc thư viện còn dùng. Template `teacher_analytics.html` không có route render và các ứng viên toàn cục còn lại tiếp tục được rà soát ở Phase 9.

## Kiểm chứng

**95 test Python + 9 subtest đạt; 779 lượt kiểm tra trình duyệt đạt; 51 ảnh nghiệm thu.** Kết quả tổng hợp cuối nằm trong [qa-summary.json](qa-summary.json). [Integrity audit](integrity-qa.json) ghi thay đổi so với snapshot trước Phase 8, gồm 50 template parse được, 9 template không còn style/handler inline, JS parse hợp lệ, không có token CSS thiếu và metadata DB thật không đổi.

- Python tích hợp dùng SQLite memory, CSRF thật và AI giả lập: render theo vai trò, bốn chế độ báo cáo, filter/no-store/null/archive, scope, CRUD lớp/người dùng, đổi giáo viên, ghi danh lại/idempotency, cấp bài đầu vào, sinh/đối chiếu báo cáo không đổi learning/mastery, thêm/thử/xóa khóa mã hóa đúng owner. Bộ validation tài khoản có 28 test riêng.
- Browser: [lớp học](courses-qa.json), [trạng thái lớp](courses-states-qa.json), [lần chốt lớp](courses-final-qa.json), [dashboard/người dùng](people-dashboard-qa.json), [AI tương tác](ai-browser-qa.json), [AI trực quan cuối](ai-visual-qa.json) và [các trang dùng CSS chung](shared-browser-qa.json). Không lỗi JS, asset thiếu hoặc script/font/CSS bên ngoài trong các lượt đạt. Các mutation trong QA riêng của agent được chặn để kiểm tra payload/CSRF; test tích hợp Python thực hiện mutation thật trong DB RAM.
- Có 24 test AI/report/route lịch sử vẫn lỗi. Đã tái hiện **đúng 24 lỗi trên source trước Phase 8** với DB memory và chặn socket, không sửa backend để phục hồi contract cũ. Chúng dùng scope C6, fallback, endpoint nhóm khóa hoặc fixture route đã cũ. Xem [audit baseline](baseline-ai-report-route-audit.md) và [từng lỗi/hash](baseline-ai-report-route-audit.json). Không tính những lỗi này là test đạt.

Lệnh kiểm tra cuối và kết quả đầy đủ nằm trong [python-regression.txt](python-regression.txt). Script browser nằm trong [qa](qa/) và `scripts/qa_ui_phase8_shared.cjs`; audit tĩnh dùng `scripts/qa_ui_phase8_integrity.py`. Snapshot `/tmp/linhedu-phase8-source-before` chỉ phục vụ đối chiếu của lượt làm này, không phải thư mục UI dự phòng trong bản chạy.

## Xem thử

Chạy `python3 scripts/preview_ui_phase8.py --port 8770`, mở [bản xem thử](http://127.0.0.1:8770/login). Tài khoản `qa_admin`, `qa_teacher`, `qa_student`, cùng mật khẩu `Academy123!`; các trạng thái bổ sung có tại `/qa/fixture`.

Preview dùng DB RAM, thư mục tạm và khóa mã hóa mới; không nạp `.env`, DB/upload hay khóa thật. Các lệnh AI/probe dùng mock và chặn HTTP outbound. Kết quả xác nhận giao diện, contract và trạng thái; không đánh giá chất lượng hoặc tình trạng dịch vụ AI thực tế. Không commit, deploy hoặc tạo PR.
