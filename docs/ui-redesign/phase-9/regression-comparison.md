# Phase 9 — đối chiếu hồi quy toàn bộ

Ngày kiểm chứng: **19/10/2026**. Chạy đủ **59 module đầu vào** trên snapshot trước Phase 9 và mã hiện tại. Mỗi lần chạy dùng DB bộ nhớ, thư mục tạm, chặn dotenv và HTTP/socket; bản baseline còn sao chép riêng nguồn, thư viện và tài nguyên công khai. Không sao chép `.env`, DB thật hoặc uploads.

| Kết quả pytest | Trước Phase 9 | Hiện tại |
|---|---:|---:|
| Test chính đạt | 419 | 445 |
| Subtest đạt | 30 | 33 |
| Test thất bại | 99 | 75 |
| Lỗi collection | 1 | 1 |
| Thời gian pytest | 236,68 giây | 237,94 giây |

**Không có node thất bại mới hoặc lỗi collection mới.** Cả 75 node còn thất bại đều có trong baseline; dòng lỗi đầu tiên đã chuẩn hóa cũng khớp cả 75. Không có failure trong các bộ UI chuyên biệt Phase 3–8. Hai assertion về câu chữ/giao diện nằm trong bộ adaptive lịch sử vẫn thất bại giống baseline; không bị bỏ qua.

24 node baseline không còn thất bại sau bảo trì contract: 18 giữ tên, 6 có tên thay thế phản ánh chức năng hiện tại; thêm 2 test chính mới và 3 subtest. Các kiểm tra quyền, bằng chứng, cache, retry và CSRF được giữ theo [báo cáo bảo trì contract](contracts-maintenance.md). [JSON đối chiếu](regression-comparison.json) ghi cặp tên thay thế và toàn bộ tập node.

Hook cũ đếm cả report subtest vào số passed, tạo raw count 449/478. Bảng trên dùng số test chính và subtest tách riêng từ terminal pytest; raw count vẫn được giữ trong JSON để truy vết.

## 75 failure còn lại

| Module | Số lỗi | Chứng cứ trực tiếp / phạm vi |
|---|---:|---|
| `test_adaptive_personalization.py` | 7 | Fixture/lời gọi học tập lịch sử: hai POST 403; answer_count và selector khác kỳ vọng; failed/fallback; hai assertion câu chữ. Không quy cả bảy về một nguyên nhân. |
| `test_bank_import_phase2_visibility.py` | 2 | Hai confirm ban đầu trả400 “Không có câu hợp lệ để lưu”, trước khi test đi tới kiểm tra replay/cross-bank. |
| `test_bank_selection_phase4.py` | 3 | Teacher authoring trả403; mock nhắm common_diagnostic_selection đã không còn trong route authoring admin. |
| `test_chapter6_migration.py` | 17 | 13 KeyError legacy trong bundle đã chuyển sang Chapter8; bốn kỳ vọng node/topic/tag Chapter6 khác dữ liệu hiện tại. |
| `test_chapter6_only_catalog.py` | 3 | Kỳ vọng chapter6 trong khi catalog trả8; parser tag cũ và số dòng cleanup khác kỳ vọng. |
| `test_curriculum_classification.py` | 12 | Fixture và ID kỳ vọng 9C6-4; validator yêu cầu Chapter8 bài i, dẫn tới ID/node/preview khác kỳ vọng. |
| `test_id6_import.py` | 5 | Fixture TeX/confirm dùng Chapter6:4, rồi truy cập questions/session_id không có trong response tương ứng. |
| `test_import_duplicates.py` | 10 | Dùng helper scope6:4; bảy confirm thiếu preview hợp lệ, một chương bị từ chối; skipped_labels/source-download khác kỳ vọng cũ. |
| `test_phase1_import_review.py` | 2 | Mode trả lời ngắn numeric khác text; một confirm không có row hợp lệ. |
| `test_phase2_import.py` | 9 | SCOPE6:4 không thuộc catalog8:i; old node/response/readiness assertions không khớp. |
| `test_question_classification.py` | 4 | Classifier trả ngoài phạm vi 9C8-i/None/needs_review cho fixture kỳ vọng9C6-4. |
| `test_teacher_keys_phase3.py` | 1 | Endpoint gán nhóm AI theo lớp đã bỏ trả404, test cũ kỳ vọng302. |

Chi tiết từng assertion, vị trí nguồn baseline và nhóm nguyên nhân có trong [baseline-failure-categories.json](baseline-failure-categories.json) và [log đầy đủ](baseline-full-tests.log). Những quan sát này chưa phải kết luận mọi kiểm tra lịch sử đều sai hoặc mọi nghiệp vụ đều đúng; chúng xác định failure đã tồn tại trước phần dọn giao diện.

## Lỗi khám phá test còn lại

`tests/test_lesson4_cleanup.py` import `_backup_sqlite` từ `scripts.cleanup_math9_chapter6_lesson4`, nhưng script này không có cả trong snapshot trước Phase 9 lẫn mã hiện tại. Lần chạy đầu dừng ở collection; lần đầy đủ dùng `--continue-on-collection-errors` để không che 58 module còn lại. Giữ nguyên và báo rõ lỗi này; không khôi phục CLI cleanup có tác dụng xóa dữ liệu để làm xanh nghiệm thu UI.

Bộ kiểm thử toàn repository vẫn có **75 failure và 1 lỗi collection**. Kết quả Phase 9 không được mô tả thành toàn bộ ứng dụng đạt mọi test. Cả hai lần chạy có **0 HTTP/socket thật được thử**; các response AI đều do fixture/mock cung cấp.
