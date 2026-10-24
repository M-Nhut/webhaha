# APTGA v1 — đặc tả trước triển khai

Phạm vi: Toán 9 Chương 6 Bài 4; ID kỹ năng giữ nguyên. Đây là bộ quy tắc
thử nghiệm, không phải thang đo chuẩn hay mô hình xác suất đã hiệu chỉnh.

## Hợp đồng

Đầu vào: lịch sử đã chấm, snapshot mã kỹ năng/mức nhận thức, câu ứng viên
được phép, tổng câu và giới hạn giáo viên. Đầu ra giữ API selection hiện có,
bổ sung audit version, quota mong muốn/thực tế, shortfall và lý do chọn câu.
Không sửa điểm chấm hay biến nguy cơ AI thành lỗi đã quan sát.

## Hồ sơ

Mỗi ô canonical_code × cognitive_level lấy normalized_score (hỗ trợ điểm
một phần), trọng số thời gian 0.8 theo mỗi phiên làm mới hơn trong cùng ô.
Một phiên có nhiều câu không làm tăng tốc suy giảm. Ước lượng chưa có dữ liệu
là null; không phải 0. Chỉ dùng bài finalized và answer_status=answered,
không lấy dữ liệu legacy_unknown làm bằng chứng chắc chắn.
Mức đủ dữ liệu = min(1, số phiên bản câu khác nhau/5) × min(1, số phiên/2).
Đạt đủ dữ liệu khi có ít nhất 5 câu khác nhau và 2 phiên. Đây không phải
confidence thống kê. Ngưỡng: >=.85 vững, >=.70 đạt, >=.50 cần củng cố, còn
lại yếu; khi thiếu dữ liệu luôn ưu tiên nhãn chưa đủ dữ liệu.

## Phân bổ

Cấu trúc nền 40/30/20/10; sàn 25/25/20/10; trần 40/35/40/25.
Dùng largest remainder cho nền; ceil cho sàn; floor cho trần. Nếu số câu
nhỏ khiến sàn/trần vô nghiệm, dùng nền nguyên và ghi rõ relaxation.
Chỉ chuyển tối đa floor(.2*N) câu từ mức đạt .70 và đủ dữ liệu, không vượt
sàn. D=max(0,.70-M)/.70; chỉ mức đủ dữ liệu được coi là thiếu hụt đã biết.
Chọn đích theo nhu cầu × số cơ hội phân bổ, tuân trần; nếu D=0 hoặc không
có nguồn thì giữ nền và cá nhân hoá trong ô. Giới hạn mức giáo viên là cứng;
khi loại mức, chuẩn hoá nền trên mức được phép và ghi ngoại lệ sàn toàn đề.

Không tự mặc định NB→TH→VD→VDC hay lambda=2/3. V1 chưa bật chuyển tiền đề
vì chưa có bảng quan hệ chuyên môn được duyệt. Audit phải ghi rõ điều này.

## Chọn câu

Trong từng mức ưu tiên 0.6*D + 0.25*R + 0.15*U, tất cả trong [0,1].
R là tỷ lệ phiên có kết quả dưới .70 trên tối đa 3 phiên gần nhất trong ô;
không khẳng định đó là một misconception. U=1-mức đủ dữ liệu. D được nhân
mức đủ dữ liệu để không coi ô chỉ một câu sai là vùng chắc chắn yếu.
Teacher priority là tie-break có giới hạn; ID tăng dần bảo đảm tái lập.
Probe khi thiếu dữ liệu, remedial khi đủ dữ liệu và M<.70, maintenance còn lại.
Tỷ lệ 60/25/15 là mục tiêu mềm dùng khi xếp câu cùng mức, không được phá
quota mức. Lưu mix thực tế; không hứa đạt mục tiêu khi ngân hàng không đủ.

Không chọn câu đã xuất hiện trong 3 phiên gần nhất hoặc chưa qua 5 ngày.
Một câu chỉ quay lại khi đạt cả hai điều kiện. Không lặp ID trong một đề.
Không lấp quota thiếu bằng mức khác; trả đề ngắn và cảnh báo số câu thiếu.
Đây là thay đổi có chủ đích so với fallback chọn tự do trước đây.
Không lấy tín hiệu AI chưa có xác nhận và mapping câu–sai lầm đáng tin vào
priority v1; ảnh hưởng AI mặc định bằng 0. Báo cáo AI vẫn hoạt động riêng.

## Kiểm thử bắt buộc

1. Đủ dữ liệu, M=.875/.833/.60/.10: chuyển theo thiếu hụt, tuân trần; không
   yêu cầu 5/5/7/3 vì ví dụ đó phụ thuộc tiền đề chưa được duyệt.
2. Tất cả đạt hoặc tất cả chưa đủ dữ liệu: không chia 0, giữ nền.
3. N=1/2/3/10/20/100: tổng quota=N; ngoại lệ rounding có thông báo.
4. Nhãn unknown khác weak; cùng câu lặp không nâng distinct evidence.
5. Kết quả mới tốt hơn làm mastery tăng; thứ tự input không ảnh hưởng.
6. Đề thiếu câu/mức bị cấm: shortfall rõ ràng, không vượt quyền/ràng buộc.
7. Cooldown, teacher exclusions, không lặp ID, deterministic tie-break.
8. Audit được lưu ở cả luồng học sinh và giáo viên; AI observed/risk không đổi.

Đánh giá nghiên cứu sau triển khai: so sánh cấu trúc cố định, mức-only,
skill×level; đo tiến bộ trên câu mới cùng kỹ năng. Lưu phiên bản tham số để
tái lập. Dự đoán AI cần kiểm chứng theo thời gian riêng, không dùng nhãn AI
làm ground truth. Không triển khai tự huấn luyện mô hình trong phiên bản này.
