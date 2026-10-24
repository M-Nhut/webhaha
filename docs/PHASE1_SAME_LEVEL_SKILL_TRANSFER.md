# Phase 1 — Thống kê nguồn và quy tắc chuyển dạng cùng mức độ

## Mục tiêu và phạm vi

Chuẩn bị chuyển câu luyện tập sang dạng kiến thức khác khi dạng được ưu tiên không có câu ở mức cần chọn. Phase 1 chỉ bổ sung dữ liệu đối chiếu; không áp dụng chuyển dạng, sửa quota hoặc đổi cách chọn đề. Không sửa luồng đề kiểm tra chung và đánh giá đầu vào.

“Dạng” trong yêu cầu là tám dạng kiến thức 9C8-i-1 đến 9C8-i-8. “Hình thức” là single, true_false, short_answer. Mức nhận thức gồm nhan_biet, thong_hieu, van_dung, van_dung_cao.

## Luồng đã rà soát

1. Các route trong routes/practice.py và routes/practice_runtime.py lấy nguồn được phép, kiểm tra hồ sơ và gọi AdaptiveEngine.select_questions.
2. adaptive_engine.py lọc ngân hàng, nguồn lớp, quyền riêng tư, ràng buộc giáo viên và câu bị loại trừ. Với đề cố định, practice_blueprint.readiness_error kiểm tra nhãn đã xác nhận, phạm vi tám dạng, đáp án và quy tắc chấm hợp lệ.
3. aptga.allocate và practice_selector.progression xác định quota mức; skill_targets xác định quota dạng. Đây là các tổng biên riêng, không phải phân bổ cho mỗi ô dạng × mức × hình thức.
4. ranked chứa câu đã duyệt cùng fingerprint, điểm ưu tiên, mã dạng và tầng tiếp xúc. Đây là nguồn đầu vào thống kê; không đọc lại toàn bộ ngân hàng hoặc mở rộng quyền truy cập.
5. practice_recovery.select_resilient hiện thử bốn tầng tiếp xúc với quota ban đầu, sau đó tìm vùng lân cận quota giới hạn tối đa hai lần chuyển vị trí. Nhánh này có thể đổi quota dạng và cả quota mức. Vì vậy cơ chế hiện tại chưa bảo đảm giữ mức như yêu cầu mới.
6. select_fixed kiểm tra ba tổng biên và tìm phương án ghép đồng thời, tránh trùng fingerprint. Đủ số lượng riêng lẻ không bảo đảm đủ giao nhau hoặc ghép được toàn bộ đề.

## Kết quả bổ sung trong Phase 1

Module services/practice_source_inventory.py cung cấp hai hàm thuần, không truy cập DB hay API AI:

- build_source_inventory: 96 ô dạng × mức × hình thức, bao gồm ô có số lượng bằng 0. Đếm nội dung khác nhau và số lượng tích lũy ở bốn tầng tiếp xúc; chỉ rõ ô không có nguồn ở mọi tầng, ô chỉ có nguồn ôn lại và thiếu hụt tổng biên.
- same_level_alternatives: xem trước các dạng khác có câu cùng mức **và cùng hình thức**, loại nội dung đã dùng và bản sao trùng; trả mã dạng, số lượng và ID đại diện theo thứ tự ưu tiên. Không lấy câu mức thấp hơn và không thay đổi nhãn câu.

AdaptiveEngine thêm source_inventory vào audit aptga của đề luyện tập cố định. Audit này được lấy từ pool đã lọc trước bộ phục hồi hiện tại, mode=observe_only. Metadata của đề sinh thành công được lưu qua luồng sẵn có; nếu sinh thất bại, dữ liệu nằm trong kết quả lựa chọn trả về, chưa có giao diện xem riêng trong phase này.

Không gọi same_level_alternatives từ bộ chọn trong Phase 1. Chưa có câu nào được chuyển tự động do tính năng mới; Phase 2 sẽ sử dụng dữ liệu/hàm này để sửa cơ chế ghép.

## Quy tắc thống kê

- Đơn vị là một câu của đề, không phải một ý Đúng/Sai. Mã dạng và mức lấy từ câu mẹ như select_fixed hiện tại; nhãn từng ý vẫn dùng cho chấm điểm và hồ sơ bằng chứng.
- fingerprint thiếu hoặc rỗng dùng khóa (id, question.id), tương tự select_fixed. Nội dung giống nhau ở nhiều ID chỉ được tính một lần trong một ô và tổng nguồn.
- Một fingerprint có thể xuất hiện ở nhiều ô do phân loại bản sao khác nhau; số ô và số nguồn thay thế không được cộng để suy ra số câu toàn đề. Bộ chọn vẫn phải loại trùng toàn đề.
- fresh gồm tier 0; spaced_review gồm tier 0–1; recent_review gồm tier 0–2; immediate_review gồm tier 0–3. Nguồn ôn lại không bị nhầm thành nguồn mới.
- Ô trống là thiếu nguồn cục bộ, không phải một suất câu bắt buộc đang thiếu: chưa tồn tại quota cho từng ô. marginal_shortages chỉ so sánh tổng dạng, tổng mức và tổng hình thức với quota đã có.
- full_paper_feasibility_checked=False: đây là kiểm tra nguồn, không khẳng định ghép thành công hoặc ngân hàng bất khả thi. Kết quả search_limit của bộ chọn vẫn là chưa kết luận.

## Thứ tự nguồn thay thế đã chốt cho Phase 2

1. Câu phải nằm trong nguồn được phép và qua kiểm tra chất lượng hiện tại; giữ cùng mức, cùng hình thức với vị trí cần bù.
2. Xét trong tầng tiếp xúc được phép của lượt tìm kiếm; mặc định xem trước chỉ dùng tier 0. Thử chuyển dạng bằng nguồn mới trước khi mở rộng câu vừa gặp là thay đổi thứ tự cần thực hiện ở Phase 2, chưa áp dụng trong Phase 1.
3. Ưu tiên dạng nhận cần luyện hơn tại đúng mức đó, dùng aptga.priority của ô hồ sơ dạng nhận × mức. Không suy diễn kỹ năng nhận đã thành thạo khi thiếu dữ liệu.
4. Trong nhóm có cùng ưu tiên, dùng thứ tự hiện có: tầng tiếp xúc, số lượt gặp, điểm câu, ưu tiên giáo viên, ID câu. Kết quả ổn định khi đổi thứ tự đầu vào.
5. Lựa chọn chỉ được chấp nhận khi ghép đủ đề và giữ tổng mức, 12–4–6, thang điểm, không trùng nội dung. Độ phủ dạng cần được kiểm tra riêng; không coi các dạng tương đương về kiến thức.
6. Nếu toàn nguồn không có câu cùng mức phù hợp, không tự hạ mức. Phân biệt thiếu nguồn thực sự, xung đột ràng buộc và giới hạn tìm kiếm. Nếu một dạng hoàn toàn thiếu nguồn, cách xử lý độ phủ sẽ được xác định trong Phase 2; Phase 1 giữ nguyên điều kiện hiện tại.

## Ví dụ

Dạng 1 không có câu single — Vận dụng cao; dạng 2 có hai bản sao cùng fingerprint, dạng 3 có một câu mới ở đúng mức và hình thức. Inventory ghi ô dạng 1 bằng 0, dạng 2 có một nội dung khác nhau, dạng 3 có một nội dung. Hàm xem trước đưa dạng 2 và dạng 3 vào nguồn thay thế; thứ tự phụ thuộc hồ sơ ở mức Vận dụng cao và xếp hạng câu. Nếu câu dạng 3 là Đúng/Sai, không dùng nó để bù trực tiếp vị trí single. Nếu chỉ có Vận dụng, danh sách nguồn cùng mức là rỗng.

## Kiểm chứng và bàn giao

Kiểm thử riêng: đủ 96 ô, trùng nội dung, tầng tiếp xúc, nguồn cùng mức/cùng hình thức, loại nội dung đã dùng, ưu tiên theo hồ sơ, đầu vào đảo thứ tự, không tự đổi mức, nhãn ngoài phạm vi, không sửa dữ liệu đầu vào, JSON audit.

Kiểm thử tích hợp: audit được thêm vào luồng thực tế; đối chiếu cùng dữ liệu khi bật/tắt hàm thống kê cho thấy danh sách câu, quota, trạng thái và cảnh báo của bộ chọn không thay đổi. Chạy bộ hồi quy cá nhân hóa v2 và APTGA trước khi bàn giao.

Bàn giao Phase 2: sử dụng inventory và hàm xem trước để thiết kế ghép/chuyển quota dạng với tổng mức bất biến; loại nhánh phục hồi đổi mức và ghi lý do chuyển thực tế. Phase 1 chưa thực hiện các thay đổi đó.

## Kết quả chạy kiểm thử

Lệnh đã chạy: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_practice_source_inventory.py tests/test_personalization_v2.py tests/test_aptga.py -q -p no:cacheprovider`.

Kết quả: **24 passed**. Dữ liệu kiểm thử là dữ liệu giả lập; kiểm thử tích hợp dùng SQLite trong bộ nhớ, không gọi AI. Các cảnh báo datetime.utcnow là cảnh báo deprecation từ mã hiện có, không gây lỗi kiểm thử.

Đây là xác nhận Phase 1; chưa xác nhận hành vi chuyển dạng tự động của Phase 2 và chưa thống kê ngân hàng thật của một lớp cụ thể.
