# Luồng cá nhân hóa Bài 4 — trạng thái triển khai

Tài liệu này ghi lại các liên kết đã triển khai cho sơ đồ: đánh giá đầu vào → hồ sơ → thuật toán quy tắc → đề 22 câu → chấm/lưu/cập nhật → tiếp tục hoặc kết thúc → báo cáo giáo viên.

## Luồng học sinh

- Mỗi môn hiển thị riêng trạng thái hồ sơ. “Đã khởi tạo” không có nghĩa là đủ dữ liệu cho 32 ô; ô chưa có bằng chứng vẫn là **chưa biết**.
- Một bài đánh giá đầu vào chung, đã đóng băng và có nhãn kỹ năng Bài 4, khởi tạo hồ sơ sau khi chấm hoàn tất. Bài bỏ trống hoàn toàn vẫn đánh dấu đã khởi tạo và giữ 32 ô ở trạng thái chưa biết, nên không tạo vòng lặp bắt làm lại đầu vào.
- Bằng chứng Bài 4 hợp lệ từ dữ liệu cũ được chấp nhận nếu thuộc bài nộp đã chấm hoàn tất. Dòng đang chờ chấm, khác bài hoặc không rõ nguồn không vượt qua bước khởi tạo.
- Nếu chưa có bài đầu vào được giao, hệ thống chặn tạo đề cá nhân hóa và hướng dẫn chờ giáo viên. Giáo viên nên tạo bài đầu vào từ ngân hàng Bài 4 đã phân loại; câu tạo tay không có nhãn chương trình không mở khóa cá nhân hóa Bài 4.
- Đề luyện chỉ lấy câu có phân loại `teacher_confirmed`, đủ nhãn kỹ năng/mức/hình thức và quy tắc chấm. Thiếu ngân hàng phù hợp thì không tạo đề ngắn hoặc phá cấu trúc 12–4–6.
- Kết quả, bằng chứng, mastery, hồ sơ lỗi, snapshot và trạng thái phiên được ghi trong cùng giao dịch. Nếu cập nhật hồ sơ thất bại thì toàn bộ lần ghi được hoàn tác để không tồn tại kết quả đã lưu nhưng hồ sơ cũ.
- Sau khi lưu hoàn tất, phiên chuyển sang `awaiting_decision`. “Tiếp tục” dùng hồ sơ vừa cập nhật; “Kết thúc” lưu `ended`. Hai lựa chọn dùng cập nhật có điều kiện nên thao tác cũ hoặc nhấp lặp không tạo hai đề và không ghi đè quyết định mới.

## Nhánh báo cáo giáo viên

- AI chỉ được gọi qua luồng báo cáo giáo viên và dùng bản sao hồ sơ lỗi đúng phạm vi `9C6-4`.
- Payload ngoài không chứa mastery, quota, trạng thái bộ chọn hoặc đáp án đúng đầy đủ. Với Đúng/Sai trả lời một phần, chỉ ý đã trả lời sai được đưa vào bản sao lỗi; ý bỏ trống và ý đúng không bị biến thành lỗi.
- Đầu ra phải là JSON có dẫn chiếu `evidence_ref`; rủi ro tương lai luôn là giả thuyết `not_validated`.
- Thuật toán chọn đề vẫn là thuật toán quy tắc với `ai_influence=0`. Báo cáo AI không cập nhật mastery, quota hay câu được chọn.
- Báo cáo lớp có trạng thái xác nhận riêng của giáo viên. Xác nhận/chỉnh trạng thái báo cáo không thay đổi dữ liệu học tập gốc.

## Thay đổi dữ liệu và vận hành

- Bổ sung bảng `practice_session` và các trường review cho `class_ai_analysis_run` trong model/startup migration.
- Migration là cộng thêm và có tính lặp lại. Trong đợt triển khai này **chưa chạy migration, seed hoặc sửa dữ liệu trên cơ sở dữ liệu thật**.
- Bài đầu vào đã có assignment không cho sửa hoặc xóa bộ câu hỏi, nhằm giữ `common_item_hash` so sánh được trong cùng cohort.

## Giới hạn đã chốt

- Không tự sinh bài đầu vào khi giáo viên chưa chuẩn bị ngân hàng phù hợp.
- Không gọi dịch vụ AI thật trong kiểm thử.
- Các bản ghi legacy không dùng blueprint `practice-22-v1` được giữ trong dữ
  liệu để đọc/đối soát; không còn route traditional để mở lại chúng.
