# Phase 2 — Đặc tả thiết kế toàn bộ màn hình LinhEdu

Ngày: 14/10/2026. **Trạng thái: Phase 3–7 đã triển khai theo yêu cầu người dùng.** Tài liệu này là đặc tả bố cục, tương tác và trạng thái cho Modern White Academy. Shell/auth/profile/errors ghi ở [Phase 3](phase-3/README.md); S01–S06 ngân hàng/soạn câu/phân loại/evaluation/catalog ghi ở [Phase 4](phase-4/README.md). S07–S09 nhập/đối chiếu/chọn câu/biên soạn đề ghi ở [Phase 5](phase-5/README.md). S10–S13 quản lý kiểm tra, ma trận, làm bài/kết quả dùng chung ghi ở [Phase 6](phase-6/README.md). S14–S20 đầu vào, tự luyện, tiến độ và theo dõi/draft ghi ở [Phase 7](phase-7/README.md). Các màn hình còn lại thuộc Phase 8, kiểm tra dọn cuối thuộc Phase 9. API/quyền/chấm điểm giữ nguyên.

Nguồn chức năng: [ma trận Phase 1](phase-1-screen-matrix.md), [ngân hàng và nhập câu hỏi](phase-1-bank-import.md), [kiểm tra và học tập](phase-1-assessments-learning.md), [quản lý và báo cáo](phase-1-management-reports.md), [khung chung](phase-1-shared-assets.md), [inventory tĩnh](phase-1-inventory.json). Các thông số dưới đây là thiết kế mới đề xuất, không mô tả UI cũ đã có hành vi đó.

## 1. Phạm vi và quy tắc thiết kế

- Phủ **32 template trang đang được route render**, **12 component**, **6 template lỗi** và **1 base**. Trong 12 component có 2 ứng viên không còn được include runtime; tài liệu xác định cách hợp nhất/dọn, không tái đưa chúng vào sản phẩm để đủ số lượng.
- `teacher_analytics.html` nằm ngoài 32 trang active; không dựng lại màn hình riêng. Giữ alias `/analytics/teacher` theo contract chuyển hướng hiện tại. Cập nhật Phase 9: template bỏ dùng đã được xóa sau đối chiếu consumer.
- Chỉ ba vai trò `admin`, `teacher`, `student`. Không dựng UI `manager/parent`, không mở quyền backend để khớp điều kiện trình bày cũ.
- Nền ứng dụng xám xanh rất nhạt; sidebar, header, card và vùng đọc màu trắng. Chữ slate, xanh chính **#1D4ED8**, font **Be Vietnam Pro**, fallback **Arial, sans-serif**. Không dùng sticker, bóng cứng, viền đen dày hoặc nội dung cổ vũ lấn át tác vụ.
- Border 1px, radius **8px** cho control và **12px** cho panel/dialog; shadow mềm chỉ cần ở overlay hoặc bề mặt nổi. Khoảng cách theo 4/8px; chữ quản trị **14px**, nội dung câu **16–18px**, desktop control tối thiểu **40px**, mobile tối thiểu **44px**.
- Mỗi page có một H1, một vùng context và một hành động chính theo nhiệm vụ. Dữ liệu và trạng thái dùng nhãn bằng chữ; không dùng màu làm tín hiệu duy nhất.
- Nút/link chỉ hiện khi quyền server và trạng thái dữ liệu cho phép. CTA đang xử lý có disabled thực; lỗi gắn vùng đã thao tác; không xóa nội dung nhập khi request thất bại nếu luồng hiện có giữ được dữ liệu.
- **Không thiết kế autosave, reorder, thêm/xóa câu trong editor đề, khôi phục đáp án đang làm, API mới hoặc số liệu mới như chức năng đã có.** Những nhu cầu này phải được duyệt riêng ngoài phạm vi đổi trình bày.

## 2. Khung bố cục và archetype

### 2.1. Kích thước, responsive, focus

| Thành phần | Desktop ≥1200px | Tablet 768–1199px | Mobile <768px |
|---|---|---|---|
| Shell quản lý | Sidebar 240px, header 64px, gutter 32px; content co giãn | Sidebar thành drawer, header64, gutter24 | Drawer, header gọn, gutter16; control44 |
| Vùng đọc/biểu mẫu | Form tối đa760px; văn bản/câu hỏi khoảng820px; workspace có bảng rộng theo content | Một cột hoặc hai cột khi mỗi cột đủ rộng | Một cột; đáp án, toolbar và form không ép ngang viewport |
| Panel phụ | 280–320px khi còn đủ vùng đọc; có thể sticky dưới header | Chuyển thành section/accordion hoặc nằm trước vùng đọc | Section thu gọn với nhãn rõ; không che nội dung |
| Table/matrix | Header, số và actions thẳng hàng; số dùng tabular numerals | Scroll trong panel có nhãn, không scroll cả trang | Bảng ít cột thành danh sách label/value; matrix/bảng so sánh giữ scroll ngang cục bộ |
| Overlay | Dialog nhỏ max560, soạn câu max1080; giới hạn90vh | Theo viewport, giữ header/actions rõ | Chiếm vùng nội dung khả dụng, body cuộn; luôn có nút đóng/hủy44px |
| Sticky actions | Chỉ ở tác vụ dài cần save/submit; inset đủ dưới cùng | Như desktop khi hữu ích | Không che control cuối, thông báo lỗi hoặc focus bàn phím |

H1 và tiêu đề không dùng chữ HOA toàn dòng dài. Tên bank/lớp/đề được wrap; mã và điểm có vùng ổn định. Toast/flash không đẩy focus vô cớ. Lỗi nhiều trường có summary liên kết trường, focus sau submit; field đơn có label/hint/error riêng. Dialog có tên, `aria-modal`, Escape, focus trap và trả focus về nút mở. Mọi thao tác hover phải có đường keyboard/touch tương đương. Reduced motion bỏ chuyển động trang trí; focus rõ và không bị sticky header che.

### 2.2. Mẫu bố cục dùng chung

| Mã | Archetype | Cấu trúc mặc định và ưu tiên |
|---|---|---|
| L1 | Danh sách quản lý | Page header → action/context → nhóm/list/table → empty state. Không thêm filter server không tồn tại |
| L2 | Form quản lý | Header/back → form nhóm trường → metadata/help phụ → save/cancel. Chỉ field backend đang nhận |
| L3 | Workspace câu hỏi | Header/context → scope + filter → vùng đọc câu chủ đạo → chi tiết/editor → pagination. Độ phủ kiến thức có vùng thu gọn riêng |
| L4 | Wizard kiểm duyệt | Header → stepper có tên → nội dung bước → lỗi/kết quả → actions; bước chưa hợp lệ không giả là hoàn tất |
| L5 | Chọn câu tạo đề | Context lớp/nguồn → vùng chọn câu → tóm tắt/quota/điểm → tạo nháp; nguồn không đủ có giải thích |
| L6 | Biên soạn đề | Header/save status → thông tin đề/điểm → câu theo thứ tự nguồn → review/giao; sửa và preview cùng vùng câu |
| L7 | Làm bài tập trung | Header bài/giờ → câu và đáp án → điều hướng câu/tiến độ → nộp; giảm độ nổi điều hướng quản trị |
| L8 | Kết quả và đối chiếu | Kết quả tổng quan → bước tiếp theo hợp lệ → chi tiết từng câu/bằng chứng → giải thích thêm thu gọn |
| L9 | Ma trận và báo cáo dữ liệu | Context → KPI thực có → bảng/biểu đồ → chi tiết và bằng chứng; legend/số liệu tương đương |
| L10 | Dashboard theo vai trò | Lời chào ngắn → CTA đúng vai trò → KPI hiện có → hoạt động → shortcuts; không có hero quảng cáo |
| L11 | Authentication | Logo/giới thiệu ngắn → form → lỗi → link login/register; độc lập shell, cùng token |
| L12 | Lỗi và phục hồi | Mã lỗi + thông điệp → hành động phục hồi → thông tin kỹ thuật thu gọn; độc lập shell |

Mọi archetype mặc định có trạng thái dữ liệu bình thường/rỗng, field thiếu, nội dung dài, disabled/busy nếu có async, flash/error theo backend và layout mobile. Chi tiết khác biệt của từng trang được ghi bên dưới.

## 3. Ma trận 32 template trang active

| ID | Template chính xác | Archetype | Phase triển khai | Ưu tiên |
|---|---|---|---|---|
| S01 | `question_banks.html` | L1 | 4 | Cao |
| S02 | `question_bank_form.html` | L2 | 4 | Cao |
| S03 | `question_bank_detail.html` | L3 | 4 | Cao nhất |
| S04 | `question_bank_classification.html` | L3 + L2 | 4 | Cao |
| S05 | `classification_evaluation.html` | L4 + L9 | 4 | Chuẩn |
| S06 | `curriculum_catalog.html` | L1 + L2 | 4 | Cao |
| S07 | `question_bank_import.html` | L4 + L3 | 5 | Cao nhất |
| S08 | `assessment_from_bank.html` | L5 | 5 | Cao nhất |
| S09 | `assessment_import.html` | L6 | 5 | Cao nhất |
| S10 | `assessment_list.html` | L1 | 6 — hoàn tất | Cao nhất |
| S11 | `assessment_matrix.html` | L9 | 6 — hoàn tất | Cao |
| S12 | `exam_take.html` | L7 | 6–7 — hoàn tất | Cao nhất |
| S13 | `exam_result.html` | L8 hoặc L1 theo `single_view` | 6–7 — hoàn tất | Cao nhất |
| S14 | `diagnostic_list.html` | L1 | 7 — hoàn tất | Cao |
| S15 | `diagnostic_form.html` | L4 + L5 | 7 — hoàn tất | Cao |
| S16 | `practice_home.html` | L8 hướng hành động | 7 — hoàn tất | Cao |
| S17 | `practice_progress.html` | L9 | 7 — hoàn tất | Cao |
| S18 | `teacher_practice_list.html` | L1 + L9 | 7 — hoàn tất | Cao |
| S19 | `teacher_practice_detail.html` | L8 + L9 | 7 — hoàn tất | Cao |
| S20 | `practice_draft.html` | L6 chỉ đọc câu + L2 phát hành | 7 — hoàn tất | Cao |
| S21 | `index.html` | L10 | 8 | Cao |
| S22 | `courses.html` | L1 | 8 | Chuẩn |
| S23 | `course_form.html` | L2 | 8 | Chuẩn |
| S24 | `course_detail.html` | L1 + L9 context lớp | 8 | Cao |
| S25 | `my_students.html` | L1 | 8 | Chuẩn |
| S26 | `manage_users.html` | L1 + dialog L2 | 8 | Chuẩn |
| S27 | `edit_user.html` | L2 | 8 | Chuẩn |
| S28 | `ai_reports.html` | L9 + L8 | 8 | Cao |
| S29 | `teacher_ai_settings.html` | L2 + L1 | 8 | Chuẩn |
| S30 | `login.html` | L11 | 3 | Cao |
| S31 | `register.html` | L11 | 3 | Chuẩn |
| S32 | `profile.html` | L2 | 3 | Chuẩn |

## 4. Ngân hàng, phân loại và danh mục

### S01 — `question_banks.html`

- **Ưu tiên/bố cục:** header “Ngân hàng câu hỏi”; “Tạo ngân hàng” là action rõ, nhập file là action phụ. Teacher có hai section “Dùng chung” và “Của tôi”; admin có danh sách kiểm toán toàn bộ. Dùng danh sách panel thấp: tên/môn/lớp → mô tả tối đa vài dòng → tổng câu + một hàng bốn mức → actions. Không tạo bốn thẻ KPI lớn cho từng bank.
- **Tương tác:** mở chi tiết từ tên; nhập vào đúng bank; sửa/xóa theo `permissions.can_edit`; xác nhận xóa nêu tên bank và nội dung bị ảnh hưởng. Ngân hàng tạm ngừng dùng bài mới vẫn đọc được nếu server cho phép.
- **Responsive/trạng thái:** desktop có metadata/actions bên phải; mobile chuyển dưới tên, label giữ rõ. Thiếu bank chung và thiếu bank riêng có thông điệp riêng; 0 câu, tên dài, mô tả trống, status inactive có mẫu. Flash xóa/lưu nằm gần header.
- **Quyền/ranh giới:** admin/teacher; không student. Không thêm search/filter/sort/pagination chưa có trên danh sách; không cho teacher sửa bank chung.

### S02 — `question_bank_form.html`

- **Ưu tiên/bố cục:** cùng L2 cho tạo/sửa; một panel760px: tên, môn; khối lớp/chủ đề cùng hàng khi đủ rộng; mô tả full width. Phạm vi bank riêng/chung là thông tin chỉ đọc theo vai trò, không phải toggle.
- **Tương tác:** save/cancel cuối form, trạng thái submit rõ; label và required nhất quán. Tạo và sửa đổi title/action. Giữ đường quay lại danh sách hiện có.
- **Responsive/trạng thái:** mobile mọi field một cột; placeholder không thay label; dữ liệu cũ thiếu grade/topic; validation/flash, busy và tên/mô tả dài. Không hứa khôi phục draft sau refresh.
- **Quyền/ranh giới:** teacher/admin tạo; sửa cần `can_edit_bank`. Giữ `name/subject/grade/topic/description`, POST CSRF; không thêm owner/visibility/is_active không được route nhận như control mới.

### S03 — `question_bank_detail.html`

- **Ưu tiên/bố cục:** workspace trọng tâm. Header compact tên bank + môn/lớp + phạm vi; hàng actions theo quyền. Sau đó scope tabs có count server, filter nằm ngay trước câu; vùng câu khoảng820px được ưu tiên. Desktop có panel độ phủ280–320px bên cạnh hoặc section thu gọn, không đặt toàn bộ ma trận dài trước danh sách. Pagination/25–50 câu và tổng kết quả ở đầu/cuối vùng đọc.
- **Research:** panel độ phủ 8 dạng, bốn mức và ba hình thức; filter node ID6; metadata nguồn chỉ đọc; thiết lập bài luyện chỉ cho câu research được sửa. Ô count/ready dẫn đúng filter/`#bank-results`.
- **General:** nhóm dạng tên tự nhập, lớp/chủ đề phù hợp bank; không ép tên Toán9/C8/8 dạng; `category:<tên>` được giữ. Picker/general editor không buộc curriculum node research.
- **Scope/overlay:** common/mine/all theo server; teacher thấy bank chung và câu bổ sung riêng của mình; nhãn nguồn tách quyền xem/sửa từng câu. Admin audit private contribution không mang ý nghĩa được dùng làm nguồn lớp. Câu chung read-only không hiện nút đổi đáp án/sửa/xóa; overlay được sửa đúng quyền.
- **Câu/đáp án:** heading một hàng số câu + loại/mức vừa đủ; dữ kiện → câu → hình. Đáp án/lời giải thu gọn mặc định và lazy load khi mở. Trạng thái detail loading/error/retry ở ngay câu. Đúng/Sai dạng từng ý rõ, ngắn hiển thị mẫu chấp nhận; dữ liệu legacy chỉ đọc theo nhánh hiện có. Không đổi font câu thành chữ quản trị14px.
- **Soạn/sửa:** editor inline đủ rộng cho preview; thêm thủ công trong dialog max1080 desktop, mobile full area; nhóm context/nội dung/hình → answers theo loại → nhãn → lời giải → review/save. Form ba loại chỉ gửi fieldset active; ảnh giới hạn và reviewed giữ nguyên. Không đưa chọn nhiều tạo đề vào trang này; lối tạo đề sang S08.
- **Responsive/trạng thái:** tablet/mobile panel độ phủ thu gọn trước filter; filter xuống hai/một cột; matrix scroll cục bộ; options dài wrap; ảnh/formula có lightbox; footer actions không che field. Empty bank có CTA nhập/thêm theo quyền; filter rỗng có reset; no permission/removed/expired session phân biệt với thiếu đáp án.
- **Ranh giới:** giữ lazy detail, bank formula scheduler, permission per row, pagination query, `qcard-<id>` và anchors hoặc chuyển toàn bộ consumer. Không thêm API, autosave hoặc broad bulk mutation. Sửa general save constraint và lỗi POST `dt` nghi vấn cần kiểm chứng ở phase triển khai, không coi là đã sửa tại Phase 2.

### S04 — `question_bank_classification.html`

- **Ưu tiên/bố cục:** header bank/back → bốn số liệu gọn → search/status/node filters → list câu chọn được. Thanh action theo selection hiển thị rõ “câu đang hiển thị”; phần gán tay/picker và xác nhận gợi ý tách action để tránh nhầm.
- **Tương tác:** checkbox đầu dòng, select-all phạm vi hiện tại; mixed/selected count là phản hồi client nếu triển khai; chọn cùng hình thức cho bulk gán tay; source-labeled/suggested/stale/teacher-confirmed có chữ và hint. Nội dung câu dùng disclosure khi dài, không tạo UI đáp án chi tiết chưa có.
- **Responsive/trạng thái:** mobile lựa chọn đứng đầu card, action xuống dưới count; picker xếp dọc; bộ lọc rỗng, gợi ý stale, nhóm loại không hợp lệ, redirect flash, không có node. Trạng thái đã khóa nhãn dễ phân biệt với chưa đủ dữ liệu.
- **Quyền/ranh giới:** admin hoặc teacher sở hữu bank riêng; teacher overlay của bank chung không được vào bulk screen. Query hiện tối đa500 câu; phải ghi phạm vi đang xem, không thêm pagination server giả. Không chuyển loại đáp án bằng bulk classification.

### S05 — `classification_evaluation.html`

- **Ưu tiên/bố cục:** luồng ba section: xuất gói nhãn độc lập → upload JSON nhãn → kết quả. Tiêu chí/mẫu số nằm cạnh báo cáo; trạng thái đạt/chưa đạt có nhãn, số và diễn giải ngắn. Không dùng celebratory illustration.
- **Tương tác:** link export, chọn file/submit; report chỉ hiện khi backend có; lỗi file/format ở uploader; ngưỡng cấu hình tách số thực bank. Kết quả invalid/duplicate/coverage/accuracy đọc theo nhóm rõ.
- **Responsive/trạng thái:** section tuần tự trên mọi màn hình; KPI hai cột/một cột; chưa upload, file sai, mẫu nhỏ, report đạt/chưa đạt, thiếu report có mẫu. Không thêm biểu đồ hoặc bảng lỗi chi tiết không có dữ liệu.
- **Quyền/ranh giới:** cùng quyền sửa bank S04; export giữ blinded, không đưa answer/prediction vào gói. `.json`5MB, mảng JSON và gate server giữ nguyên; giao diện không tự tuyên bố “sẵn sàng” từ màu xanh.

### S06 — `curriculum_catalog.html`

- **Ưu tiên/bố cục:** header “Danh mục kiến thức” và context lớp/chương theo query/dữ liệu; filters trước table tên dạng/canonical/active/advanced. Admin có section “Quản lý danh mục” tách khỏi vùng đọc: single entry và bulk paste.
- **Tương tác:** search/inactive filter; admin edit/upsert/toggle; single và bulk có label/format ví dụ, flash lỗi và số lỗi còn lại. Teacher chỉ đọc.
- **Responsive/trạng thái:** table ít cột thành card metadata trên mobile; canonical wrap có kiểm soát; bulk textarea full width; empty context/inactive/no results/data lỗi có mẫu. Không để header C8 cố định mô tả dữ liệu ngoài C8.
- **Ranh giới:** không thêm role manager, mở catalog mới hoặc API sinh ID6. Giữ fields/query/toggle và inactive redirect; canonical/source preview read-only đúng service.

## 5. Nhập và biên soạn kiểm tra

### S07 — `question_bank_import.html`

- **Ưu tiên/bố cục:** L4 năm bước “Tải file → Đọc tài liệu → Kiểm tra → Duyệt và lưu → Kết quả”. Header tên file/đích/mục đích luôn dễ kiểm tra. Stepper thể hiện bước hiện tại, không biểu thị75% xử lý thật. Trạng thái đọc file dùng indeterminate vì chưa có phần trăm server.
- **Bước tải/kiểm tra:** chọn `.tex/.latex`, mẫu theo profile, purpose auto/assessment. Review tách ba chiều: nội dung lỗi/cần xem; phân loại/gợi ý; duplicate. Filter/task summary dẫn vào vùng câu; editor/preview dùng cùng ngôn ngữ với S03/S09.
- **Đối chiếu trùng:** dialog hai bản có nhãn “Đang nhập/Hiện có”; context/câu/hình/answer/lời giải; lý do và quyền thay thế trước quyết định incoming/duplicate/different/neither. Đổi đích nêu rõ phải rescan/mất quyết định cũ; quyết định đang lưu/error inline. Không đặt nút phá hủy cạnh primary bằng cùng độ nổi.
- **Duyệt/kết quả:** summary đủ điều kiện, đích có sẵn chỉ đọc hoặc form tạo bank mới; reviewed được xác nhận trước save. Receipt có thêm/cập nhật/bỏ trùng/cần đối chiếu/lỗi và hành động tiếp tục phần còn lại. Assessment chuyển đúng editor S09; không viết receipt bank cho luồng tạo đề.
- **Responsive/trạng thái:** desktop câu/preview và summary chia vùng khi đủ rộng; mobile so sánh xếp dọc, giữ nhãn mỗi bản và actions dưới cả hai. Bao phủ resume phiên, file sai/rỗng/parse fail, hình retry, duplicate conflict/answer missing, partial save, replay, target revoked, busy/error/cancel. Những câu đã lưu không trông như câu có thể nhập lại.
- **Quyền/ranh giới:** teacher/admin, session owner, target permissions/overlay; không dò private ngoài quyền. Giữ revision/confirmation token, receipt/replay, scope helpers dù partial scope cũ không runtime. No progress giả, no new API, no autosave; đổi cách báo lỗi không thay transaction service.

### S08 — `assessment_from_bank.html`

- **Ưu tiên/bố cục:** context lớp và nguồn nằm trước lựa chọn. Sau GET nguồn hợp lệ, desktop vùng câu chiếm phần lớn + summary300px gồm mode/quota/budget/tổng10 và tạo nháp. Câu xem trước đủ font18, metadata nguồn/mức14.
- **Tương tác:** chọn manual bằng checkbox câu; auto dùng quota theo single/Đúng-Sai/ngắn; budget phần luôn rõ. Summary phản ánh field thực; manual số câu từ selection, auto số từ quota. Giữ hidden course/bank IDs khi POST; nếu mode không dùng một nhóm input thì thể hiện trạng thái dễ hiểu, không mất dữ liệu mode kia ngoài chủ ý.
- **Responsive/trạng thái:** summary chuyển dưới context/trước danh sách có đường tới action cuối; không có nested scroll khó dùng trên mobile. Chưa lớp, lớp không nguồn, bank không câu đủ điều kiện, quota quá nguồn, budget không10, selection trống, dữ liệu thay quyền có mẫu.
- **Quyền/ranh giới:** teacher/admin đúng lớp active và bank theo teacher hiện tại lớp; không đưa bank private của người khác bằng quyền audit admin. Không thêm server search/page/drag reorder, không coi chọn tại bank detail đã có. Tạo bản nháp rồi sang S09.

### S09 — `assessment_import.html`

- **Ưu tiên/bố cục:** header đề + status lưu và “Lưu chỉnh sửa”; thông tin title/class/duration, budget từng phần; issues trước câu. Mỗi câu là panel trắng: preview rõ → sửa nội dung/answer/nhãn/weight/explanation trong disclosure gọn. Kết thúc có reviewed + lưu/giao. Sticky save status chỉ khi không che field.
- **Tương tác:** giữ thứ tự câu từ nguồn; preview công thức debounce theo module hiện có; phân loại report optional, xác nhận nhãn riêng. Trọng số và điểm phân bổ khác nhau về nhãn/hint. Lưu có busy/success/error/dirty; lỗi giữ DOM. Giao nêu rõ lớp, thời gian, tổng10, nội dung khóa; xác nhận review trước POST.
- **Responsive/trạng thái:** desktop fields ba cột; trong câu options phù hợp chiều dài, preview và editor có thể xếp dọc để không bó công thức; mobile một cột, save bar đủ inset. Import/bank origin, chưa lưu/dirty/saving/saved/failed, issues, answer thiếu, hình lỗi, budget không10, session hết quyền, đề đã active/có submissions khóa có mẫu.
- **Quyền/ranh giới:** teacher/admin đúng import session owner; title/class/duration1–240, prefix `q<i>_`, budget/action/reviewed giữ contract. Không thêm câu, xóa câu hoặc reorder trong editor; không autosave/recovery browser. Đề đã giao/có nộp chuyển kết quả theo backend.

### S10 — `assessment_list.html`

- **Ưu tiên/bố cục:** danh sách đề có tên/số câu10đ, lớp, phút, nháp/đã giao, actions. Teacher/admin có tạo từ bank và nhập LaTeX; một primary, một secondary. Student có bản đơn giản ưu tiên đề được giao và đường làm/xem kết quả.
- **Tương tác:** nháp → S09; đã giao → bài làm; matrix/export riêng; student action qua route take để server xác định làm hay đã nộp. Không tự gắn nhãn “chưa làm/đã làm” nếu list context chưa cung cấp.
- **Responsive/trạng thái:** desktop table; mobile row card tên, lớp/thời gian/status, actions; empty role-specific. Nhiều tên dài, thời gian, đề chưa đủ dữ liệu, permission/redirect có mẫu.
- **Ranh giới:** giữ query role hiện có; không thêm tabs/filter/sort giả hoặc ngày deadline không có backend. Nội dung standalone khác diagnostic/practice.

### S11 — `assessment_matrix.html`

- **Ưu tiên/bố cục:** header title/class/phút/câu10đ + tải Excel. Cảnh báo missing/unknown ngay trước matrix; matrix chuẩn và bảng đối chiếu câu ở hai section. Border1px, column header nhiều tầng có độ tương phản và grouping rõ.
- **Tương tác:** chỉ đọc; tải `.xlsx`; link bổ sung nhãn/sửa chỉ nháp chưa có submissions. Bố cục mẫu vẫn giữ các cột, level gốc và level xuất tách rõ; số 0 thể hiện thống nhất dấu/giá trị theo nguồn.
- **Responsive/trạng thái:** matrix giữ scroll ngang có nhãn và hint, không ép font quá nhỏ; bảng details scroll riêng; print landscape/độ rộng là yêu cầu kiểm chứng. Missing/unknown, nháp/khóa, số thập phân/nhiều hàng có mẫu.
- **Quyền/ranh giới:** teacher phụ trách/admin; chỉ standalone; không đổi cách gộp VDC vào Vận dụng/đếm Đúng-Sai hoặc tự tính lại score. Không quảng bá pháp lý/chuẩn áp dụng mới; giữ mẫu server hiện có.

## 6. Làm bài, kết quả và học tập

### S12 — `exam_take.html`

- **Ưu tiên/bố cục:** dùng shell tập trung chung cho standalone, đầu vào, fixed practice và lịch sử. Header bài + context rõ + timer; vùng đọc820px, desktop panel câu/tiến độ280px; mỗi câu context → prompt/hình → answer. Sidebar quản trị giảm độ nổi/thu gọn nhưng luôn có đường điều hướng hợp lệ; không đặt CTA marketing.
- **Tương tác:** điều hướng số câu cuộn anchor; progress phản ánh đáp án thật trong form, TF chưa đủ ý có trạng thái riêng. Single radio; multi legacy checkbox; TF từng ý có lựa chọn Đúng/Sai; short input với label. Submit mở xác nhận số câu đã/chưa trả lời và gửi đúng form, ngăn bấm lặp. Cảnh báo dưới5 phút có chữ; giữ auto-submit nếu code runtime đang có, không đổi rule timer.
- **Responsive/trạng thái:** mobile timer/context compact, grid câu thu gọn, control44; options long wrap, không bẻ công thức tùy tiện; no keyboard trap/nested scroll. Chưa trả lời/partial/đã trả lời, hình lỗi/retry, submit busy/error, server closed/no assignment/already submitted và source invalid có đường server đúng.
- **Biến thể:** standalone10đ theo budget; diagnostic assignment paper chung; fixed22 có giải thích lựa chọn thu gọn; lịch sử không gán cứng22. Student thấy đúng bài mình; teacher/admin không có luồng làm bài bằng route này.
- **Ranh giới:** `#exam-form`, answer names, CSRF, time fields/tracking và anchors phải đi theo JS. Không có autosave/restore đáp án đang nhập; mở lại bài không nghĩa là khôi phục câu trả lời. Không thêm upload bài/tự luận mới hoặc thay countdown semantics bằng UI.

### S13 — `exam_result.html`

- **Ưu tiên/bố cục cá nhân:** header bài → điểm/thang/trạng thái → actions được phép → từng câu. Đối chiếu có nhãn “Bạn trả lời/Đáp án”; TF thể hiện từng ý và một phần; lời giải disclosure dưới answer. Nội dung câu giữ typography chung S12.
- **Biến thể danh sách:** teacher/admin `single_view=false` dùng table học sinh, điểm/tỷ lệ, thời gian/status, link bài; không dựng cùng khung score cá nhân cho danh sách. Student chỉ bài mình; teacher theo submission quyền lớp; admin theo route.
- **Quyết định học tập:** nếu `can_decide`, tiếp tục/kết thúc là nhóm rõ sau score, giữ POST; nguồn không còn hợp lệ không hiện CTA tiếp tục như khả dụng. Diagnostic hoàn tất có bước về tự luyện; standalone về đề/lớp; không làm lẫn mục đích.
- **Responsive/trạng thái:** desktop summary gọn, câu full readable; mobile score/actions stack, TF compare thành row label/value, list table thành card; chưa có bài nộp, chưa chấm lịch sử, đúng/sai/partial/blank, thiếu explanation/image, đã xử lý decision, permission có mẫu.
- **Ranh giới:** không dùng điểm standalone để đổi adaptive mastery; không tạo tính năng chấm lại dữ liệu lịch sử; không thay scoring theo nguồn. Preserve explanation toggle/renderFormulas và selection audit khi có metadata.

### S14 — `diagnostic_list.html`

- **Ưu tiên/bố cục:** danh sách đầu vào có tiêu đề, lớp, câu/thời gian, active/đã giao, bài nộp và actions từ dữ liệu thật. Admin có CTA tạo; teacher xem scope hiện có và actions được phép; student route sang S16.
- **Tương tác:** xem bài làm; xóa xác nhận tên và ảnh hưởng dữ liệu, POST CSRF; không show create teacher vì handler admin-only.
- **Responsive/trạng thái:** table/card theo L1; chưa đề/chưa nộp/đề nguồn lịch sử, flash lỗi xóa/không quyền có mẫu. Không thêm hàng đợi chấm hoặc scheduling chưa có.
- **Ranh giới:** giữ teacher scope creator và delete checks cụ thể; không đổi paper đầu vào đóng băng/cơ chế assignment.

### S15 — `diagnostic_form.html`

- **Ưu tiên/bố cục:** L4 ba bước nguồn → chọn câu → review/giao. Quota22=12+4+6 và coverage8 dạng luôn có summary;40 phút hiện read-only. Desktop danh sách câu + summary; review phải đọc toàn bộ bộ câu và chọn lớp trước confirm.
- **Tương tác:** search/filter/pagination choices25 theo API, disclosure lazy detail; show reason blocked; current selections/restored state được tái xác minh. Chuyển bước có focus heading; digest stale đưa lại review. Confirm thể hiện title/class/cohort rõ.
- **Responsive/trạng thái:** mobile stepper tên ngắn + số bước, quota stack, no horizontal overflow câu; chưa bank, không đủ quota/coverage, empty filter, loading/retry/detail missing, restore expired, review changed, session403/publish failed có mẫu.
- **Quyền/ranh giới:** chỉ admin; không teacher create. Không biến quota/thời gian thành field tự do. sessionStorage tối đa1h giữ metadata selection, không mô tả lưu đáp án/nội dung paper. Giữ review digest và server reconfirm.

### S16 — `practice_home.html`

- **Ưu tiên/bố cục:** chọn lớp ở đầu → **một bước tiếp theo chủ đạo** theo state → bài giáo viên giao → bằng chứng hiện có thu gọn. Student thấy “Làm đầu vào”, “Tiếp tục bài”, “Xem kết quả để chọn tiếp/kết thúc” hoặc “Bắt đầu bài luyện” đúng biến backend.
- **Tương tác:** GET course selector; POST generate; source state là chỉ đọc; resume/decision đúng endpoint. Matrix chỉ xuất khi profile có, không tạo score dự đoán khi chưa đầu vào.
- **Responsive/trạng thái:** single column khoảng820, mobile CTA full width; chưa lớp, chưa đầu vào hợp lệ, đã có assignment, nguồn chưa sẵn sàng, pending decision, resume, teacher papers, chưa profile đều có thông điệp hành động phù hợp.
- **Quyền/ranh giới:** student only; class active + enrollment active; nguồn do đầu vào lớp xác định. Không cho tự chọn bank private hoặc tạo second paper khi đang có đề/decision.

### S17 — `practice_progress.html`

- **Ưu tiên/bố cục:** subject context → dữ liệu đủ/chưa đủ → chỉ số hiện có → score/mastery trend → accuracy/knowledge matrix → history. Phân biệt điểm bài và mức thành thạo bằng tiêu đề/trục/đơn vị rõ.
- **Tương tác:** subject GET; tooltip chart có số và text tương đương/bảng khi triển khai; mở matrix và lịch sử/chi tiết bài. Không thêm filter lớp khi handler đang theo môn.
- **Responsive/trạng thái:** chart co width, mỗi biểu đồ một panel; matrix scroll cục bộ; mobile hai KPI/một chart; cold start, unknown cells, thiếu history, một điểm dữ liệu, improving/declining/stable, null accuracy không đổi thành0.
- **Quyền/ranh giới:** student; giữ Chart.js config và history/masteryHistory khác nghĩa. Không invent dự báo/goal/calendar hoặc gamification; palette JS phải chuyển token đồng bộ.

### S18 — `teacher_practice_list.html`

- **Ưu tiên/bố cục:** chọn lớp → bảng học sinh → xem quá trình; class-report link trong context. Điểm TB ghi rõ chỉ đầu vào/tự luyện, số bài kiểm tra là cột riêng hoặc label rõ.
- **Tương tác:** chọn `course_id`, link detail giữ lớp; không thêm filter/search server. No-class empty có lối lớp học, no-roster khác no-activity.
- **Responsive/trạng thái:** table desktop, student cards mobile; tên/username, practice/assessment counts, avg “Chưa có dữ liệu”, latest chưa làm có mẫu. Không biểu diễn null average thành0đ.
- **Quyền/ranh giới:** teacher đúng lớp/admin; course ngoài quyền403. Alias analytics tiếp tục redirect, không tạo tab analytics cũ.

### S19 — `teacher_practice_detail.html`

- **Ưu tiên/bố cục:** học sinh + phạm vi lớp → summary hồ sơ theo môn → knowledge matrix thu gọn → bằng chứng kiểm tra riêng → lịch sử → hỗ trợ tạo draft. Link AI theo lớp nằm cạnh context, không nhúng lại một report cũ dài.
- **Tương tác:** GET lớp/tất cả lớp được phép; form bài củng cố trong disclosure với course/banks, fixed22, chapter/section/topic, levels, mix tổng100. Bank checkbox bị disable/uncheck nếu đổi lớp làm nguồn invalid; preview draft đến S20.
- **Responsive/trạng thái:** mobile mọi section stack, matrix/bảng scroll riêng, form một cột; no data/unknown/cold start, no history/no banks, class scope invalid, fixed source unavailable và generate error có mẫu.
- **Quyền/ranh giới:** teacher phải có active enrollment trong lớp phụ trách/admin theo route; metadata per-course giữ. Không khôi phục control AI review cũ chỉ vì endpoint vẫn tồn tại; dùng workspace S28, không mở thêm nguồn riêng ngoài resolver.

### S20 — `practice_draft.html`

- **Ưu tiên/bố cục:** header “Duyệt bài luyện 22 câu” → giải thích lựa chọn thu gọn → form title/phút/phát hành → câu/answer chỉ đọc theo ba phần. Nêu rõ không sửa bộ câu tại đây; save label “Lưu trạng thái phát hành”.
- **Tương tác:** title/duration5–180/is_active; source checks khi publish; content/labels frozen; có submissions thì khóa sửa theo backend. Muốn thay nguồn/câu dùng luồng tạo draft mới đang có, không cung cấp drag/add/remove.
- **Responsive/trạng thái:** form760 và câu820, mobile stack; chưa giao/đã giao/khóa/source invalid/flash, thiếu explanation/metadata có mẫu. Không chỉ gọi trạng thái read-only là lỗi.
- **Quyền/ranh giới:** teacher người tạo/admin; phát hành teacher đúng lớp; giữ22 và selection provenance, không autosave.

## 7. Tổng quan, quản lý, tài khoản và AI

### S21 — `index.html`

- **Ưu tiên/bố cục:** lời chào ngắn không hero/logo lớn; CTA theo role; hai KPI đang có; hoạt động gần đây chủ đạo và shortcuts phụ. Admin tổng học sinh/teacher, teacher lớp/học sinh, student lớp/bài hoàn tất.
- **Tương tác:** shortcuts đúng quyền và mục đích; teacher ngân hàng/theo dõi, student tự luyện/tiến độ, admin quản lý. Chỉ dùng counts/activities thật, không biến `exams_data` chưa render thành deadline/task giả.
- **Responsive/trạng thái:** desktop2 KPI, activity + shortcuts; mobile1 cột hoặc2 KPI đủ chiều rộng; empty activities có action đúng role; tên dài/count0/dates thiếu có mẫu.
- **Ranh giới:** không dashboard manager/parent, không thêm lịch/goal/AI insights chưa có; label KPI giữ ý nghĩa aggregate hiện tại.

### S22 — `courses.html`

- **Ưu tiên/bố cục:** header “Lớp học”; admin create; table tên/môn/teacher/phòng/status/actions; giảm avatar/metadata cạnh tranh với tên lớp.
- **Tương tác:** detail, admin edit/delete; confirm delete tên rõ; chưa phân teacher/phòng có label nhẹ. Teacher/student không có mutate controls.
- **Responsive/trạng thái:** mobile card lớp + label teacher/phòng/status/actions; empty theo role; inactive/active và enrollment state khác nghĩa, lỗi flash/permission có mẫu.
- **Ranh giới:** không tự thêm filter/search/page; không đổi query student enrollment khi đang redesign; trạng thái sai phạm vi kiểm thử riêng.

### S23 — `course_form.html`

- **Ưu tiên/bố cục:** form760/hoặc hai panel đủ rộng: thông tin lớp chính, teacher assignment phụ. Ngày bắt đầu/kết thúc cùng nhóm; preview teacher compact; AI note không làm form thành cài đặt credential.
- **Tương tác:** create/edit, teacher preview, active, save/cancel; info teacher only. Giữ field names/date formatting và teacher change semantics.
- **Responsive/trạng thái:** mobile một cột, preview phía dưới select; teacher missing/unassigned, dates blank, long description, submitting/flash/bad date xử lý server có mẫu.
- **Quyền/ranh giới:** admin only. Không thêm ai_key_group selector hay đổi effective config; giữ cấu hình do teacher hiện tại quyết định.

### S24 — `course_detail.html`

- **Ưu tiên/bố cục:** header lớp + admin edit/teacher-admin theo dõi; summary lớp compact, roster là nội dung chính; admin ghi danh ngay trên roster; AI report link trong section riêng gọn, giữ anchor.
- **Tương tác:** ghi danh select student, POST; lớp→theo dõi/AI giữ context; student chỉ đọc trong quyền. Thông tin ngày/phòng/teacher/AI khả dụng không dùng badge lớn lặp.
- **Responsive/trạng thái:** desktop summary280 + roster; mobile summary thu gọn/stack, roster cards hoặc scroll trong panel; no teacher/room/dates/description/roster, hết student khả dụng, enrollment duplicate/reactivate/not found có mẫu.
- **Ranh giới:** không phục hồi điểm danh/học phí/lịch đã xóa; không thêm hủy ghi danh/API. Teacher/student sai quyền giữ redirect/flash; admin-only mutation.

### S25 — `my_students.html`

- **Ưu tiên/bố cục:** danh bạ teacher: tên/username, mã, vị trí/lớp, liên hệ. Table14px, tên rõ; không lẫn với bảng theo dõi điểm S18.
- **Tương tác:** chỉ các link thật cần nếu hiện có; không thêm edit/student profile endpoint mới. Lối vào theo dõi chung dùng navigation hiện có.
- **Responsive/trạng thái:** mobile card label/value; no students, phone/position missing, tên/mã dài có mẫu.
- **Quyền/ranh giới:** teacher thực sự; admin handler redirect, không tự mở quyền admin. Không phục hồi parent student selector.

### S26 — `manage_users.html`

- **Ưu tiên/bố cục:** tabs học sinh/giáo viên, action thêm; table danh bạ identity/code/role/phone/position/status/actions. Modal thêm cùng L2, field groups dễ đọc.
- **Tương tác:** modal semantics/focus/Escape/return focus; tạo student/teacher; xóa confirm; role-specific position không làm mất field hợp lệ. Submit names/POST CSRF giữ; không show admin option backend từ chối.
- **Responsive/trạng thái:** table desktop, card mobile; dialog body cuộn; empty từng tab, active/locked, validation server/flash, close/cancel/open có mẫu; không hứa draft modal sống sau reload.
- **Ranh giới:** admin only. Không thêm search/bulk/reset hàng loạt/mở role manager/parent. Admin account được bảo vệ theo backend.

### S27 — `edit_user.html`

- **Ưu tiên/bố cục:** form760 title identity; fields role/code/fullname/username/phone/position/active; save primary, reset mật khẩu nhóm phụ có cảnh báo riêng, back/cancel nhất quán.
- **Tương tác:** sửa role student/teacher, khóa/mở, reset POST confirm cụ thể; field không hợp lệ không làm UI ám chỉ role admin được đổi. Trường hợp admin protected thể hiện read-only/không khả dụng tương ứng backend.
- **Responsive/trạng thái:** mobile một cột; reset không chèn cạnh save bằng cùng màu; missing data, server-rejected role, not found, protected admin, success/error flash có mẫu.
- **Ranh giới:** admin actor; không đổi mật khẩu mặc định hoặc thêm quy trình mail invite trong redesign. Giữ self-delete/admin protections.

### S28 — `ai_reports.html`

- **Ưu tiên/bố cục:** context “Cả lớp/Cá nhân” + lớp/student ở đầu; tabs Tổng quan/Chi tiết không lẫn scope. Overview: KPI hiện có → grouped bar + distribution → table skill/roster → evidence. Detail: status/summary → cause/risk/recommendation → evidence → metadata/archive thu gọn.
- **Tương tác:** filter skill/source/type chỉ đổi số liệu; click chart lọc đúng query, outcome lọc bằng chứng, evidence paging; disclosure render toán. Reload, generate và review phân cấp; generate là thao tác teacher rõ nghĩa, không CTA giả admin. Link detail có `refresh=1` hiện có thể phát sinh AI; copy/chỉ báo phải cho biết ý nghĩa, không gọi như đọc tĩnh đơn thuần.
- **Responsive/trạng thái:** desktopcharts 2 cột khi đủ; tablet/mobile1 cột, KPI2/1; labels không quá nhỏ, tables scroll, evidence compare stack. Bốn modes class/individual × overview/detail đầy đủ: no class/no roster/no evidence/filter empty, initial facts, loading, processing, missing, stale, failed, completed, confirmed, archive absent/present, expired session/retry.
- **Quyền/ranh giới:** admin xem/review theo route, teacher đúng lớp mới generate; student không vào. Palette chart JS và CSS cùng token; không đưa hypothesis thành fact hoặc null thành0. Giữ class-bound no-store APIs, request sequence/polling/CSRF, report scope Bài25+26 thật và source evidence; không thêm AI chat/API mới.

### S29 — `teacher_ai_settings.html`

- **Ưu tiên/bố cục:** header “Khóa AI của tôi” → readiness banner nếu cần → form batch → bảng masked key/status/last test/actions. Security note ngắn phục vụ thao tác, không phủ kín trang.
- **Tương tác:** keys mỗi dòng tối đa20, kiểm tra/lưu; retry/delete theo key, confirm delete; disabled thật khi security chưa ready hoặc group paused; không hiện secret sau save.
- **Responsive/trạng thái:** form760, table rộng đủ labels; mobile key card/action44; no group/no keys/archived groups, paused, ready, verified-waiting-quota, deferred, invalid/revoked, permission/network/model/overload/malformed errors có label và next step hợp lý.
- **Quyền/ranh giới:** teacher own default group; admin không được vào để xem keys; không mở thêm group editor hoặc selector cũ. Runtime quota không đổi verification success thành failed; raw keys không đi vào ảnh/demo/log.

### S30 — `login.html`

- **Ưu tiên/bố cục:** L11 desktop split có phần thương hiệu ngắn, form tối đa400–440; nền trắng, logo tĩnh nhỏ; title/login/instructions. Mobile bỏ phần giới thiệu dài, logo và form đủ gutter.
- **Tương tác:** username/password, visibility control, submit, đăng ký. Password manager/paste/autocomplete hoạt động; errors nối đúng trường, auth failure là alert rõ không lộ dữ liệu tài khoản.
- **Responsive/trạng thái:** form không bị viewport-height khóa khi keyboard/zoom; empty/invalid/locked/success registration flash, visibility toggle có keyboard; busy tránh double submit.
- **Ranh giới:** WTForms/CSRF/next giữ; không thêm forgot-password/SSO backend chưa có; không dùng cartoon assets cũ.

### S31 — `register.html`

- **Ưu tiên/bố cục:** cùng auth system S30; form lớn hơn nhưng một luồng rõ: identity → account/role → optional contact/position → password/confirm. Desktop field pairs khi đủ rộng, mobile1 cột.
- **Tương tác:** chỉ student/teacher; validation inline + summary nếu nhiều; link login; required/optional rõ; password manager new-password; submit redirect theo route.
- **Trạng thái:** username/code duplicate, password short/mismatch, role invalid, optional blank, success, long name có mẫu. Không thêm terms checkbox hoặc verification step không có nghiệp vụ.
- **Ranh giới:** giữ names/validators/source labels, không tự đăng ký admin/manager/parent. Bỏ các yếu tố trang trí pop-study/sticker sau chuyển UI; logo thương hiệu giữ.

### S32 — `profile.html`

- **Ưu tiên/bố cục:** hai section “Thông tin cá nhân” và “Đổi mật khẩu”, mỗi form action riêng; avatar + chọn ảnh đầu section hồ sơ; identity/contact/birth/position dưới. Desktop hai cột khi đủ, mobile tuần tự.
- **Tương tác:** preview ảnh trong cùng form multipart; profile/password submit tách rõ; error gắn đúng form; change password giữ paste/autocomplete. Không gộp hai submit tạo validation chéo.
- **Trạng thái:** avatar default/current/new/invalid, username duplicate, ngày trống, old password wrong/new mismatch, success/error, upload busy có mẫu.
- **Quyền/ranh giới:** mọi tài khoản đăng nhập; chỉ dữ liệu chính mình. Giữ `submit_profile/submit_password`, hidden CSRF, fields và avatar contract; không thêm public profile/parent links.

## 8. Base và 12 component

### `base.html` — shell toàn ứng dụng

- **Bố cục:** document head/meta CSRF → skip link → navigation → header → main H1/content/flash → footer/bootstrap. White shell/slate/blue theo một token source; layout content theo archetype, không chồng theme cũ cuối head.
- **Tương tác:** drawer menu, focus/overlay/Escape/return focus, active route và `aria-current`; page title không lặp H1; forms/MathJax/FormulaRenderer/Alpine/HTMX/Lucide giữ lifecycle. Toast, dialog và image lightbox dùng z-index thống nhất.
- **Responsive/trạng thái:** desktop/tablet/mobile theo2.1; bfcache/resizing/reduced motion/print; file asset/error network không làm main biến mất. Shell có mode tập trung cho bài làm, không thay permission.
- **Ranh giới:** đổi template block hoặc data hooks phải chuyển consumer đồng bộ; không xóa JS nghiệp vụ chỉ vì bỏ theme; assets/phần tử cũ dọn sau migrate. HTML độc lập auth/errors dùng cùng tokens nhưng không cần sidebar.

| Component chính xác | Đặc tả layout/tương tác/trạng thái | Quyền/ranh giới và đích chuyển |
|---|---|---|
| `components/navigation.html` | Sidebar trắng240, logo nhỏ, nhóm mục theo nhiệm vụ, active xanh nhạt; drawer trên tablet/mobile có label và close44; dài có scroll riêng. Focus/expanded/current rõ | Chỉ admin/teacher/student và links thật; endpoint checks server giữ; không phục hồi manager/parent/menu tính năng lịch sử |
| `components/header.html` | Header64, breadcrumb/context vừa đủ, account/avatar/profile/logout compact; mobile menu button + title, actions không đè nhau; tên dài wrap/truncate có text đầy đủ | Profile/logout đúng routes; không thêm search/global notifications backend chưa có |
| `components/footer.html` | Bootstrap tài nguyên renderer/icons/libs tách khỏi trang trí; footer text nếu có ngắn và nhẹ, không chiếm viewport. Không ảnh hưởng flow bài làm | Thứ tự scripts/formula init và page blocks giữ; runtime lỗi cần kiểm thử, không thay bằng footer marketing |
| `components/flash_messages.html` | Notice1px semantic palette, icon+text+close chỉ khi có handler; error `alert`, success/info `status`; list nhiều messages có spacing8, không biến tất cả thành toast mất nhanh | Escape message text, không lộ secret; feedback redirect/POST không bị mất khi chuyển layout |
| `components/bank_overview.html` | Research/general groups từ server; độ phủ trong panel phụ/disclosure; matrix4×3, count/ready có label; empty0 “Cần bổ sung”; selected outline/blue rõ; mobile scroll nội bộ | Không áp8 dạng research cho general; ô link giữ scope/filter/per_page; count toàn quyền khác result count; anchors S03 giữ |
| `components/bank_pagination.html` | Summary first–last/total + page; desktop inline, mobile wrap trước/sau và số vừa đủ; disabled không tương tác; current `aria-current` | Giữ URL server filter/25–50 và anchors; không thêm client paginate làm thiếu dữ liệu |
| `components/id6_picker.html` | Nhãn kiến thức tách cấp lớp/chương/bài/dạng/mức/loại; research picker theo catalog, general category text; metadata source read-only; mobile1 cột; helper/hint/error tại field | D/T/S và fieldset type/answers giữ; không API sinh ID6, không buộc general node; draft đáp án khi chuyển type theo JS contract |
| `components/import_duplicates.html` | Toolbar status/count, list đối chiếu và dialog hai bản rõ label; decision primary/secondary; mobile stack; focus trap, Escape, restore; loading/save/error/conflict/revision/receipt/partial có mẫu | Incoming/duplicate/different/neither chỉ khi policy cho; raw private ngoài quyền không hiện; không đổi receipt/replay/tokens |
| `components/import_scope.html` | **Không dựng partial thành bước runtime mới** vì Phase1 chưa thấy include active. Nếu dọn, gộp phần context/scope đang dùng vào S07; chọn scope có label/group, lỗi gần field và indeterminate xử lý | Không xóa `import_scope.js/css` theo tên partial: wizard còn helper restore/steps; xử lý consumer trước xóa ở phase9 |
| `components/practice_skill_matrix.html` | Matrix8 dạng×4 mức, heading “Chưa biết ≠ yếu”; mỗi ô % nếu có + state + số câu khác nhau/lượt; border nhẹ, semantic bg nhạt; mobile scroll với row/column labels rõ | Unknown/null không0/yếu; giữ sufficient/distinct_count/session_count, không biến thành calibrated difficulty hoặc score |
| `components/selection_audit.html` | Disclosure giải thích lựa chọn, metrics gọn, actual vs target tables, source shortage/transfers; đặt sau nội dung chính ở take/result, trước preview draft khi phù hợp; mobile tables scroll | Chỉ hiện khi algorithm metadata có; fixed/legacy khác nhau; không đưa thông số thuật toán lên primary flow học sinh, không xóa provenance |
| `components/diagnostic_report.html` | **Không tái thêm vào runtime**; preview/test consumer cần chuyển sang report design S28/khối evidence chung nếu vẫn cần. Design cho dữ liệu hiện có: observed → hypothesis → support, readable paragraphs/compare/table, mobile stack | Giữ distinction fact/hypothesis, bằng chứng và no-data khi chuyển consumer; xóa partial chỉ sau scripts/preview/tests cập nhật. Không mất contract vì không include runtime |

Hai partial không active vẫn được xét trong phạm vi làm sạch toàn bộ giao diện: quyết định là hợp nhất/dọn consumer, không để giao diện cũ tồn tại như một “phiên bản dự phòng”. Đây là đề xuất phase tiếp theo, chưa xóa tại Phase 2.

## 9. Sáu template lỗi và fallback

Tất cả dùng L12, palette/font/control mới, logo tĩnh nhỏ. Main panel khoảng640px: mã + H1/message; primary quay về nơi hợp lệ; secondary quay lại khi có history; technical disclosure với request id/copy. Không dùng hình cartoon lớn hoặc bốn quick cards dẫn vào route ngoài quyền.

| Template chính xác | Ưu tiên thông điệp và action | Trạng thái/ranh giới |
|---|---|---|
| `errors/error.html` | Master độc lập, layout lỗi + technical disclosure; title/message/status từ handler. “Quay lại”, “Trang chủ/Đăng nhập” tùy auth/context; chi tiết kỹ thuật thu gọn | Fallback cho429 và mã khác/missing template; JSON API giữ JSON. Copy success/error accessible; details chỉ khi server cấp; không đọc/log credentials |
| `errors/400.html` | “Yêu cầu không hợp lệ”; hướng quay form/trang trước, thông điệp server đủ hiểu | CSRF/field request lỗi không mất status400; không gợi ý tự gửi lại payment/irreversible action; không thay handler bằng success view |
| `errors/403.html` | “Bạn không có quyền truy cập”; đăng nhập nếu guest, trở về workspace nếu đã auth | Không tự mở quyền; không dẫn student sang ngân hàng/AI; chi tiết hạn chế có thể do role hoặc tài nguyên, không suy ra tài khoản bị khóa |
| `errors/404.html` | “Không tìm thấy trang hoặc tài nguyên”; home/back; bank/search link chỉ nếu route có quyền và có control thật | Item deleted/link sai/unknown resource có cùng pattern; không thêm global search API |
| `errors/405.html` | “Thao tác không được hỗ trợ”; quay trang hợp lệ để thực hiện lại | Method/request id ở kỹ thuật; không nút replay tự động; status405 giữ |
| `errors/500.html` | “Hệ thống chưa xử lý được yêu cầu”; quay lại/home; copy mã sự cố | Không hứa đội kỹ thuật đã nhận nếu chưa có hệ thống thông báo; không lộ exception production; status500/rollback handler giữ |

**Responsive lỗi:** mobile gutter16, panel full width, actions44 xếp dọc, mã trạng thái không chiếm quá nửa màn hình; technical values wrap; browser zoom/keyboard vẫn đọc được. Keyboard mở disclosure/copy, role status cho copy. Print bỏ actions nếu phù hợp. Không phải sáu ứng dụng CSS riêng: variants cùng master/system.

## 10. Ranh giới backend và checklist review Phase 2

### 10.1. Những điều không được đổi ngầm khi triển khai thiết kế

1. Quyền bank shared/private/overlay và per-question, class-bound sources, import session ownership, assignment/student ownership và teacher-only credential/AI generation.
2. Source research/general; standalone vs diagnostic vs practice; unknown/null vs0; observed vs hypothesis; verified key vs quota wait.
3. POST/CSRF/form names, JSON response/URL/query/anchor contracts hoặc consumer đổi đồng bộ có kiểm thử; alias redirect không biến mất khi dọn template.
4. Fixed22,12+4+6, diagnostic40 phút, total10 standalone, weighting/scoring/rule legacy, source freezes và submitted locks; UI không tự suy diễn backend mới.
5. Lưu explicit editor/import, partial receipt/replay, digest/revision, no autosave/restore đáp án, no reorder/new question editor control khi backend chưa có.
6. Math/formula/TikZ/image rendering, lazy detail, viewport scheduler, image retry/lightbox, Chart.js data semantics và current polling/request sequence.

### 10.2. Review thiết kế cần xác nhận

- Hướng trắng/slate/blue, typography/density/radius và shell thống nhất; khung mobile vẫn đủ đọc câu/toán.
- S03 ngân hàng general/research/overlay và độ phủ không đẩy nội dung quá sâu; actions đúng quyền từng câu.
- S08/S09/S10 phân biệt chọn câu, biên soạn và quản lý đề; S12/S13 đủ ba mục đích và các trạng thái kết quả.
- Các màn hình CRUD/auth/errors/report đều có thiết kế mới, không miễn trừ main.css hoặc trang ít dùng.
- Hướng hợp nhất/dọn partial không runtime và CSS/JS cũ được chấp nhận; chưa xóa trước chuyển consumer.

### 10.3. Tiêu chí nghiệm thu ở phase triển khai

Mỗi S01…S32, base, component active và error variant phải có evidence desktop/mobile + role/state phù hợp danh mục; keyboard/focus/dialog/contrast/long text/formula/images/print kiểm tra nơi liên quan. Tests dùng dữ liệu giả/DB tách biệt, giữ contract chức năng và phát hiện permission regressions. Tìm tham chiếu/assets/styles cũ chỉ là một phần cleanup; cần kiểm tra browser/network/console sau migrate trước kết luận sạch.

**Duyệt tài liệu/bản mẫu Phase 2 chưa phải xác nhận giao diện đã triển khai hoặc đã pass test.** Triển khai các phase sau chỉ bắt đầu khi người dùng duyệt thiết kế và phạm vi thực hiện tương ứng.
