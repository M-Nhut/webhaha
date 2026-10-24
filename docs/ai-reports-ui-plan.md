# Kế hoạch giao diện Báo cáo AI · LinhEdu

## 1. Mục tiêu và phạm vi

Tách báo cáo sai lầm thành mục **Báo cáo AI** trên thanh điều hướng. Có tổng quan lớp, tổng quan học sinh và báo cáo phân tích chi tiết. Giữ nền kem, font Nunito, card bo góc 20px, viền 2px #1E293B, bóng cứng 4px 6px và điểm nhấn xanh #C2E5FA.

Kế hoạch đã được triển khai trong mã nguồn theo các phase ở `docs/ai-reports-phases.md`. Báo cáo mới mở từ mục Báo cáo AI; chưa gọi API AI thật trong quá trình triển khai.

### Hiện trạng đã đọc từ mã nguồn

- Báo cáo lớp đang nằm trong `templates/course_detail.html`, được dựng bởi `static/js/modules/class_learning_report.js`.
- `routes/academic.py` đã có API xem, tạo/cập nhật và ghi nhận đối chiếu báo cáo lớp.
- `services/class_lesson4_report.py` giữ bản phân tích, kiểm tra dữ liệu mới và liên kết bằng chứng. Phạm vi hiện tại giới hạn ở Bài 25 + 26.
- Báo cáo cá nhân nằm trong `templates/teacher_practice_detail.html` và `templates/components/diagnostic_report.html`; đã có tổng quan, lỗi, nguyên nhân giả thuyết, nguy cơ và can thiệp.
- Schema AI báo cáo lớp hiện chủ yếu nhận nguy cơ và khuyến nghị. Phần diagnosis của lớp hiện do hệ thống dựng, cần bổ sung trường tóm tắt AI và nguyên nhân có căn cứ.
- Dự án đã dùng Chart.js cho biểu đồ tiến bộ; có thể tiếp tục dùng thư viện này.

## 2. Điều hướng

```text
Báo cáo AI
  ├─ Cả lớp → Chọn lớp
  │   ├─ Tổng quan: số liệu có sẵn, biểu đồ cột + tròn
  │   ├─ Danh sách học sinh → Tổng quan cá nhân
  │   └─ Chi tiết → Gọi lại AI → Hiển thị phân tích mới
  └─ Cá nhân → Chọn lớp và học sinh
      ├─ Tổng quan: số liệu có sẵn, biểu đồ cột + tròn
      └─ Chi tiết → Gọi lại AI → Hiển thị phân tích của học sinh
```

- Menu bên trái có một mục **Báo cáo AI**. Bên trong trang có hai tab nhỏ **Cả lớp** và **Cá nhân** cho giáo viên và quản trị viên theo quyền hiện có.
- Trang lớp học và trang theo dõi học sinh có nút dẫn đến trang báo cáo tương ứng, thay cho khối phân tích dài đang nhúng trong trang.
- Giữ lớp, học sinh và bộ lọc khi chuyển giữa tổng quan và chi tiết hoặc quay lại.
- Giáo viên chỉ xem lớp phụ trách và tạo phân tích bằng khóa được cấp cho lớp. Quản trị viên xem theo quyền hiện có; không tự mở thêm quyền gọi khóa của giáo viên.

## 3. Tổng quan lớp

Thứ tự hiển thị:

1. Tiêu đề lớp, phạm vi dữ liệu, thời điểm cập nhật và trạng thái báo cáo.
2. Chọn lớp; bộ lọc dạng kiến thức, loại câu và nguồn bài làm. Khoảng thời gian chỉ bổ sung khi backend áp dụng đồng nhất cho thống kê và AI.
3. Bốn card: học sinh có bài làm/tổng sĩ số, lượt trả lời đúng, lượt trả lời sai, tỷ lệ đúng với mẫu số rõ ràng. Hiện thêm số chưa đủ ý khi có.
4. Hai card biểu đồ: cột theo dạng và tròn tổng kết quả.
5. Nút **Chi tiết**: giáo viên bấm để gọi lại API AI và xem tóm tắt, nguyên nhân, nguy cơ, khuyến nghị. Tổng quan chỉ hiển thị thông tin có sẵn.
6. Bảng học sinh: tên, số lượt trả lời, đúng/sai/chưa đủ ý, dạng cần xem lại, trạng thái phân tích và **Xem cá nhân**. Dạng cần xem lại được chọn từ số liệu thực, không gắn nhãn năng lực tự động.

Mặc định “dạng” là dạng kiến thức trong danh mục, ví dụ không gian mẫu, tung đồng xu, gieo xúc xắc. Loại câu Trắc nghiệm/Đúng–Sai/Trả lời ngắn là một bộ lọc riêng.

## 4. Tổng quan cá nhân

- Breadcrumb: Báo cáo AI → Lớp → Học sinh.
- Tên học sinh, lớp, phạm vi, số bài đã chấm và thời điểm dữ liệu mới nhất.
- Các card đúng, sai, chưa đủ ý và tỷ lệ đúng dùng cùng quy tắc với tổng quan lớp.
- Biểu đồ cột đúng/sai theo dạng và biểu đồ tròn kết quả của riêng học sinh.
- Các dạng cần củng cố và dấu hiệu tiến bộ từ dữ liệu quan sát; tóm tắt AI nằm trong Chi tiết.
- Nút **Xem báo cáo chi tiết**; liên kết tới bài làm/lịch sử liên quan.
- Danh sách bài làm làm căn cứ, không lấy dữ liệu học sinh khác khi đổi bộ chọn.

## 5. Biểu đồ

| Biểu đồ | Nội dung | Tương tác |
| --- | --- | --- |
| Cột nhóm | Mỗi dạng có cột Đúng và Sai; có thêm Chưa đủ ý nếu phát sinh | Hover hiển thị số lượng/mẫu số; chọn dạng để lọc bảng và bằng chứng |
| Tròn dạng doughnut | Tỷ trọng Đúng/Sai/Chưa đủ ý trong phạm vi đang xem | Nhãn số và %, chú giải; chọn trạng thái để lọc bằng chứng |

- Đúng dùng xanh lá, sai dùng hồng/đỏ, chưa đủ ý dùng vàng; đều có tên trạng thái và giá trị, không chỉ phân biệt bằng màu.
- Card biểu đồ có viền và bóng cứng; bản thân cột/lát có đường viền rõ. Tránh hiệu ứng 3D làm sai cách đọc số liệu.
- Biểu đồ cột đặt bên trái khoảng 2/3 chiều rộng; biểu đồ tròn bên phải. Điện thoại xếp dọc.
- Có bảng số liệu xem được bằng bàn phím và nút lọc tương đương thao tác chọn biểu đồ.
- Dạng chưa có dữ liệu ghi “Chưa có dữ liệu”; không biến thành 0% đúng. Nhãn dài được viết gọn và có tên đầy đủ trong bảng.

### Quy tắc đếm

- Thống kê từ các câu trả lời đã nộp và đã chấm thuộc đúng lớp/phạm vi, không từ danh sách lỗi rút gọn gửi AI.
- Mặc định đếm **lượt trả lời câu hỏi**; cùng câu được làm nhiều lần có nhiều lượt và phải ghi rõ trên giao diện.
- Đúng/Sai: chỉ đúng cả câu khi đúng đủ ý. Câu có kết quả một phần được tách riêng; không cộng các ý nhỏ lần nữa vào tổng số câu.
- Khi mở chi tiết Đúng/Sai, hiển thị từng ý đúng/sai/bỏ trống. Nếu bổ sung chế độ thống kê theo ý, phải đổi nhãn và mẫu số rõ ràng.
- Bỏ trống/chưa chấm được mô tả trong độ phủ dữ liệu, không nhập ngầm vào cột Sai. Tỷ lệ đúng dùng tổng Đúng + Sai + Chưa đủ ý có kết quả hợp lệ.
- Tổng card, biểu đồ, bảng và dữ liệu căn cứ phải khớp trong cùng bộ lọc.

## 6. Báo cáo chi tiết từ API

| Phần | Nội dung hiển thị |
| --- | --- |
| Tóm tắt AI | 3–5 câu/bullet: điểm làm được, lỗi nổi bật, ưu tiên hỗ trợ; lấy từ kết quả API đã chuẩn hóa |
| Lỗi quan sát | Dạng, câu/ý sai, đáp án học sinh, đáp án chuẩn, số lượt/số học sinh liên quan |
| Giả thuyết nguyên nhân | Nguyên nhân có thể có, bằng chứng liên quan và câu hỏi để kiểm chứng |
| Nguy cơ tiếp theo | Nguy cơ có điều kiện, khi nào có thể xuất hiện và cách xác minh |
| Khuyến nghị hướng dạy | Mục tiêu cần củng cố, cách giáo viên hướng dẫn, câu hỏi gợi mở, bài luyện gợi ý và tiêu chí kiểm tra tiến bộ |
| Bằng chứng | Nội dung câu hỏi, bài làm gốc, công thức/hình ảnh, thời điểm và nguồn bài |

- Phần tóm tắt mở sẵn; các phần dài dùng card và mục thu gọn, có liên kết tới bằng chứng.
- Lỗi thực tế và nhận định AI có nhãn riêng. Nguyên nhân/nguy cơ chưa xác nhận dùng nhãn “Giả thuyết cần kiểm chứng”.
- Báo cáo lớp cho biết học sinh liên quan; báo cáo cá nhân chỉ chứa căn cứ của người đó.
- Hiển thị trạng thái tạo, thời điểm cập nhật và ghi nhận đối chiếu của giáo viên. Thông tin kỹ thuật như model/version đặt trong “Thông tin báo cáo”.
- Khi API chưa trả phần nào, ghi đúng trạng thái thiếu dữ liệu; không tự điền đoạn nhận định vào phần AI.

## 7. Backend/API cần bổ sung

1. Tạo trang tổng quan riêng và route cá nhân theo lớp, tái sử dụng kiểm tra quyền ở API hiện có.
2. Tách hàm thống kê dùng chung để trả KPI, `by_skill`, phân bố kết quả, độ phủ, danh sách học sinh và phạm vi. Tính trên dữ liệu đầy đủ trước khi giới hạn bằng chứng gửi AI.
3. Chuẩn hóa đầu ra hiển thị: `summary`, `observed_errors`, `cause_hypotheses`, `future_risks`, `recommendations`, `evidence`, `metadata`. Adapter đọc cả schema lớp và cá nhân hiện có.
4. Mở rộng schema/prompt/validator lớp để nhận tóm tắt và giả thuyết nguyên nhân cùng evidence refs; không chỉ thêm tiêu đề trong UI.
5. API chỉ lưu/hiển thị kết quả đã kiểm tra schema và quyền liên kết bằng chứng. Khi thay đổi schema, tăng phiên bản; báo cáo cũ vẫn mở được nhưng phần mới có thể chưa có.
6. Xem tổng quan/chi tiết không tự gọi AI lại. Nút cập nhật dùng quy tắc cache và kiểm tra dữ liệu mới hiện có.
7. Nếu bộ lọc khác phạm vi bản phân tích, ghi phạm vi AI rõ ràng hoặc yêu cầu cập nhật báo cáo đúng phạm vi; không gắn báo cáo toàn lớp vào một bộ lọc cá nhân/dạng khác.

Phạm vi triển khai đầu tiên giữ dữ liệu Bài 25 + 26 hiện có, thể hiện rõ trên màn hình. Muốn mở rộng tới mọi bài/chương cần mở rộng bộ chọn dữ liệu, service và cache identity; không chỉ thêm bộ lọc giao diện.

## 8. Trạng thái giao diện

- Đang tải: skeleton card và biểu đồ.
- Chưa có bài đã chấm: thông báo và liên kết tới bài làm/đề.
- Có số liệu nhưng chưa có AI: vẫn xem đầy đủ thống kê; nút tạo phân tích nếu được phép.
- Đang phân tích: trạng thái xử lý, hạn chế bấm lặp.
- Báo cáo cũ: nhãn có dữ liệu mới, nút cập nhật; bản cũ ghi đúng phạm vi/thời điểm.
- API lỗi/chưa có khóa: giữ thống kê đã tải và thông báo phù hợp; không trình bày dữ liệu dự phòng như nhận định AI.

## 9. Trình tự triển khai

1. **Dữ liệu:** thống nhất phạm vi, đơn vị đếm, API thống kê và adapter schema.
2. **Tổng quan:** thêm menu, trang lớp/cá nhân, bộ chọn và biểu đồ.
3. **Chi tiết:** dựng các phần API, liên kết bằng chứng, tóm tắt và nguyên nhân mới.
4. **Chuyển điều hướng:** thay khối báo cáo nhúng bằng liên kết, giữ đường vào từ lớp/học sinh.
5. **Nghiệm thu khi triển khai:** đối chiếu số liệu, ba loại câu, TF một phần, dữ liệu rỗng, quyền lớp/cá nhân, lỗi API/cache, responsive và bàn phím.

## 10. Tiêu chí hoàn thành

- Menu Báo cáo AI dẫn được tới lớp và cá nhân; quay lại không mất bộ lọc.
- Hai loại biểu đồ xuất hiện ở cả hai trang tổng quan và khớp bảng dữ liệu.
- Xem chi tiết có đầy đủ phần theo dữ liệu API; phần thiếu hiển thị đúng trạng thái.
- Không trộn bài làm giữa các lớp/học sinh hoặc trộn phạm vi thống kê với bản AI.
- Nhãn, biểu đồ và công thức đọc rõ trên desktop/mobile, giữ phong cách LinhEdu.
