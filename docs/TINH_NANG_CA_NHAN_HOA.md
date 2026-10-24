# Tính năng cá nhân hóa học tập

## Phạm vi đã triển khai

Mỗi câu trả lời được lưu thành một bản ghi lịch sử gồm học sinh, bài nộp, câu hỏi trong đề, câu hỏi ngân hàng, môn, chủ đề, độ khó, mức nhận thức, đúng/sai, điểm chuẩn hóa, điểm thực nhận, điểm tối đa, trọng số, thời gian làm và thời điểm thực hiện. Việc chấm lại cập nhật đúng bản ghi cũ, không tạo lịch sử trùng.

Hồ sơ năng lực được tính trên ba chiều:

- Theo chủ đề.
- Theo đủ bốn mức nhận thức: Nhận biết, Thông hiểu, Vận dụng và Vận dụng cao.
- Theo giao điểm chủ đề × mức nhận thức để tìm đúng vùng yếu.

Sau mỗi lần nộp hoặc chấm lại, hệ thống lưu một ảnh chụp hồ sơ. Màn hình tiến bộ dùng các ảnh chụp này để theo dõi thay đổi theo thời gian.

Khi nâng cấp cơ sở dữ liệu hiện có, hệ thống tự đọc các bài nộp cũ theo thứ tự thời gian, tạo lịch sử câu trả lời và ảnh chụp năng lực còn thiếu. Tiến trình này chạy lặp an toàn và không nhân đôi dữ liệu.

## Công thức và tham số

Mức thành thạo dùng đúng công thức:

`Mastery = Σ(weight × normalized_score) / Σ(weight)`

Trọng số của một lần trả lời hiện được tạo từ độ khó, mức nhận thức và độ tin cậy của nhãn phân loại. Các ngưỡng khởi tạo là 0,40; 0,60; 0,80. Chúng được gom tại `AdaptiveEngine.MASTERY_THRESHOLDS` để hiệu chỉnh sau thực nghiệm, không phải các chân lý cố định.

Điểm ứng viên dùng năm thành phần W/D/C/V/P với trọng số khởi tạo 40/25/20/10/5. Từng thành phần và tổng điểm của các câu đã chọn được lưu trong metadata của bài để kiểm tra và giải thích.

## Sinh bài thích ứng

Luồng sinh bài thực hiện theo thứ tự: đọc lịch sử → tính hồ sơ → tìm vùng yếu → xác định phân phối độ khó → chấm điểm câu hỏi → áp tỷ lệ ôn tập → tạo bài → lưu lý do.

- Cold start kéo dài đến khi có 20 câu trả lời. Bài đầu vào ưu tiên mức trung bình nhưng vẫn có đủ dải độ khó.
- Tỷ lệ ôn mặc định là 60% vùng yếu, 25% vùng trung bình và 15% vùng đã tốt. Bộ chia quota dùng phần dư lớn nhất để tỷ lệ hợp lý cả với bài ít câu.
- Bộ chọn loại câu bị khóa, tránh câu vừa xuất hiện, không lấy trùng trong một bài, và lấp phần thiếu khi ngân hàng không đủ cơ cấu mong muốn.
- Câu hỏi được lọc theo môn, quyền truy cập, chương, bài, chủ đề, mức nhận thức và danh sách loại trừ trước khi chấm điểm.

## Quyền kiểm soát của giáo viên

Tại ngân hàng, giáo viên có thể đặt độ khó thích ứng, mức ưu tiên từ 0 đến 100 hoặc loại một câu khỏi mọi bài thích ứng.

Tại hồ sơ luyện tập của học sinh, giáo viên có thể giới hạn lớp học, ngân hàng, chương, bài, chủ đề, mức nhận thức, số câu và tỷ lệ yếu/trung bình/duy trì. Hệ thống tạo bài ở trạng thái bản nháp để giáo viên xem, sửa và bật phát hành.

## Hiệu chỉnh và đánh giá

Khi có dữ liệu thật, nên đánh giá các cấu hình cạnh nhau theo các chỉ số: tỷ lệ hoàn thành, thay đổi mastery sau 2–4 tuần, độ phủ chủ đề, tỷ lệ lặp câu, thời gian làm trung vị và chênh lệch giữa dự đoán với kết quả thực tế. Thử thay từng nhóm tham số trong biên nhỏ trước, giữ các nhóm còn lại cố định, rồi so sánh độ nhạy. Cần ghi phiên bản cấu hình dùng trong mỗi đợt thử nghiệm cùng dữ liệu kết quả để có thể tái lập.

## Kiểm tra tự động

Bộ kiểm tra chuyên biệt xác nhận công thức trung bình có trọng số, đủ bốn mức nhận thức, cold start, lưu lịch sử không trùng khi chấm lại, quyền loại/ưu tiên câu và việc tạo bản nháp có lý do giải thích.

## Phân tích năng lực Chương 6 bằng AI

### Hồ sơ đầu vào

`chapter6_profile_service` lấy tối đa 5 bài và 50 câu trả lời gần nhất, sau đó chỉ giữ dữ liệu có phân loại Chương 6. Kết quả được nhóm theo bài, dạng bài và mức nhận thức. Mỗi nhóm có số lần làm, số câu đúng, tỷ lệ đúng, điểm chuẩn hóa, mastery có trọng số, thời gian trung vị và xu hướng gần đây.

Tên, mã học sinh, số điện thoại và nội dung câu trả lời không được gửi ra ngoài. Hệ thống gửi một mã ẩn danh sinh từ `AI_ANALYSIS_PSEUDONYM_SALT`, các chỉ số tổng hợp và danh mục dạng bài hợp lệ của Chương 6.

### Kết nối API

Thiết lập các biến sau trong môi trường triển khai:

```text
AI_ANALYSIS_API_URL=https://your-provider.example/v1/chat/completions
AI_ANALYSIS_API_KEY=...
AI_ANALYSIS_MODEL=...
AI_ANALYSIS_PROVIDER=...
AI_ANALYSIS_PSEUDONYM_SALT=...
```

Endpoint cần tương thích định dạng chat completions và hỗ trợ trả JSON object. Có thể điều chỉnh timeout, số lần thử lại và thời gian cache bằng `AI_ANALYSIS_TIMEOUT_SECONDS`, `AI_ANALYSIS_RETRIES` và `AI_ANALYSIS_CACHE_HOURS`.

AI phải trả đúng schema `chapter6-analysis-v1`: chẩn đoán chung, độ tin cậy, vùng mạnh, vùng yếu, mục tiêu tiếp theo, phân phối NB–TH–VD–VDC và giải thích cho học sinh. Hệ thống từ chối mọi bài/dạng ngoài danh mục, nhận định không có vùng dữ liệu quan sát hoặc phân phối không đủ 100%.

Mỗi lần gọi được lưu vào `AIAnalysisRun` cùng hash đầu vào, nhà cung cấp, model, phiên bản prompt, request, response, trạng thái và lỗi. Kết quả thành công được cache 24 giờ khi dữ liệu không đổi. Lỗi mạng, timeout, hết hạn mức hoặc JSON sai đều chuyển sang phân tích theo quy tắc hiện tại để giáo viên vẫn làm việc bình thường.

Ở giai đoạn này, kết quả AI phục vụ chẩn đoán và xem xét của giáo viên. Việc đưa mục tiêu AI vào bộ sinh đề tự động thuộc bước tích hợp tiếp theo, sau khi có dữ liệu đánh giá độ chính xác.
