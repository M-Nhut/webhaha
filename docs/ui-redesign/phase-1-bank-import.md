# Phase 1 — Kiểm kê ngân hàng câu hỏi, nhập liệu và phân loại

Ngày kiểm kê: 13/10/2026. Phạm vi: đọc mã nguồn, không triển khai giao diện, không khởi động ứng dụng, không truy cập cơ sở dữ liệu thật hoặc `.env`.

## 1. Mức độ xác minh

- **Đã quan sát trong code:** route, template, nhánh quyền truy cập, điều kiện hiển thị, hook JavaScript, CSS, kiểm thử hiện có.
- **Yêu cầu thiết kế:** các kết quả cần đạt trong phase thiết kế/triển khai sau khi được duyệt; không phải chức năng đã tồn tại.
- **Chưa kiểm chứng runtime:** giao diện thật, khả năng đọc công thức, dữ liệu thực tế, độ trễ import, bàn phím, mobile, trạng thái mạng và kết quả kiểm thử. Tài liệu này không tuyên bố ứng dụng đang chạy đúng.

Đã đọc skill `ui-ux-pro-max` tại `/Users/mac/.agents/skills/ui-ux-pro-max/SKILL.md`. Tra cứu tập trung `keyboard focus modal --domain ux` trả đúng nhóm UX: focus nhìn thấy và không bị overlay/sticky che khuất. Các hướng dẫn này được đưa vào yêu cầu kiểm chứng modal; chưa chốt hệ thống màu/font hoặc bố cục Phase 2.

## 2. Danh mục màn hình

Có **7 template màn hình**, trong đó form tạo/sửa có hai chế độ; trang chi tiết và wizard có nhiều trạng thái con.

| Mã | Template | Endpoint, URL, phương thức | Quyền thực tế trong route |
|---|---|---|---|
| BANK-01 | `templates/question_banks.html` | `question_bank_list` · `GET /question-banks` | Đăng nhập + `teacher` hoặc `admin`; học sinh/manager không được qua decorator này |
| BANK-02 | `templates/question_bank_form.html` | `create_question_bank` · `GET/POST /question-banks/new`; `edit_question_bank` · `GET/POST /question-banks/<bank_id>/edit` | Tạo: teacher/admin. Sửa: admin hoặc teacher sở hữu bank riêng/legacy riêng hợp lệ |
| BANK-03 | `templates/question_bank_detail.html` | `question_bank_detail` · `GET /question-banks/<bank_id>` | Admin xem mọi bank để kiểm toán; teacher xem bank chung hợp lệ và bank riêng do mình sở hữu |
| BANK-04 | `templates/question_bank_import.html` | `import_questions_page` · `GET /question-banks/import` | Teacher/admin. Danh sách đích được lọc bằng `can_import_questions` |
| BANK-05 | `templates/question_bank_classification.html` | `question_bank_classification` · `GET /question-banks/<bank_id>/classification` | Cần quyền sửa **bank**. Teacher chỉ sở hữu bank riêng; admin mọi bank. Teacher có overlay trong bank chung không có quyền vào màn hình này |
| BANK-06 | `templates/classification_evaluation.html` | `classification_evaluation_page` · `GET/POST /question-banks/<bank_id>/classification/evaluation` | Cần quyền sửa bank, giống BANK-05 |
| BANK-07 | `templates/curriculum_catalog.html` | `curriculum_catalog` · `GET/POST /curriculum` | GET: teacher/admin. POST: chỉ admin. Route toggle chỉ admin |

### Quy tắc quyền cần giữ xuyên suốt

Nguồn chính: `services/access_control.py`, `routes/question_bank.py`, `routes/imports.py`.

- `role_required("teacher")` luôn cho admin đi qua, nhưng không tự cho manager đi qua.
- Tạo bank: phạm vi do server đóng dấu. Admin tạo bank chia sẻ; teacher tạo bank riêng. Không thêm tùy chọn chia sẻ vào UI nếu chưa có nghiệp vụ được duyệt.
- Teacher xem bank chung; bank chung và câu chung chỉ đọc. Teacher có thể **thêm/import câu riêng của mình** vào bank chung. Quyền thêm khác quyền sửa bank.
- Teacher chỉ thấy và sửa/xóa câu riêng của mình trong bank chung; câu riêng của teacher khác không được đưa vào JSON để trình duyệt che lại.
- Admin có thể kiểm toán dữ liệu cũ/không rõ phạm vi. Nhãn riêng tư đối với admin là “Riêng tư — giáo viên sở hữu”, không được ghi “chỉ bạn”.
- Bank ngừng hoạt động có thể vẫn xem được theo policy, nhưng không được chọn cho bài mới (`can_use_bank=False`). BANK-01 có nhãn “Tạm ngưng dùng cho bài mới”; không tìm thấy UI bật/tắt bank trong nhóm trang này.
- Nhãn legacy/phạm vi bất thường không được tự diễn giải thành dùng chung. Các bộ đếm, tab và filter phải tiếp tục dùng tập dữ liệu đã được server cấp quyền.

## 3. BANK-01 — Danh sách ngân hàng

### Quan sát trong code

- Teacher thấy hai khu “Ngân hàng dùng chung” và “Ngân hàng của tôi”; admin có một danh sách toàn bộ.
- Mỗi card có môn, lớp, tên/link chi tiết, mô tả tùy chọn, tổng số câu, bốn mức nhận thức, ngày tạo, trạng thái không dùng cho bài mới.
- Thao tác chung: tải `.tex`, import, tạo bank. Thao tác từng bank: chi tiết; sửa/xóa chỉ khi `permissions.can_edit`.
- Xóa bank là form POST có CSRF và `confirm()` trình duyệt, xóa thật cả câu/đáp án/tài nguyên liên quan theo route.
- Trống: không có bank chung; không có bank riêng; admin không có bank nào với CTA tạo/import.
- Danh sách chưa có UI tìm kiếm, lọc, sắp xếp, phân trang hoặc loading cục bộ. Không được mô tả các chức năng này là đã có.
- `grouped_bank_stats` tính thống kê theo quyền; không tải nội dung toàn bộ câu để dựng card.

### Yêu cầu thiết kế sau kiểm kê

- Làm rõ phạm vi bank, số câu và hành động chính; giảm sự lặp lại của bốn ô số liệu lớn trên mọi card.
- Bố cục phải chịu được tên dài, mô tả dài, bank 0 câu, số câu lớn, hai khu không đều số lượng.
- Quyết định card hay bảng tại Phase 2 dựa trên nhiệm vụ quản lý. Tìm kiếm/phân trang danh sách bank nếu đề xuất là bổ sung chức năng, cần ghi rõ phạm vi.
- Xóa phải có xác nhận cụ thể bank nào và hậu quả; trạng thái không dùng bài mới khác với không có quyền xem.

## 4. BANK-02 — Tạo/sửa ngân hàng

### Quan sát trong code

- Form POST thường, CSRF; tạo/sửa dùng cùng template, thay tiêu đề, giá trị và nút.
- Trường: `name` bắt buộc, `subject` bắt buộc, `grade`, `topic`, `description` tùy chọn. Có 9 môn ở form tạo/sửa; danh sách môn trong wizard tạo bank mới ngắn hơn.
- Nút lưu; Hủy/Quay lại luôn trở về danh sách bank, kể cả khi mở sửa từ chi tiết.
- Không có loading/submitting UI, lỗi gắn từng trường hoặc giữ bản nhập khi server redirect. Thông báo dựa trên flash từ backend.
- Không có trường `visibility`, `is_active`, chọn chủ sở hữu; đây là các quyết định server, không bỏ sót trường thiết kế.

### Yêu cầu thiết kế

- Form có nhóm thông tin cơ bản và mô tả, nhãn/hint rõ cho khối lớp/chủ đề, trạng thái đang lưu và lỗi vẫn giữ dữ liệu khi khả thi.
- Nêu rõ bank tạo mới sẽ riêng tư/chia sẻ theo vai trò mà không cung cấp điều khiển vượt quyền.
- Chuẩn hóa danh sách môn và hành vi quay lại trong phạm vi được duyệt.

## 5. BANK-03 — Chi tiết ngân hàng và câu hỏi

### Hai chế độ dữ liệu bắt buộc

- **Research:** Toán 9, Chương 8 bài `i`, danh mục ID6 và 8 dạng; nhận diện theo `is_research_bank` (khối lớp, chủ đề/tên hoặc câu có curriculum node).
- **General:** nhiều lớp/chủ đề; dạng kiến thức là tên tự nhập, `node_id` filter có dạng `category:<tên>`, không buộc catalog nghiên cứu. Không được xây mọi bank thành Toán 9.

### Cấu trúc hiện tại

1. Header: môn/lớp/chủ đề, tên bank; link phân loại (research) hoặc lọc chưa phân loại (general), import, thêm, sửa, xóa theo quyền.
2. Ghi chú bank chung, overlay riêng và chế độ kiểm toán admin.
3. Tab phạm vi `all`, `common`, `mine`; admin đổi nhãn `mine` thành đóng góp riêng kiểm toán. Số liệu server tính từ toàn bộ tập được cấp quyền.
4. `components/bank_overview.html`: nhóm `<details>` dạng kiến thức; ma trận 4 mức × 3 hình thức; tổng câu và “sẵn sàng”; link ô ma trận chuyển filter và cuộn `#bank-results`.
5. Filter GET: `q`, `difficulty`, `grade`, `type`, `node_id`, `scope`, `per_page`; nút Lọc/Đặt lại.
6. Phân trang trước và sau danh sách: 25/50 câu, đầu/cuối và lân cận, trước/sau; query lọc được giữ. `page` được chặn trong khoảng hợp lệ.
7. Card câu hỏi tải phần xem trước; đáp án/lời giải/thiết lập chỉ tải khi mở chi tiết hoặc sửa.
8. Inline editor và modal thêm câu thủ công.

### Trạng thái và thao tác phải bao phủ

| Nhóm | Các trạng thái/điều kiện thực tế |
|---|---|
| Phạm vi | Tất cả được phép; câu chung; câu riêng của tôi; audit admin; nguồn legacy chưa xác định |
| Nội dung | Dữ kiện chung có/không; hình có/không; công thức/TikZ/bảng; nhãn lớp/source ID có/không; nội dung dài |
| Chi tiết | Thu gọn, đang tải, đã tải, lỗi mạng, hết phiên đăng nhập, bị thu hồi quyền, câu đã bị xóa; nút Thử lại |
| Loại câu | `single`, `true_false`, `short_answer`; nhánh hiển thị legacy `multiple_choice`, `essay` còn tồn tại, không đồng nghĩa cho phép tạo mới |
| Đáp án | Một đáp án đúng; bốn mệnh đề đúng/sai; nhiều đáp án ngắn phân cách `|`; dữ liệu cũ thiếu đáp án |
| Chỉnh sửa | Chờ tải chi tiết trước; xem trước công thức; hủy; lưu và tải lại view để tính filter/thống kê; lỗi lưu dùng `alert()` |
| Đổi đáp án nhanh | Nút đáp án trên chế độ xem gọi API ngay; chỉ người có `can_edit` cấp câu được thao tác |
| Xóa câu | Xác nhận `confirm()`; POST rồi tải lại view để cập nhật thống kê |
| Thiết lập luyện tập | Chỉ câu research được sửa: difficulty band; ưu tiên 0–100; tạm ngừng dùng; submit giữ scope/page/filter |
| Rỗng | Không có nhóm kiến thức; không có câu phù hợp filter; tổng số câu khác số kết quả lọc |
| Hình | Phóng to bằng `FormulaRenderer.openImageLightbox`; ảnh xem có lazy load/async decode và Enter/Space |

“Sẵn sàng” không chỉ là đã phân loại: phụ thuộc nội dung, đáp án hợp lệ, teacher-confirmed, mức nhận thức và chưa bị loại luyện tập. Không thay bằng nhãn tổng số câu.

### Modal thêm thủ công

- ID hiện tại `add-question-modal`; mở/đóng qua thay `style.display`, không dùng dialog component.
- Form multipart: CSRF; giữ `scope`, `page`, `per_page`, `node_id`, từ khóa/type/difficulty/grade khi redirect.
- Trường: ID6 picker hoặc dạng general; dữ kiện; nội dung; file hình PNG/JPG/WebP tối đa 5 MB; đáp án động; lời giải.
- `single`: bốn phương án, một radio đúng. `true_false`: bốn phát biểu và đáp án; research còn có nhãn dạng/mức từng ý kế thừa câu. `short_answer`: mẫu `|`, chế độ số/văn bản, sai số 0–1.
- Trường khác loại bị `fieldset disabled` để không gửi dữ liệu lẫn nhau.
- Có preview nội dung/công thức tự lên lịch và nút preview thủ công; checkbox `reviewed=1` bắt buộc trước lưu.
- Route chặn trùng cùng nội dung; đáp án trùng khác nhau trả thông báo kiểm tra. Teacher thêm vào bank chung tạo câu riêng.
- Không tìm thấy khai báo `role=dialog`, `aria-modal`, focus trap/return focus hoặc Escape cho modal này. Đây là thiếu sót nhìn thấy trong code; chưa chạy bàn phím để kết luận đầy đủ.

### Hook cần bảo toàn hoặc chuyển đổi có kiểm thử

- `window.questionBankDetailConfig`: `questions`, `csrfToken`, `pageOffset`, `canEdit`, `canAdd`.
- `bankQuestionsManager`, per-row `can_edit`, `can_delete`, `source`, `source_label`, `detail_url`; không thay quyền bằng một boolean toàn bank.
- `data-bank-lazy-formulas`, `.katex-render`, `[data-latex-answer]`, `[data-manual-preview]`; `BankFormulaScheduler` ưu tiên viewport/idle, dọn block đã tháo và phục hồi bfcache.
- ID `qcard-<id>`, `qdetail-<id>`, `bank-results`; đối chiếu import liên kết `#qcard-<id>`, ma trận/phân trang dùng `#bank-results`.
- `.inline-edit-card`, `.question-editor`, `questionBankDetailConfig`, `ID6_CATALOG`, `id6Picker`, `scheduleManualPreview`, `previewManualQuestion`, `renderFormulas`, `toEditableLatex`.
- Thuộc tính `aria-expanded`, `aria-controls`, `aria-busy`, `role=status/alert` ở tải chi tiết cần giữ chức năng khi đổi markup.

### Yêu cầu thiết kế

- Tách cấu trúc tìm/lọc và độ phủ khỏi vùng đọc; tránh ma trận và các toolbar đẩy danh sách quá sâu. Bảo toàn liên kết ô ma trận đến đúng nhóm câu.
- Dùng bề mặt trắng, chữ/công thức dễ đọc, vùng đáp án/lời giải có phân cấp và không trang trí viền dày cho mọi card.
- Hiển thị nguồn, quyền thao tác và mức nhận thức đủ rõ; hạn chế badge lặp.
- Thiết kế cả general và research; tạo/sửa câu là không gian soạn nội dung phù hợp câu toán dài, không chỉ thu nhỏ modal hiện tại.
- Trạng thái async phải hiển thị gần thao tác, ngăn lưu lặp và có phục hồi lỗi; không đánh đồng chi tiết chưa tải với câu thiếu đáp án.
- Nhóm ngân hàng hiện tại **chưa có chọn nhiều câu để tạo đề ngay tại trang detail**. Nghiệp vụ chọn từ bank nằm ở `assessment_from_bank.html` do báo cáo kiểm tra phụ trách; không mô tả bulk chọn trong detail là chức năng hiện có.

## 6. BANK-04 — Wizard nhập học liệu LaTeX

### Luồng đã quan sát

| Bước | Nội dung/trạng thái |
|---|---|
| 1. Tải file | Chọn mục đích auto/assessment; kéo thả/chọn `.tex/.latex`; hướng dẫn, tải ba profile mẫu; bank đích có thể nhận từ `?bank_id=` |
| 2. Đọc tài liệu | Spinner, tên file, thanh tiến trình cố định `75%`; đây không phải phần trăm xử lý thật |
| 3. Kiểm tra | Nội dung câu, thống kê/dò trùng, filter trạng thái nội dung, hình thức, mức độ; sửa inline; xóa khỏi phiên; chỉnh đáp án ngay; đối chiếu; đổi đích và dò lại |
| 4. Duyệt và lưu | Tổng câu đủ điều kiện, ý nghĩa xác nhận đã duyệt; đích hiện có chỉ đọc; hoặc nhập tên/môn/lớp bank mới; quay lại; đang lưu |
| 5. Kết quả | Số thêm/cập nhật/bỏ trùng/cần đối chiếu/lỗi; bảng từng câu; hoàn thành hoặc tiếp tục đối chiếu phần còn lại; link bank/nhập file khác |

- Đề `ex` không phân dạng hoặc chọn mục đích assessment có thể redirect sang `assessment_import`; đây là ranh giới giữa import bank và import đề, phải rõ trong thiết kế.
- URL lưu `session_id` qua `history.replaceState`; tải lại có thể khôi phục preview/kết quả qua GET preview. Không được làm mất resume khi thay wizard.
- Nhận mặc định `node_id`, `difficulty`, `type` từ ô ma trận; upload hiện chỉ truyền node/difficulty, loại câu phải giữ cấu trúc parse, không ép đổi loại theo cell.
- Parser có thể đưa mode general nhiều lớp/chủ đề; header preview thay theo `scope.mode`.
- Câu preview có trạng thái nội dung `valid/warning/error`, trạng thái phân loại gợi ý/cần kiểm tra và trạng thái trùng riêng. Đây là ba chiều khác nhau.
- Sửa inline gồm dữ kiện, nội dung, loại câu/mức/dạng, đáp án, hình URL, lời giải, rule chấm và metadata từng ý; chuyển loại có bản nháp đáp án riêng trong picker.
- `.tex/.latex` được kiểm tra extension ở client; template ghi 10 MB nhưng JS upload không tự chặn dung lượng. Backend mới quyết định hợp lệ.

### Đối chiếu trùng và phạm vi

- `components/import_duplicates.html`: filter tất cả/mới/trùng/cần đối chiếu; số lượng từ `duplicateReport` server.
- Dialog hai bản hiển thị dữ kiện, hình, câu, đáp án, lời giải, nguyên nhân so sánh; tải file nguồn; mở câu gốc.
- Quyết định: giữ trái (`incoming`, nếu được thay thế), giữ phải (`duplicate`), giữ cả hai (`different`), bỏ cả hai (`neither`, chỉ khi hai bản đều trong file).
- Cảnh báo xung đột đáp án, thiếu đáp án, đề xuất giữ bản có lời giải; lưu quyết định có disabled và lỗi.
- Đổi bank đích gọi rescan, khóa khi đã lưu một phần; thay đích làm mất quyết định cũ. Confirmation gửi `confirmation_token=duplicateReport.revision` để server kiểm tra lại.
- Admin kiểm toán không đồng nghĩa được đưa mọi private overlay vào dò trùng. Dữ liệu đối chiếu do service lọc theo người nhập và đích.
- Lưu có thể một phần; receipt và replay không thêm lại câu đã lưu. Xóa câu khỏi preview khác xóa câu đã lưu trong bank.
- Dialog có `role=dialog`, `aria-modal`, đóng bằng Escape/click backdrop; chưa tìm thấy quản lý focus trap/return focus trong mã đối chiếu.

### Hook và API

- `window.importWizardConfig`: `defaults`, `uploadUrl`, `bankListUrl`, `csrfToken`; `IMPORT_CSRF`, `currentImportSessionId`, `ID6_CATALOG`.
- `importWizard`, `importScopeState`, `importDuplicateState` hợp nhất bằng `Object.defineProperties`; thứ tự tải helper trước module quan trọng.
- `x-ref=fileInput`, `#document-purpose`, `.inline-edit-container`, `qcard-<index>`, `.duplicate-comparison`, `.duplicate-*`, `.scope-*`, `.import-*`.
- Session API dưới `/question-banks/import/<session_id>`: `GET preview`, `GET source`, `POST update/scope/remove/destination/duplicate-decision/confirm/cancel`, `POST formulas/<formula_id>/retry`.
- Upload: `POST /question-banks/import/upload`; tải mẫu: `GET /question-banks/import/template/latex` với `profile=general/assessment` hoặc mặc định.
- Các mutation đều CSRF, session thuộc người hiện tại và kiểm tra lại quyền target; sau bị thu hồi quyền vẫn có thể hủy để cleanup. `source` chỉ cho file trong thư mục temp của phiên đang mở.
- Error hiện tại nhiều nơi dùng `alert`; một số fetch restore/update/save chưa có catch/toàn bộ lỗi hiển thị trong trang. `duplicateError` là lỗi inline riêng.

### Yêu cầu thiết kế

- Giữ quy trình năm bước, làm rõ tự nhận diện tài liệu và đích ghi trước lưu; trạng thái xử lý dùng indeterminate nếu không có tiến độ thật.
- Có tổng quan đúng về nội dung lỗi/cần xem, trùng, gợi ý phân loại và khả năng lưu; không dùng một màu/trạng thái duy nhất thay cả ba.
- So sánh hai bản phải đọc được câu dài/công thức ở desktop; mobile có cấu trúc xếp dọc, giữ nhãn “đang nhập”/“hiện có” để tránh chọn sai.
- Thể hiện rõ kết quả lưu một phần, nút tiếp tục review và những câu đã lưu; giữ token/revision, resume session và policy quyền.
- Chuyển editor/preview sang thành phần dùng chung nếu phù hợp, tránh tiếp tục sao chép khối đáp án và lời giải giữa import/detail/assessment.

## 7. BANK-05 — Duyệt nhãn kiến thức

- Bốn số liệu: tổng, đã phân loại, chưa phân loại, gợi ý chờ duyệt.
- Filter: `q`, trạng thái `all/unclassified/classified/suggested/needs_review/teacher_confirmed`, `node_id`. Dạng trong select giới hạn Toán 9 C8-i dù route lấy node active rộng hơn.
- Route chỉ lấy **tối đa 500 câu**, chưa có phân trang; select-all chỉ chọn câu đang hiển thị.
- Form `#classification-form`, CSRF; `#select-all`, `.question-checkbox`, `question_ids`.
- Hai bulk action: gán tay với picker (`POST .../classification/bulk`) hoặc xác nhận suggestion (`POST .../classification/accept-suggestions`).
- Bulk gán tay yêu cầu mức/loại D/T/S hợp lệ; các câu phải cùng hình thức đã chọn, không được chuyển dạng đáp án hàng loạt. Gán curriculum và khóa nhãn teacher-confirmed.
- Xác nhận gợi ý chỉ áp dụng fingerprint còn đúng, node active, mức đúng; stale bị bỏ qua và flash cảnh báo. UI có rationale và trạng thái stale, source_labeled, needs_review, teacher_confirmed.
- Card câu có ID, loại, source ID, trạng thái phân loại, nội dung, hình, đường dẫn chương→bài→dạng. Không có xem đáp án/lời giải chi tiết tại màn hình này.
- Rỗng: không có câu phù hợp. Kết quả bulk là redirect+flash. Không có spinner, modal, số đã chọn live hoặc mixed-state select-all.

Yêu cầu thiết kế: hàng/câu dễ quét và mở nội dung; thanh thao tác theo selection; giải thích rõ giới hạn “chọn đang hiển thị”; phân biệt nhãn file/gợi ý/đã khóa/stale; giữ hạn chế loại câu. Nếu bổ sung phân trang cần backend/query và kiểm thử, không chỉ sửa CSS. Không mở quyền bulk vào bank chung cho teacher bằng thay điều kiện template.

## 8. BANK-06 — Cổng đánh giá phân loại

- Bước 1 tải gói nhãn độc lập từ `GET .../classification/evaluation/export`; chỉ các câu khối 9, chương 8, bài i được phép xem. `build_blinded_rows` loại đáp án, lời giải, dự đoán.
- Bước 2 upload `labels_file` `.json`, tối đa 5 MB, phải là mảng JSON; lỗi được render trong form cùng trang.
- Sau POST có/không report. Report đạt/chưa đạt; nhãn hợp lệ, độ phủ tự gán, đúng cặp dạng–mức độ, nhóm nội dung lặp, số dòng invalid.
- Copy hiện tại nêu cổng mặc định 240 nhãn, độ đúng 95%; đây không phải số liệu thực tế của bank.
- Chưa có chi tiết bảng lỗi, biểu đồ, loading async, modal, lọc report.

Yêu cầu thiết kế: trình bày thành luồng tạo nhãn → nạp nhãn → kết quả, tiêu chí và mẫu số minh bạch; kết quả đạt/chưa đạt có chữ và số, không chỉ màu. Không tự công bố sẵn sàng khi mẫu nhỏ; giữ tính blinded của gói xuất.

## 9. BANK-07 — Danh mục kiến thức

- Header hiện cố định Toán 9 Chương 8; mô tả thống kê/xác suất. Filter GET có `q`, hidden `grade=9`, `chapter=8`, checkbox `inactive=1`.
- Route không mặc định ép grade/chapter khi thiếu query, nên trang GET không query có thể hiển thị node ngoài phạm vi copy header; cần kiểm chứng dữ liệu trước khi quyết định thiết kế.
- Bảng: dạng/tên, mã canonical, active/inactive, advanced; tổng số node, empty row.
- Admin có `<details class=catalog-management>`: form thêm/cập nhật một dạng theo canonical code; form bulk paste 7 cột `|`/tab; flash kết quả và tối đa 10 lỗi, báo còn lỗi khác.
- Toggle `POST /curriculum/<node_id>/toggle`; admin-only, redirect có `inactive=1` khi vừa ngừng dùng.
- Template dùng điều kiện `admin/manager` cho UI quản lý, nhưng GET decorator chỉ cho teacher/admin và POST chỉ admin. Không có chứng cứ manager thực sự dùng được màn hình này.
- `GET /curriculum/id6-preview` là API read-only prefix nguồn; không phải UI tự sinh ID6 mới. Giới hạn C8-i, kiểm tra quyền nếu đọc câu đã lưu.

Yêu cầu thiết kế: bảng có ngữ cảnh lớp/chương đúng dữ liệu, tìm/lọc trạng thái rõ; quyền đọc và quản lý thống nhất backend; quản lý single/bulk có validation dễ hiểu. Việc mở rộng catalog/role là thay nghiệp vụ, không tự đưa vào redesign.

## 10. Bản đồ CSS, JS và thành phần

| Nguồn | Phạm vi/trách nhiệm quan sát |
|---|---|
| `templates/base.html` | Tải `main.css`, `learning.css`, `question-document.css`, sau block head tải `neo-pop.css`; block scripts của từng trang được tải phía dưới |
| `static/css/main.css` | Thành phần nền tảng form/card/table/button/page-header; không có stylesheet riêng bank-list ở đây |
| `static/css/neo-pop.css` | Nắm gần như toàn bộ `.bank-list-*`, phủ card, knowledge group, matrix, manual help, question card; có `!important` |
| `static/css/question-bank.css` | Chỉ detail tải; overview/knowledge matrix, kết quả, pagination, page size, loading/error chi tiết. File vừa có rule giản lược question-card vừa có phần pagination viền đậm/bóng cứng |
| `static/css/id6.css` | Picker; detail/import/classification tải |
| `static/css/import_duplicates.css` | Toolbar, bảng, dialog và responsive import; import bank tải, có consumer ngoài nhóm cần kiểm tra trước xóa |
| `static/css/import_scope.css` | Scope selector và các lớp bước import; được import bank tải dù template scope riêng không được include hiện tại. `.import-filter-bar` nằm trong `question-document.css` |
| `static/css/question-document.css` | Dùng chung câu hỏi/đáp án/lời giải/hình/công thức và editor với kiểm tra/luyện tập; không thể xóa theo phạm vi bank riêng |
| `static/js/modules/question_bank_detail.js` | State per-question, lazy detail, editor, đáp án nhanh, save/delete/reload |
| `static/js/bank_formula_scheduler.js` | Render công thức theo viewport/idle cho bank detail, không phải JS trang trí |
| `static/js/id6_picker.js` + macro `components/id6_picker.html` | Research/general, chuyển type có giữ draft, metadata nguồn chỉ đọc; không gọi API tự sinh ID |
| `static/js/manual_question.js` | Preview form thủ công, debounce/scheduling và validation liên quan |
| `static/js/modules/import_wizard.js` | Năm bước, upload, editor, confirm, resume; hợp nhất scope và duplicate state |
| `static/js/import_scope.js`, `static/js/import_duplicates.js` | Scope/restore session và dò trùng/đích/receipt |
| `static/js/formula_renderer.js` | Công thức/TikZ/bảng, lỗi/retry/image lightbox dùng nhiều màn hình; không được coi là giao diện cũ bỏ toàn bộ |
| Template inline | Rất nhiều `style=` cho grid, kích thước, màu, bo góc và modal; import có `<style>` định nghĩa step/spinner/btn-success/btn-danger |

Hướng dọn sau này: chuyển template/style sang hệ thống mới theo từng màn hình, gỡ rule cũ đã hết consumer; hợp nhất toàn bộ thành phần form/card/question display. Không giữ Neo Pop làm lớp override và cũng không giữ main.css chỉ vì gần phong cách mới.

## 11. Dấu hiệu cần kiểm chứng trước quyết định xóa/sửa

| Phát hiện tĩnh | Mức kết luận và việc cần làm |
|---|---|
| `components/import_scope.html` không được include trong template/route tìm thấy; helper JS/CSS vẫn được tải | Ứng viên template bỏ dùng. **Không kết luận toàn bộ `import_scope.js/css` chết**: `restoreImport` nằm trong helper và wizard đang gọi, CSS còn `.import-steps`/`.import-step` hoạt động |
| `filterGrade`, `availableGrades`, `renderTempFormulaPreview`, `formatRichText` trong import module không thấy hook gọi từ template hiện tại | Ứng viên member dư; cần kiểm tra consumer động/tests/toàn repo trước bỏ |
| `formatRichText` trong detail module không thấy hook gọi trong detail | Ứng viên dư; không xóa `renderFormulas`/renderer cùng lúc |
| Modal general dùng `:disabled="!question.curriculum_node_id"`, trong khi picker general đặt node null | Có khả năng khóa nút lưu general dù backend chấp nhận category. Phải tái hiện với general bank trên dữ liệu thử; chưa sửa trong Phase 1 |
| `edit_question_bank` dùng `dt.datetime.utcnow()` nhưng `routes/question_bank.py` không thấy import `dt` | Có khả năng lỗi POST sửa bank; không phải vấn đề theme. Kiểm chứng bằng test cô lập trước khi sửa ở phase được phép |
| Link mở câu gốc từ dialog dùng `#qcard-id` nhưng không kèm page/filter của câu gốc | Câu trên trang khác có thể không nằm trong DOM. Cần kiểm chứng và định nghĩa link đúng trong thiết kế, không đổi ID âm thầm |
| Catalog template có UI manager, route không cho manager; header C8 nhưng route GET không query không ép C8 | Sự không khớp quyền/ngữ cảnh trong code; giữ kiểm soát server, không nới quyền để làm UI khớp |
| Nhánh hiển thị legacy `multiple_choice`/`essay` tồn tại nhưng picker/service chỉ cho single/TF/short mới | Đây là compatibility đọc dữ liệu, **không phải dead code đã chứng minh** |
| Step 2 thanh tiến độ 75% cố định | Trạng thái minh họa, cần thay bằng indeterminate hoặc dữ liệu thật; không quảng bá là tiến độ thật |
| Các rule card/btn cùng lúc ở main/Neo Pop/question-bank/inline | Chồng style có chứng cứ; chỉ xóa khi consumer đã chuyển và kiểm tra visual/regression |

Không xóa tài nguyên câu hỏi, ảnh upload, SVG công thức hoặc file nguồn import chỉ vì chúng không được nhắc trực tiếp trong HTML: đường dẫn lấy từ dữ liệu động.

## 12. Kiểm thử hiện có và kế hoạch xác minh sau redesign

**Chỉ đã đọc test, chưa chạy trong Phase 1 này.** Một số bộ kiểm thử mang tên phase cũ có kỳ vọng trước khi có overlay; phải đối chiếu policy hiện tại, không dùng tên test làm bằng chứng hành vi runtime.

| Bộ kiểm thử | Hợp đồng liên quan |
|---|---|
| `tests/test_route_contract.py`, fixture routes | Endpoint/URL/method công khai; thay markup không được làm mất route |
| `tests/test_bank_visibility_phase1.py`, `test_bank_list_phase3.py` | Tách xem/dùng/sửa, bank shared/private/legacy, role, tạo scope server, list/read controls; có kỳ vọng cũ cần so với overlay |
| `tests/test_bank_import_phase2_visibility.py` | Danh sách đích và upload, kiểm tra lại quyền phiên/target, revoke/replay, scope bank mới |
| `tests/test_question_overlay_phase2.py`, `test_question_overlay_phase3.py` | Overlay riêng, actor-scoped duplicate, tab/count/facet, nhãn audit, serialized per-row permission |
| `tests/test_phase1_import_review.py`, `test_import_duplicates.py` | Sẵn sàng sau duyệt, suffix khi save, duplicate/answer conflict/near decision, đổi đích, partial save/replay, tải nguồn, cạnh tranh import |
| `tests/test_import_regression_guard.py`, `test_three_type_import.py`, `test_local_tex_bank.py`, `test_phase2_import.py`, `test_id6_import.py` | Định dạng TeX, parser, ba hình thức, curriculum/ID và pipeline tài nguyên |
| `tests/test_curriculum_classification.py`, `test_question_classification.py` | Catalog/classification render, bulk cùng loại, stale suggestion, ID, metadata/answers, ngân hàng khác bị chặn |
| `tests/test_classification_evaluation.py`, `test_evaluation_dataset.py` | Metric/gate, mẫu nhỏ, trùng và nhãn invalid, gói blinded |
| `tests/test_general_bank.py` | Bank general nhiều lớp/chủ đề, reimport, giữ ID khi thay lời giải |
| `tests/test_id6_picker.js`, `test_import_scope.js` | State picker/draft answers, scope/restore wizard không cần app |
| `tests/test_formulas.py`, `test_latex_display_v3.py` | Render/bảng/TikZ/ảnh/công thức; không phá nội dung toán khi đổi markup |

Checklist runtime cần chuẩn bị sau khi được duyệt triển khai:

1. Admin, teacher chủ bank, teacher thứ hai cùng bank chung, học sinh/role không được vào; có cả câu common/private/legacy unknown và bank inactive.
2. Bank rỗng/1 câu/26 câu/51 câu/nhiều dữ liệu; research và general; filter có/không kết quả; số đếm scope không đổi sai theo query.
3. Lazy details thành công/lỗi mạng/403/404/hết phiên; mở/đóng/sửa nhanh không ghép nhầm câu; pager giữ filter; MathJax chỉ render phần cần.
4. Thêm/sửa đủ ba hình thức, câu sai đáp án, dữ liệu dài, ảnh, công thức, bảng, lời giải; chấm số/văn bản và metadata từng ý.
5. Import từ bank/matrix, resume URL, đề chuyển assessment, file invalid/quá lớn, general/research, duplicate trong file/đã có/xung đột, thay đích, bị revoke, lưu một phần/tiếp tục/replay/hủy.
6. Bulk gán cùng loại/khác loại, không chọn, stale suggestion, node ngừng dùng; catalog đọc/quản lý và report labels invalid/mẫu nhỏ/đạt gate.
7. 375/768/1024/1440 px, nội dung dài; keyboard focus, nhãn control, thứ tự tab, modal trap/return focus/Escape, giảm chuyển động; không để sticky toolbar che focus.

## 13. Phạm vi chuyển giao sang phase tiếp theo

- Phase 2 phải có bản mẫu BANK-03 research/general, BANK-01, trạng thái soạn câu và luồng review import; kiểm tra quyền trên bản mẫu bằng chú thích.
- Phase 4 triển khai ngân hàng/câu hỏi/phân loại/catalog/evaluation; Phase 5 triển khai import và biên soạn đề theo kế hoạch chung. Các trang phụ có chủ sở hữu phase rõ, không để thành trang cũ bị sót.
- Phase 9 rà tham chiếu và xóa thành phần cũ sau khi toàn bộ consumer đã chuyển. Không xóa các hook nghiệp vụ/công thức chỉ vì chúng nằm trong file có giao diện cũ.

Tất cả yêu cầu bố cục/hành vi trình bày trong tài liệu là đầu vào thiết kế; Phase 1 chưa thay UI và chưa chốt thêm chức năng.
