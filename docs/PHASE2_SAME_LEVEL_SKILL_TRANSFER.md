# Báo cáo Phase 2 — Chuyển dạng và giữ mức nhận thức

## Kết quả

Đã triển khai cơ chế phục hồi cho đề luyện tập cá nhân hóa 22 câu. Khi phân bổ dạng kiến thức ban đầu chưa ghép được, bộ chọn được phép thay số câu giữa các dạng; tổng từng mức nhận thức và cơ cấu 12 câu chọn đáp án, 4 câu Đúng/Sai, 6 câu trả lời ngắn không thay đổi. Loại bỏ nhánh phục hồi v2 chuyển quota sang mức nhận thức liền kề.

Phiên bản mới: `aptga-recovery-v3-same-level`. Không sửa đề đã lưu, thuật toán chấm, nhãn câu, hồ sơ bằng chứng hoặc luồng đề kiểm tra chung/đánh giá đầu vào. Phân bổ mức cá nhân hóa và bước thăm dò nâng mức vẫn được tính trước khi chọn câu; tính bất biến ở đây là so với quota yêu cầu của lượt sinh đề, không phải bắt mọi học sinh nhận phân bố 7–7–5–3.

## Luồng thực hiện

1. Giữ nguồn đã được kiểm tra quyền truy cập, phạm vi bài học, xác nhận giáo viên, đáp án/quy tắc chấm và các ràng buộc loại trừ hiện có.
2. Kiểm tra khả năng đáp ứng toàn nguồn: 22 nội dung khác nhau, số câu từng hình thức, **đúng số câu yêu cầu của từng mức**, tổng sức chứa tối đa năm câu mỗi dạng.
3. Trong mỗi tầng tiếp xúc, thử bộ chọn strict với quota ban đầu. Nếu thành công, giữ nguyên cách chọn này.
4. Nếu thất bại, thử ghép với quota mức và hình thức cố định, quota dạng mềm. Do đó một dạng không có Vận dụng cao không ngăn lấy câu Vận dụng cao từ dạng khác.
5. Chỉ sau khi thử nguồn mới mới mở rộng theo các tầng ôn lại cũ, gần đây, rồi lượt gần nhất. Dạng có nguồn nhưng tất cả đang cooldown vẫn phải được phủ; không coi nó là dạng hoàn toàn thiếu nguồn.
6. Nếu có phương án, ghi quota hiệu lực, các vị trí phân bổ chuyển và câu thực tế đại diện. Nếu không có, trả thiếu nguồn, xung đột giao ràng buộc hoặc giới hạn tìm kiếm; không phát hành đề ngắn hơn, không hạ mức để bù.

## Ràng buộc và ưu tiên

- Giữ đúng tổng mức và hình thức, do đó giữ thang điểm 10 và cấu trúc đề hiện có; thời gian vẫn theo blueprint.
- Không trùng nội dung kể cả các bản sao khác ID/ngân hàng. Giữ các nhánh phân loại khác nhau của cùng fingerprint trong tìm kiếm nhưng chỉ chọn một bản trong đề.
- Mỗi dạng có câu hợp lệ trong nguồn đầy đủ cần ít nhất một câu; tối đa năm câu mỗi dạng. Nếu một dạng hoàn toàn không có nguồn hợp lệ, bỏ sàn độ phủ cho riêng dạng đó, chuyển phần phân bổ và công khai số dạng được phủ. Không ghi “đủ tám dạng” khi thực tế chỉ có bảy.
- Thử giữ quota dạng ban đầu trước. Khi phục hồi, ưu tiên chưa vượt quota mong muốn, rồi dạng nhận cần luyện ở đúng mức đó theo aptga.priority. Thứ tự câu dùng tầng tiếp xúc, số lượt đã gặp, điểm ưu tiên, ưu tiên giáo viên, ID và fingerprint.
- Tìm kiếm có giới hạn và trả phương án hợp lệ đầu tiên theo thứ tự xác định; không tuyên bố đây là phương án tối ưu toàn cục hoặc ít lần chuyển nhất.
- Giới hạn cũ hai vị trí chuyển được thay bằng số vị trí thực tế cần chuyển trong phương án tìm được. Vẫn giới hạn số trạng thái tìm kiếm; `max_variants` được giữ để tương thích lời gọi, nay quy định ngân sách `max(1, max_variants) × 40` trạng thái cho một lượt ghép mềm (mặc định 3200).

## Ví dụ và cách hiểu dữ liệu chuyển

Ví dụ: dạng 1 không có câu Vận dụng cao, trong khi dạng 3 có câu đã duyệt ở mức này. Bộ ghép lấy câu Vận dụng cao ở dạng 3, giữ đúng tổng câu Vận dụng cao của đề và tìm câu dạng 1 ở mức khác nếu cần/nguồn cho phép. Không đổi nhãn câu dạng 3 thành dạng 1.

**Source hiện tại không có quota cho từng ô dạng × mức × hình thức**. Nó có quota dạng, quota mức và quota hình thức riêng. Vì vậy:

- Nếu bộ chọn strict đã ghép được bằng cách lấy mức cao ở dạng khác và giữ quota dạng ở các mức còn lại, không phát sinh điều chỉnh quota hay một sự kiện chuyển giả tạo.
- `skill_transfers` mô tả **chênh lệch ròng quota dạng** và mức/hình thức của câu thực tế đại diện bên nhận. Không khẳng định từng có một câu nguồn hoặc một suất ô nguồn cố định trước khi ghép.
- `source_cell_empty`: ô dạng nguồn tại mức/hình thức của câu đại diện không có nội dung hợp lệ trong tầng đang xét.
- `initial_targets_unresolved`: ô đó có nguồn nhưng quota ban đầu chưa ghép được trong lượt tìm kiếm. Thông báo không kết luận ngân hàng chắc chắn bất khả thi chỉ vì bộ tìm kiếm đạt giới hạn.

## Lưu và trình bày kết quả

Audit aptga bổ sung:

- `effective_level_targets`: luôn bằng quota mức của lượt yêu cầu; `level_targets_preserved=true`.
- `effective_skill_targets`, `quota_changes`, `skill_transfers` với source_skill, target_skill, level, question_type, question_id, count, source_available, reason.
- `exposure_stage`, `coverage_policy=cover_available_skills`, `unavailable_skills`, `covered_skill_count`.

AdaptiveEngine thêm thông báo chuyển dạng và độ phủ vào explanation. Luồng tạo đề lưu audit vào adaptive_metadata. Trang làm bài, kết quả và bản nháp dùng chung selection_audit để hiển thị phần “Chuyển dạng và giữ mức nhận thức” cùng số dạng thiếu nguồn. Các đề cũ không có trường mới vẫn đọc được bằng giá trị mặc định.

## Tệp thay đổi

- services/practice_transfer_selector.py: bộ ghép quota dạng mềm, giữ quota mức/hình thức; diễn giải chuyển.
- services/practice_recovery.py: thứ tự phục hồi mới, kiểm tra thiếu quota mức chính xác, thống kê độ phủ và trạng thái.
- adaptive_engine.py: truyền hồ sơ cho bộ phục hồi, thông báo chuyển và thiếu dạng.
- templates/components/selection_audit.html: hiển thị căn cứ chuyển và độ phủ thực tế.
- tests/test_practice_same_level_transfer.py: kiểm thử thuần cho cơ chế mới.
- tests/test_personalization_v2.py: cập nhật kỳ vọng phiên bản phục hồi và kiểm thử lưu/hiển thị đề thật.

## Kiểm chứng

Đã chạy:

`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_practice_same_level_transfer.py tests/test_practice_source_inventory.py tests/test_personalization_v2.py tests/test_aptga.py -q -p no:cacheprovider --disable-warnings`

Kết quả: **40 passed**. Dữ liệu giả lập, SQLite trong bộ nhớ; không gọi API AI và không thay dữ liệu học sinh thật.

Các trường hợp đã kiểm chứng gồm: nguồn đủ giữ lựa chọn strict; chuyển dạng giữ tổng mức/hình thức; thiếu toàn bộ dạng và chuyển trên hai vị trí; câu mới được ưu tiên trước câu ôn lại; cooldown không làm mất độ phủ dạng; thiếu Vận dụng cao so với quota yêu cầu dù còn trên sàn cũ; thiếu toàn bộ mức; thiếu hình thức; trùng nội dung trong ghép mềm; ưu tiên dạng nhận theo hồ sơ; vượt ngân sách tìm kiếm; giao mức/hình thức không tương thích; trần năm câu mỗi dạng; đầu vào đảo thứ tự và không sửa nhãn/quota đầu vào.

Kiểm thử tích hợp đã tạo/lưu đề có chuyển, xác nhận nhãn câu đóng băng đúng ngân hàng, mở trang làm bài trả 200 và hiển thị lý do cùng độ phủ 7/8. Trường hợp toàn nguồn thiếu Vận dụng cao trả danh sách câu rỗng và thiếu hụt mức chính xác.

Đã xem phần báo cáo bằng trình duyệt tại 1280px và 390px, không tràn ngang. Cảnh báo datetime.utcnow xuất phát từ mã hiện có, không làm thất bại kiểm thử.

## Bàn giao

Phase 2 hoàn thành ở phạm vi triển khai và kiểm thử liên quan. Phase 3 còn phần kiểm thử mở rộng theo ngân hàng thực tế từng lớp và cập nhật tài liệu sách/báo cáo Word đã tạo trước đây theo phiên bản mới. Không tuyên bố đã đánh giá phân bố của ngân hàng thật hoặc hiệu quả học tập của học sinh.
