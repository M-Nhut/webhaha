# Nhập học liệu LaTeX theo hai mục đích

## 1. Ngân hàng đã phân dạng

Giữ mẫu `cautrucde.tex`: khối ex, mã lớp/chương/mức độ/dạng/loại, choice hoặc choiceTF hoặc shortans, loigiai. Với lớp và chủ đề khác có thể dùng mẫu `ngan_hang_nhieu_chu_de.tex`, nhãn `% @grade:`, `% @category:`, `% @level:`. Tiêu đề section chỉ kiến thức cũng được nhận dạng; subsection mức độ dùng khi câu chưa có mức độ riêng. Mã câu tường minh có ưu tiên cao hơn mức độ của tiêu đề.

Câu được đọc, xem trước, kiểm tra trùng, giáo viên xác nhận phân loại rồi lưu ngân hàng. Không dùng AI để tự đoán nhãn khi không có căn cứ. Nếu một file có cả câu có nhãn và câu chưa có nhãn, file đi qua luồng ngân hàng để giáo viên rà lại các nhãn thiếu.

Nếu giáo viên đã chọn đúng ô dạng kiến thức trong ngân hàng rồi mới nhập file, nhãn đã chọn được dùng làm căn cứ phân loại; file vẫn đi vào ngân hàng kể cả khi nguồn chưa ghi mã. Dòng mẫu bị chú thích bằng `%` không được tính là câu hỏi.

## 2. Đề kiểm tra chưa phân dạng

File ex không có nhãn dạng kiến thức được chuyển sang Đề kiểm tra. Các tiêu đề như “Phần I. Trắc nghiệm” chỉ phân chia đề, không trở thành nhãn kiến thức. Mẫu tải trực tiếp trong trang nhập: `de_kiem_tra_ex.tex`.

Giáo viên chọn lớp, tên đề và thời gian; kiểm tra từng câu, chỉnh đáp án và trọng số điểm. Lưu bản nháp để xem lại công thức và các chỉnh sửa. Chỉ khi giáo viên xác nhận và bấm Giao đề, học sinh trong lớp mới thấy đề. Giữ nguyên thứ tự câu và phương án, không tự bỏ câu trùng hay đưa câu vào ngân hàng. Đề đã giao được khóa nội dung. Bản nháp có thể chỉnh lại từ danh sách đề.

Ba hình thức hỗ trợ: trắc nghiệm một đáp án, đúng/sai bốn ý, trả lời ngắn khớp văn bản. Không thay thế chấm tự luận hoặc đánh giá lời giải mở. Thiếu đáp án hoặc hình biên dịch lỗi thì giữ nháp, không được giao. Lời giải có thể thiếu trong bản đề học sinh; giáo viên có ô bổ sung, và chỉ được hiển thị trong kết quả sau khi nộp.

Điểm mỗi câu do giáo viên đặt. Đúng/sai tính theo tỷ lệ số ý đúng nhân trọng số câu; toàn bài là tổng điểm đạt / tổng điểm đề. Hệ thống hiển thị quy tắc trước khi giao; không mặc nhiên gọi đây là thang điểm của một kỳ thi chính thức. Mỗi học sinh nộp một lần; kiểm tra quyền lớp và kiểm tra lượt nộp ở máy chủ.

## 3. Giữ nguyên mô hình khóa luận

Đánh giá đầu vào chuẩn → hồ sơ năng lực → chọn câu từ ngân hàng đã duyệt → tự luyện thích ứng → cập nhật bằng chứng → AI đề xuất sai lầm → giáo viên đối chiếu vẫn là luồng nghiên cứu chính.

Đề riêng là công cụ phục vụ dạy học bổ sung, không khởi tạo hồ sơ đầu vào và không cập nhật thuật toán cá nhân hóa. Kết quả được đưa vào Theo dõi học tập ở mức bài làm và từng câu, kể cả khi không có mã câu. Câu có nhãn kiến thức được giáo viên xác nhận và thuộc phạm vi xác suất 9 được bổ sung vào bằng chứng báo cáo sai lầm; câu chưa phân loại hoặc thuộc chủ đề khác được giữ riêng trong kết quả kiểm tra. Không suy đoán nhãn từ điểm số hay nội dung bằng AI.

Việc tách nguồn được thực hiện cả ở cập nhật năng lực, ma trận kỹ năng và lịch sử câu đã gặp của bộ chọn đề. Bằng chứng đề kiểm tra là dữ liệu đọc từ bài đã chấm, không ghi thành LearningHistory của tự luyện. Mỗi bằng chứng giữ bài nộp, câu hỏi, câu trả lời, phiên bản chấm và nguồn đánh giá; AI không được diễn giải chênh lệch điểm giữa các đề khác nhau thành tiến bộ đã được chứng minh.

## Kiến trúc

- `latex_document.py`: nhận dạng từ bằng chứng nhãn; `latex_parser.py`: đọc cấu trúc và giữ nội dung.
- `standalone_assessment.py`: kiểm tra đề, lưu tài sản công thức và đóng băng câu/đáp án; không tạo BankQuestion.
- `assessments.py`: kiểm tra quyền lớp, duyệt nháp và danh sách đề.
- Runtime dùng chung chấm ba loại câu; endpoint đề riêng kiểm tra đúng mục đích `standalone`. Endpoint tự luyện vẫn từ chối đề riêng. Không sửa quy tắc đánh giá đầu vào hoặc thuật toán chọn đề thích ứng.

Không cần dịch vụ dựng LaTeX bên ngoài hoặc thay đổi lược đồ cơ sở dữ liệu trong lần nâng cấp này.

## Kiểm chứng ngày 28/09/2026

Nhóm kiểm thử liên quan: 63 kiểm thử và 20 kiểm thử con đã qua (ngân hàng phổ thông, nhập LaTeX, runtime đề riêng, báo cáo và cá nhân hóa). Đã thao tác trên trình duyệt với dữ liệu kiểm thử trong bộ nhớ: chọn lớp, lưu nháp, giao đề và kiểm tra danh sách đề đã giao. Kiểm thử máy chủ xác nhận học sinh không thấy bản nháp, nộp một lần, chấm đủ ba hình thức, không tạo câu ngân hàng và không gọi cập nhật năng lực. Các kiểm thử không sử dụng dữ liệu học sinh thật hoặc gọi AI.

Đây là kết quả của nhóm kiểm thử liên quan, không phải tuyên bố mọi bộ kiểm thử cũ trong repository đều tương thích. Hiệu quả sư phạm cần đánh giá thực nghiệm riêng theo đề cương khóa luận.

## Bổ sung: tạo đề từ ngân hàng và chỉnh sửa trực tiếp

Vào **Đề kiểm tra → Tạo đề từ ngân hàng**, chọn lớp và một hoặc nhiều ngân hàng được phép sử dụng. Có thể đánh dấu từng câu hoặc yêu cầu chọn ngẫu nhiên một số lượng câu. Đây là cách lấy mẫu đơn giản cho đề chung, không phải thuật toán sinh đề thích ứng và chưa phải bộ tạo ma trận đề theo hạn ngạch. Không tự giao đề: luôn qua bước xem trước, chỉnh sửa và xác nhận. Khi lưu/giao, máy chủ kiểm tra lại quyền sử dụng và tình trạng duyệt nguồn câu.

Nút **Nhập đề từ LaTeX** cho phép chọn mục đích đề kiểm tra dù file có mã câu; chế độ tự nhận diện vẫn giữ hai luồng theo cấu trúc gốc. Trong bản nháp, nội dung, công thức, phương án và lời giải được xem trước khi nhập. Nút Lưu chỉnh sửa có thông báo đang lưu/thành công/thất bại; tải lại trang chỉ sau khi thông báo thành công. Đề đã giao khóa nội dung để bảo toàn căn cứ chấm.

Phân loại báo cáo là tùy chọn. Câu từ ngân hàng kế thừa nhãn đã duyệt; câu từ file được giáo viên liên kết danh mục hoặc ghi tên dạng. Nhãn không nằm trong danh mục nghiên cứu không bị ép vào tám dạng xác suất. Các ý Đúng/Sai giữ nhãn riêng nếu nguồn đã có; không tự coi mọi ý là cùng một kỹ năng.

Đóng góp có thể trình bày trong khóa luận là cơ chế hợp nhất bằng chứng có nguồn gốc, xác nhận nhãn, phân biệt dữ liệu quan sát và giả thuyết AI, đồng thời bảo toàn đầu vào thuật toán luyện tập. Cần đánh giá thực nghiệm độ đúng của nhãn, mức phù hợp nhận định của giáo viên và khả năng hỗ trợ can thiệp; riêng việc thêm màn hình báo cáo chưa chứng minh tính mới hoặc hiệu quả sư phạm.

### Kiểm chứng bổ sung

56 kiểm thử và 9 kiểm thử con đã qua trong nhóm hiện hành; báo cáo máy ở `docs/reports/assessment-integration-tests.xml`. Bao gồm lưu nội dung/công thức/đáp án/lời giải, từ chối nguồn trái quyền, thiếu câu, đề có mã nhưng chọn luồng kiểm tra, bằng chứng có nhãn/chưa có nhãn, và bài luyện được chọn không đổi trước/sau nộp đề kiểm tra. Kiểm tra trình duyệt xác nhận xem trước công thức và lưu rồi tải lại không mất nội dung. Không gọi AI thật hay dùng cơ sở dữ liệu học sinh thực.

Khi mở rộng sang các bộ cũ `test_class_lesson4_report.py` và `test_practice22.py`, còn 21 ca không tương thích giả định chương 6/bài 4, fallback và quy tắc cũ. Không tuyên bố toàn bộ repository đã qua. Các bộ cũ chưa được chuyển đổi trong lần bổ sung này.
