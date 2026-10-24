# Phase 3 — Kiểm chứng và hoàn thiện tài liệu chuyển dạng cùng mức

> Bổ sung ngày 07/10/2026: kiểm thử phase 3 ở dưới tập trung vào luồng luyện tập. Lỗi tạo đề đầu vào thiếu dạng 6 đã được sửa và kiểm chứng riêng qua POST tạo đề, giao cả lớp và mở đề của học sinh; xem [báo cáo sửa luồng đầu vào](DIAGNOSTIC_SAME_LEVEL_TRANSFER_FIX.md). Cả hai luồng tạo đề hiện chọn ngẫu nhiên dạng thay thế khi phục hồi.

Ngày hoàn tất: 07/10/2026. Phiên bản phục hồi: `aptga-recovery-v3-same-level`.

## 1. Kết quả bàn giao

Hoàn tất kiểm thử hồi quy mở rộng, kiểm tra nguồn câu được phép của các lớp trên bản sao SQLite và cập nhật hai tài liệu Word hiện hành. Các điều kiện của Phase 2 được giữ: 22 nội dung khác nhau, cơ cấu 12 trắc nghiệm / 4 Đúng-Sai / 6 trả lời ngắn, tổng câu mỗi mức bằng quota yêu cầu, mỗi dạng có nguồn từ 1 đến 5 câu. Dạng hoàn toàn không có nguồn được công khai trong audit.

Khi dạng 1 thiếu Vận dụng cao, lấy câu Vận dụng cao từ dạng khác có nguồn hợp lệ. Không đổi nhãn câu, không hạ mức để bù. Source không có quota cố định cho từng ô dạng × mức × hình thức; audit chuyển thể hiện chênh lệch ròng quota dạng và câu thực tế đại diện bên nhận.

## 2. Kiểm thử hồi quy

Lệnh chạy:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/test_practice_same_level_transfer.py \
  tests/test_practice_source_inventory.py \
  tests/test_personalization_v2.py \
  tests/test_aptga.py \
  tests/test_unified_practice_phase3.py \
  tests/test_practice22.py \
  tests/test_source_resolver_phase4.py \
  tests/test_personalization_mvp.py \
  tests/test_learning_loop_phase4.py \
  -q -p no:cacheprovider --disable-warnings --tb=short
```

**Kết quả: 78 passed, 14,68 giây.** Log: `docs/reports/phase3-same-level-regression.txt`.

Các bài kiểm thử xác nhận:

- Nguồn đủ giữ lựa chọn ban đầu; khi cần chuyển dạng, giữ chính xác quota mức/hình thức và không sửa nhãn/quota đầu vào.
- Chuyển được hơn hai vị trí; phủ các dạng có nguồn, tối đa năm câu mỗi dạng; cooldown không làm một dạng bị coi là hoàn toàn không có nguồn.
- Ưu tiên chuyển trong tầng fresh trước khi mở câu ôn lại; thứ tự xác định và ưu tiên dạng nhận theo hồ sơ.
- Thiếu đúng quota Vận dụng cao, thiếu hình thức, giao mức/hình thức không tương thích hoặc nội dung trùng thì không phát hành đề sai cấu trúc; hết ngân sách được phân biệt với thiếu nguồn chắc chắn.
- Tạo/lưu bản nháp, nhãn và nội dung câu đóng băng; hiển thị audit và độ phủ; quyền lớp, ngân hàng riêng, manifest và đề cũ.
- Đánh giá đầu vào, chấm Đúng/Sai và số, cập nhật bằng chứng, luyện tiếp/kết thúc và chống tạo đề hai lần từ một quyết định cũ.
- Gói bằng chứng cá nhân giữ đối chiếu đáp án thực tế/chuẩn; không gửi mastery/quota để AI điều khiển chọn đề.

Dữ liệu thử cũ trong `test_practice22.py`, `test_personalization_mvp.py` được chuyển về Chương 8/bài i. Fixture đầu vào dùng đề 22 câu đủ 12/4/6, tám dạng, bản chụp/manifest và bài nộp đã chấm; cờ “completed” đơn lẻ không được dùng thay bằng chứng hoàn tất. Test API không cấu hình kỳ vọng trạng thái failed, đúng code hiện tại. Test điểm số dùng hợp đồng tolerance số hợp lệ. `test_unified_practice_phase3.py` xác nhận liên kết route thay vì câu chữ giao diện cũ. Các assertion về điểm, hồ sơ, quyền và quyết định phiên vẫn được kiểm tra.

Đây là 9 file test liên quan, không phải toàn bộ bộ kiểm thử dự án. Cảnh báo chủ yếu về API datetime/ORM cũ, không làm thất bại kiểm thử. Các bài dùng SQLite trong bộ nhớ hoặc mô phỏng dịch vụ; không gọi API AI thật.

## 3. Kiểm tra ngân hàng của lớp trên dữ liệu cục bộ

Công cụ: `scripts/evaluate_same_level_sources.py`.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/evaluate_same_level_sources.py \
  --database tutoring_center.db \
  --output /private/tmp/phase3-sources.json
```

Công cụ mở DB nguồn bằng `mode=ro`, sao chép với SQLite backup sang thư mục tạm, không chạy seed/migration/backfill; không đọc `.env`, hồ sơ học sinh hoặc gọi AI. Dữ liệu được lọc bằng `resolve_class_banks`, `resolve_class_questions`, readiness/nhãn đã duyệt và phạm vi Chương 8/bài i. Checksum DB nguồn trước/sau không đổi. JSON chỉ lưu mã lớp thay thế và số liệu/căn cứ nguồn, không tên người học hay nội dung câu.

Kết quả được lưu tại `docs/reports/phase3-same-level-real-sources.json`. Quota thử là hồ sơ trung tính: NB/TH/VD/VDC = 7/7/5/3; quota dạng gốc = 3/3/3/3/3/3/2/2; chưa áp dụng lịch sử tiếp xúc của học sinh thật.

| Nguồn/lớp | Câu được phép và sẵn sàng | Kết quả |
|---|---:|---|
| class-01, nguồn thực | 129 | ready, 22 câu, 12/4/6 và 7/7/5/3, không trùng; phủ 7/8 dạng có nguồn; chuyển 3 vị trí quota dạng |
| class-01, mô phỏng bỏ toàn bộ dạng 1 | 115 | ready, 22 câu, giữ mức/hình thức; phủ 6/8 dạng; chuyển 6 vị trí quota dạng |
| class-01, mô phỏng bỏ toàn bộ Vận dụng cao | 119 | insufficient_candidates, 0 câu |
| class-01, mô phỏng bỏ toàn bộ Đúng/Sai | 110 | insufficient_candidates, 0 câu |
| class-01, mô phỏng toàn bộ cùng fingerprint | 1 nội dung khác nhau | insufficient_candidates, 0 câu |
| class-02, nguồn thực và bốn tình huống thử | 0 | Không có ngân hàng được phép; 0 câu, không lấy nguồn riêng của giáo viên khác |

Nguồn thực class-01 thiếu toàn bộ dạng 6 (`9C8-i-6`); dạng 1 cũng không có Vận dụng cao ở cả ba hình thức. Bộ ghép vẫn lấy đủ ba câu Vận dụng cao từ các dạng khác, giữ nhãn thật và công khai độ phủ 7/8. Vì vậy “đủ 22 câu” không đồng nghĩa “nguồn phủ đủ tám dạng”. Giáo viên có thể bổ sung dạng 6 để cải thiện độ phủ.

Bốn tình huống loại nguồn là mô phỏng trên danh sách ứng viên của snapshot, không sửa ngân hàng thật. Kết quả đo khả năng ghép nguồn, chưa đo hiệu quả cá nhân hóa trên hồ sơ thật, độ chính xác dự đoán sai lầm hay hiệu quả học tập.

## 4. Tài liệu Word đã cập nhật

- Sách **Đọc hiểu FNWEB2 — Sinh đề cá nhân hóa và dự đoán sai lầm**: chương 21 mô tả thứ tự strict → chuyển dạng trong từng tầng; quota mức bất biến, độ phủ, trùng nội dung, ngân sách tìm kiếm và audit. Phụ lục A.11 giải thích vòng phục hồi và đoạn source `select_same_level`; phụ lục D bổ sung hai module mới và cập nhật dòng bắt đầu hàm từ AST. 73 trang.
- **Báo cáo ngắn gọn FNWEB2 kèm prompt AI**: giải thích chuyển dạng cùng mức, độ phủ thực tế và xử lý thiếu toàn nguồn. Giữ system prompt, lời mở đầu user prompt và schema nguyên văn từ source báo cáo lớp. 6 trang: ba trang trình bày, ba trang đối chiếu prompt.

Hai file tại thư mục `tai-lieu-thuat-toan` của bản xuất đã tạo. Font Times New Roman, không chứa cụm từ “tự học”. Đã render và kiểm tra toàn bộ trang, đối chiếu các trang giữ nguyên bằng ảnh băm; kiểm tra đoạn trích nguồn và nội dung prompt bằng script. Sửa ngắt dòng bảng tra cứu tên file/hàm, bỏ trang chỉ còn hai dòng, kiểm tra không tràn hoặc chồng nội dung.

Các tài liệu Word phiên bản cũ có tên `TAI-LIEU-TU-HOC...` và file giáo án tổng hợp được giữ là bản cũ; hai bản hiện hành nêu trên là bản đã cập nhật Phase 3.

## 5. Giới hạn và kết thúc

Phase 3 không sửa dữ liệu vận hành, không tạo đề cho học sinh thật và không gọi dịch vụ AI thật. Đánh giá độ chính xác nguy cơ sai lầm cần dữ liệu kiểm chứng riêng; số liệu ở đây không phải kết quả đánh giá đó. Phụ lục D.2 của sách vẫn ghi nhận nhánh báo cáo cá nhân riêng có lời gọi `actual_answer` thiếu import; đây là điểm đọc source ngoài thay đổi chuyển dạng, không nằm trong các nhánh AI được xác nhận ở Phase 3.

Ba phase của thay đổi chuyển dạng cùng mức đã hoàn tất: kiểm kê nguồn → triển khai cơ chế và audit → kiểm chứng mở rộng cùng tài liệu cập nhật.
