# Thang điểm đề kiểm tra

## Đã triển khai ngày 29/09/2026

- Đề kiểm tra riêng (nhập LaTeX hoặc lấy từ ngân hàng) luôn được phân bổ tổng 10 điểm khi lưu.
- Giáo viên xác định điểm cả phần: trắc nghiệm, đúng/sai, trả lời ngắn. Không áp đặt một tỷ lệ chung cho mọi lớp và môn.
- Chọn ngẫu nhiên theo số câu từng phần; kiểm tra nguồn câu đủ điều kiện và quyền truy cập trước khi tạo bản nháp. Thiếu câu ở một phần phải điều chỉnh cấu trúc hoặc nguồn, không tự thay bằng hình thức khác.
- Trọng số chia điểm trong cùng phần, không cộng thêm điểm vào tổng 10. Mặc định các trọng số bằng nhau. Sử dụng số thập phân chính xác và phân phối phần dư theo đơn vị 0,0001 điểm để tổng không bị lệch do làm tròn.
- Câu đúng/sai trong đề kiểm tra riêng chấm tuyến tính: điểm câu × số ý đúng / số ý. Đây là quy tắc của ứng dụng, được thông báo trước khi giao, không tuyên bố là cách chấm bắt buộc của kỳ thi quốc gia. Quy tắc bài tự luyện hiện có được giữ riêng.
- Kết quả hiển thị trên thang 10, làm tròn một chữ số thập phân theo ROUND_HALF_UP. Bài cũ quy đổi từ tổng điểm gốc, không viết lại bằng chứng chấm hoặc kết quả đã lưu.
- Chỉ sửa nội dung và phân bổ điểm khi đề còn là bản nháp. Kết quả đề riêng vẫn tách khỏi cập nhật năng lực dùng sinh bài tự luyện.

Ví dụ cấu trúc do giáo viên lựa chọn: 12 câu trắc nghiệm / 3 điểm; 4 câu đúng/sai / 4 điểm; 6 câu trả lời ngắn / 3 điểm. Đây là ví dụ, không phải tỷ lệ bắt buộc.

## Kiểm chứng

32 kiểm thử thuộc test_assessment_scoring.py, test_standalone_assessment.py và test_personalization_v2.py đã qua. Bao gồm đề 1, 3, 11, 22, 100 câu; phân bổ theo phần; trọng số; số không hợp lệ; thiếu nguồn; không tạo nháp dở; lưu sai tổng bị từ chối; dữ liệu cũ giữ nguyên; và tách kết quả đề khỏi thuật toán tự luyện.

Giao diện đã được thử lưu 3–4–3 và tải lại trên máy chủ kiểm thử sử dụng dữ liệu trong bộ nhớ. Ảnh: reports/phan-bo-diem-10.png. Không sửa cơ sở dữ liệu thật trong quá trình kiểm thử.

## Xuất ma trận Excel — cập nhật theo mẫu 7991 ngày 30/09/2026

Vào Đề kiểm tra → Ma trận bản đã lưu / Excel → Tải ma trận Excel. Mẫu trước đã được thay bằng bố cục trong ảnh người dùng cung cấp và phụ lục Công văn 7991/BGDĐT-GDTrH ngày 17/12/2024.

- Cột: TT; Chủ đề/Chương; Nội dung/đơn vị kiến thức; Mức độ đánh giá (TNKQ gồm Nhiều lựa chọn, Đúng–Sai, Trả lời ngắn; Tự luận); Tổng theo ba mức; Tỉ lệ % điểm.
- Mỗi hình thức có ba mức Biết, Hiểu, Vận dụng. Quy ước xuất của ứng dụng: Nhận biết → Biết; Thông hiểu → Hiểu; Vận dụng cao gộp vào Vận dụng. Quy ước này không thay đổi nhãn gốc hoặc thuật toán tự luyện; bảng Đối chiếu câu giữ cả mức gốc và mức xuất.
- Các đơn vị kiến thức cùng chương được nhóm dưới ô chương gộp. Đơn vị trùng tên ở hai chương khác nhau không bị cộng chung. Danh mục liên kết cung cấp tên chương khi lưu; chương được lưu cùng bản đề để tránh thay đổi khi danh mục được đổi tên về sau. Bài cũ chưa có bản chụp tên chương tra cứu theo mã liên kết rõ ràng.
- Giáo viên có thể nhập Chủ đề/Chương trong phần phân loại của trình sửa đề nếu chưa liên kết danh mục. Nhãn chỉ dùng khi giáo viên xác nhận.
- Ba dòng cuối: Tổng số câu; Tổng số điểm; Tỉ lệ %. Điểm và tỷ lệ lấy từ đề thật, không sao chép các tỷ lệ minh họa 30–20–20–30 trong phụ lục. Tổng điểm các hình thức bằng 10.
- Câu thiếu mức vẫn nằm trong bảng đối chiếu, tính vào điểm hình thức và tỷ lệ điểm của nội dung; chưa tính vào ba cột mức. Thông báo nêu số câu và điểm chưa phân mức, không che thiếu dữ liệu hoặc tự gán Biết. Chưa đủ nhãn thì bản xuất chưa phải ma trận hoàn chỉnh.
- Đúng–Sai đếm theo câu, số ý ghi ở bảng đối chiếu. Hiện dùng nhãn mức của cả câu, chưa tách từng ý. Cột Tự luận được giữ theo mẫu; hệ thống tạo/chấm đề hiện vẫn hỗ trợ ba hình thức tự động, không có tự luận thì cột số câu để trống.
- File có công thức tổng hợp từ Đối chiếu câu, cố định tiêu đề, in ngang A3 và lặp tiêu đề. Các ký tự *, ?, ~ trong tên được thoát trong tiêu chí công thức; văn bản luôn được ghi dưới dạng chuỗi, không thực thi công thức người dùng nhập.

Mẫu ma trận không thay thế bản đặc tả yêu cầu cần đạt. Công văn đề cập hướng dẫn xây dựng cho THPT; sử dụng bố cục này trong đề tài THCS là lựa chọn của ứng dụng theo yêu cầu người dùng, không khẳng định các tỷ lệ ví dụ là quy định bắt buộc cho mọi lớp/môn.

Nguồn đối chiếu: https://cdn.thuvienphapluat.vn/uploads/Hoidapphapluat/2024/NTH/20122024/20241210-Cong-van-7991-huong-dan-KTDGDK.pdf (trang 1–2).

Kiểm chứng đợt này: 38 kiểm thử đạt (ma trận, điểm, đề riêng, cá nhân hóa); đã nhập lại Excel bằng Artifact Tool, tính lại và thay đổi thử điểm nguồn để kiểm tra công thức, quét không thấy lỗi công thức, xem ảnh cả hai trang. Chưa kiểm chứng trực tiếp bằng Microsoft Excel desktop. Báo cáo: reports/matrix7991-tests.xml. Bản mẫu cũ được giữ tại backups/assessment_matrix_before_7991.xlsx.
