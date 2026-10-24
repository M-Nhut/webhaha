# Question overlays — Phase 5 question-scope backfill

## Phạm vi và assumption

Các tài liệu Phase 1–4 chưa chốt một kế hoạch Phase 5 riêng cho
`bank_question`. `BANK_VISIBILITY_PHASE5` là migration độc lập của
`question_bank.visibility`; tài liệu này chốt Phase 5 question-level theo
assumption bảo thủ sau:

- chỉ rollout/backfill dữ liệu legacy và dọn integration/documentation;
- không thêm đường authoring, import, selector hay UI mới;
- không suy đoán historical mapping khi resolver trung tâm không xác định
  được nguồn;
- không sửa đề thi, `ExamQuestion`, submission, kết quả, nội dung câu hỏi,
  chủ sở hữu ngân hàng hay bất kỳ bảng nào khác.

## Công cụ offline

`scripts/migrate_question_scope_phase5.py` chạy độc lập trên một SQLite file
đã tồn tại. Mặc định là dry-run:

```text
python scripts/migrate_question_scope_phase5.py \
  --database /absolute/path/to/tutoring_center.db
```

Classifier dựng object nhẹ từ các bảng `user`, `question_bank` và
`bank_question`, sau đó gọi trực tiếp `services.access_control.resolve_question_source`.
Nhờ vậy, migration không sao chép rule authorization đang được runtime dùng.
Script không khởi tạo Flask app và không load `.env` hay provider credentials.

Chỉ row có `bank_question.scope IS NULL` mới được lập kế hoạch:

| Resolver hiện tại | Backfill |
| --- | --- |
| `common` từ explicit shared bank + câu do đúng bank admin tạo | `scope=shared`, `private_owner_id=NULL` |
| `private` từ private/legacy-private bank | `scope=private`, owner giáo viên của bank |
| `private` từ teacher contribution/owner trong shared bank | `scope=private`, owner giáo viên đó |
| `unknown` hoặc quan hệ owner/bank malformed | giữ nguyên, báo `review_required` |

Một row đã có scope (kể cả scope malformed hoặc owner không tương thích) luôn
được giữ nguyên và báo cáo. Công cụ không có mapping thủ công để biến private
thành shared. Admin-owned legacy bank (`visibility IS NULL`) cũng không được
tự động mở rộng; cần hoàn tất review/backfill bank-level trước.

## Apply có kiểm soát

Chỉ sau khi review fingerprint của dry-run mới được apply:

```text
python scripts/migrate_question_scope_phase5.py \
  --database /absolute/path/to/tutoring_center.db \
  --apply --expect <database_fingerprint> \
  --backup-dir /absolute/path/to/reviewed-backup
```

Apply tạo `before.sqlite3` mode 600 và `manifest.json` mode 600 trong thư mục
mode 700. Trước khi commit, công cụ kiểm tra fingerprint, backup integrity,
foreign keys và `BEGIN IMMEDIATE`; kế hoạch chỉ update đúng hai cột scope.
Snapshot chứng minh mọi bảng khác và mọi cột khác của `bank_question` không đổi.
Nếu row thay đổi giữa dry-run và transaction, transaction rollback. Apply
không có update là no-op và không tạo backup lần hai; các row unresolved vẫn
giữ trạng thái `review_required`.

Không chạy migration này trên local/production database trong Phase 5 review.
Operator phải tự review report/fingerprint và phê duyệt rollout riêng.
