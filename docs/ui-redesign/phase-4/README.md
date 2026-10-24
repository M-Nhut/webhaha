# Phase 4 · Ngân hàng câu hỏi và kiến thức

**Hoàn tất ngày 14/10/2026**, theo yêu cầu “hoàn thành phase 4”. Đã áp dụng Modern White Academy vào toàn bộ sáu màn hình S01–S06 của [đặc tả được duyệt](../phase-2-screen-specs.md), gồm các thành phần và tương tác liên quan. Phase 5–9 tiếp tục theo kế hoạch.

## Giao diện đã thay

| Màn hình | Thiết kế và hành vi |
|---|---|
| Danh sách ngân hàng | Hàng thấp với tên, môn/lớp, tổng câu và bốn mức gọn; teacher chia dùng chung/của tôi, admin thấy phạm vi/người tạo; nhập đúng bank theo `can_add`, sửa/xóa theo `can_edit` |
| Tạo/sửa ngân hàng | Form 760px, năm trường hiện tại, phạm vi chỉ đọc; nhãn/required/hint rõ, lỗi dẫn đến trường và giữ dữ liệu đang nhập, trạng thái đang lưu |
| Chi tiết ngân hàng | Tên và phạm vi gọn; filter ngay trước danh sách; câu chiếm vùng đọc chính, độ phủ 300px bên phải desktop và disclosure thu gọn trên tablet/mobile; giữ scope, filter và phân trang 25/50 câu |
| Soạn câu | Inline editor và dialog native 1080px; nội dung/hình → kiến thức/hình thức → đáp án → lời giải → preview/xác nhận/lưu; ba hình thức đầy đủ, inactive fieldsets không gửi lẫn dữ liệu |
| Duyệt nhãn | Tổng quan, filter, selection/count/mixed-state theo câu đang hiển thị; gán thủ công và xác nhận gợi ý là hai form riêng; chặn mixed types, câu không được sửa và gợi ý stale |
| Đánh giá phân loại | Xuất gói nhãn độc lập → upload JSON 5 MB → kết quả và tiêu chí; `None` hiển thị “Chưa đủ dữ liệu”, không biến thiếu dữ liệu thành độ đúng 0 hoặc đạt chất lượng |
| Danh mục kiến thức | Context từ dữ liệu/query, filter trước kết quả, bảng desktop/card mobile; teacher chỉ đọc, admin single/bulk/toggle; chỉ biên tập phạm vi backend hỗ trợ 9/8/i/mã1–8 |

General dùng tên dạng tự đặt và không bị buộc chọn curriculum node nghiên cứu. Research giữ tám dạng và nhãn riêng cho bốn ý Đúng/Sai. Bank chung vẫn cho teacher bổ sung câu riêng nhưng câu chung chỉ đọc; câu riêng của giáo viên khác không lọt vào HTML/JSON/count của teacher. Admin dùng nhãn kiểm toán phù hợp.

Đáp án/lời giải vẫn lazy load, có busy/error/retry và phản hồi khi hết phiên/mất quyền/câu bị xóa. Cập nhật đáp án thất bại giữ key cũ; lưu editor thất bại giữ bản nhập và cho thử lại. Thao tác gửi lặp được chặn. Công thức, bảng toán, ảnh/zoom và dữ liệu câu cũ vẫn đọc được; các loại cũ không được dùng làm loại tạo mới.

## Mã cũ đã dọn

- **223 thuộc tính `style=`** được bỏ khỏi sáu template trang; không còn khối CSS inline hoặc event `onclick`/`onsubmit` cũ trong nhóm này. Alpine vẫn quản lý trạng thái hiển thị và dữ liệu; cấu hình JSON server vẫn dùng `tojson` an toàn.
- `question-bank.css` và `id6.css` được viết lại theo semantic token hiện tại. Không thêm theme mới bên trên theme cũ.
- Xóa **39 selector bank/catalog cũ** trong `question-document.css`, các rule bank trong bridge `pages/workspaces.css` và CSS preview ID6 hết consumer.
- Rule editor còn phục vụ import được giới hạn để không ghi đè editor bank mới. CSS toán/import/exam/learning còn consumer tiếp tục dùng cho đến phase tương ứng.
- Thêm CSS trang riêng `pages/bank-list.css`, `bank-form.css`, `knowledge.css`; JS tương tác riêng và tiện ích dialog dùng chung. Bump asset version để tránh giữ style cũ trong cache.

Không giữ bản template/CSS cũ làm backup runtime. Số file xóa nguyên file ở phase này là 0 vì các file đang dùng đã được thay hoặc cắt đúng phần hết consumer; theme Neo Pop đã xóa ở Phase 3. Không xóa code MathJax, formula scheduler, policy hoặc upload còn dùng.

## Sửa lỗi để các luồng hoạt động

1. Lưu sửa bank thiếu import `datetime`: đã sửa; create/edit kiểm tra required/độ dài theo schema, trả lại form với bản nhập và lỗi trước khi thay DB.
2. JSON nhãn sai shape từng dòng/question/scope/answers/labels có thể gây 500: kiểm tra shape ở boundary và hiển thị lỗi file; giới hạn 5 MB, bộ phân loại và gate giữ nguyên.
3. Gán nhãn thủ công thiếu fingerprint nên trang kế tiếp coi nhãn vừa lưu là stale: lưu fingerprint hiện tại cùng xác nhận.
4. Tên bài readonly ở catalog lệch dấu chấm so với validator: lấy trực tiếp `RETAINED_LESSON_NAME` từ backend cho field và mẫu bulk, chuẩn hóa khi sửa dữ liệu cũ.
5. Đổi đáp án Đúng/Sai gọi hàm chưa tồn tại, general save bị buộc node, draft đáp án ngắn mất dấu phân cách và dialog mobile bị overflow: đã sửa trong phần giao diện/tương tác.

Backend chỉ thay `routes/question_bank.py` và context hiển thị ở `routes/curriculum.py`. Không đổi URL/API, quyền, gate, scoring, models hoặc service phân loại.

## Kiểm chứng

| Bộ kiểm tra | Kết quả |
|---|---|
| Python tích hợp/regression liên quan | **60 đạt**: 25 case Phase 4 với CSRF, bank visibility/overlay, evaluation và regression Phase 3/errors |
| End-to-end browser | **170/170 đạt**; POST thật sửa câu, thêm general ba loại, overlay chung, research TF, gán/duyệt nhãn, upload/report, create/edit/delete bank và catalog single/bulk/toggle |
| Browser bổ sung chỉ đọc | **122/122 đạt**: list24, knowledge39, detail39, research20; gồm keyboard, lỗi mạng/403, giữ draft/key, selection và fieldsets |
| JavaScript state | **42 assertions đạt**: bank manager24, picker ID6 readonly18 |
| Capture/visual QA | **138/138 đạt**, ảnh desktop/mobile, font/icon local, không overflow; MathJax render đầy đủ khi chụp và khi câu vào viewport |
| Tĩnh/phạm vi | 52 template parse được, JS syntax/CSS parse đạt, không CSS variable thiếu; sáu trang đều 0 inline style; metadata DB thật giữ nguyên |

Viewport 375/768/1024/1440px cho list/form/general/research/classification/evaluation/catalog, cùng các trạng thái bank chung, rỗng, no-match, lỗi upload, report và admin catalog. Đã xem ảnh và sửa các lỗi bố cục/field height/overflow/focus phát hiện trong quá trình kiểm tra. Không có browser JS exception hoặc request font/script ngoài localhost trong phiên QA cuối.

Các tests UI cũ được đổi từ assertion bám câu chữ/Unicode HTML sang payload nguồn, quyền và count thật. Fixture evaluation C6 đổi sang C8 hiện được hỗ trợ, giữ các assertion độ đúng/duplicate/gate. Test picker cũ mong sinh ID/gọi API được chuyển sang contract readonly đã có từ trước; runtime `id6_picker.js` không đổi. Test manual overlay bổ sung xác nhận reviewed đúng form hiện tại.

**Mốc Phase 4 — một test import cũ ngoài phạm vi chưa đạt:** `test_import_stamps_teacher_overlay_and_admin_private_destination_owner` báo không có câu hợp lệ để lưu. Đã tái hiện bằng routes/template snapshot trước Phase 4 trong DB tạm; không làm yếu policy hoặc validator để ép test đạt. Luồng import và fixture review/confirmation này thuộc Phase 5. Không tuyên bố toàn bộ test suite của dự án đạt. **Cập nhật 15/10/2026:** fixture source T và bước materialize metadata đã được sửa theo pipeline hiện tại; test này đạt trong [Phase 5](../phase-5/README.md).

Bằng chứng: [browser-qa.json](browser-qa.json), [capture-qa.json](capture-qa.json), [bank-list-qa.json](bank-list-qa.json), [knowledge-qa.json](knowledge-qa.json), [bank-detail-qa.json](bank-detail-qa.json), [research-qa.json](research-qa.json), [integrity-qa.json](integrity-qa.json). Harness bổ sung nằm trong [qa](qa/), không tải vào ứng dụng.

## Xem và chạy lại

```bash
python3 scripts/preview_ui_phase4.py --port 8766
```

[Mở bản xem](http://127.0.0.1:8766/login). `qa_teacher`, `qa_admin`, `qa_student`; mật khẩu `Academy123!`. Bank1 chung/research, bank2 general, bank3 research/duyệt nhãn, bank4 inactive, bank5 thuộc teacher khác, bank6 rỗng.

Preview bypass dotenv trước import Flask, dùng SQLite memory, app root và mọi storage mutation ở thư mục tạm; collector orphan ảnh của preview được vô hiệu vì đường dẫn legacy của nó trỏ tới kho thật. Không đọc/chỉnh dữ liệu học sinh, avatar, hình hoặc khóa provider thật. Dừng server là mất dữ liệu giả.

```bash
python3 -m pytest tests/test_ui_redesign_phase4.py tests/test_bank_list_phase3.py tests/test_question_overlay_phase3.py tests/test_evaluation_dataset.py tests/test_classification_evaluation.py tests/test_question_overlay_phase2.py tests/test_ui_redesign_phase3.py tests/test_error_pages.py -k "not test_import_stamps_teacher_overlay_and_admin_private_destination_owner" -q
node tests/test_id6_picker.js
node docs/ui-redesign/phase-4/qa/qa-bank-state.cjs
PLAYWRIGHT_MODULE=/path/to/playwright node scripts/qa_ui_phase4.cjs
```

Browser QA dùng Chrome/Playwright đã có, chỉ chạy với server preview dữ liệu giả. `PHASE4_CAPTURE_ONLY=1` chụp/kiểm tra bố cục mà không gửi POST mutation. Harness readonly trong `qa/` có thể chạy riêng; kết quả phụ của chúng ghi vào `/tmp`.

## Ảnh

| Trang | Desktop | Mobile |
|---|---|---|
| Danh sách bank | [1440px](screenshots/bank-list-1440.png) | [375px](screenshots/bank-list-375.png) |
| Form bank | [1440px](screenshots/bank-form-1440.png) | [375px](screenshots/bank-form-375.png) |
| General | [1440px](screenshots/bank-general-1440.png) | [375px](screenshots/bank-general-375.png) |
| Research | [1440px](screenshots/bank-research-1440.png) | [375px](screenshots/bank-research-375.png) |
| Thêm câu | [1440px](screenshots/question-dialog-1440.png) | [375px](screenshots/question-dialog-375.png) |
| Duyệt nhãn | [1440px](screenshots/classification-1440.png) | [375px](screenshots/classification-375.png) |
| Evaluation | [1440px](screenshots/evaluation-1440.png) | [375px](screenshots/evaluation-375.png) |
| Catalog teacher | [1440px](screenshots/catalog-teacher-1440.png) | [375px](screenshots/catalog-teacher-375.png) |
| Catalog admin | [1440px](screenshots/catalog-admin-1440.png) | [375px](screenshots/catalog-admin-375.png) |

Ảnh bank chung/rỗng/no-match, lỗi upload và report ở [screenshots](screenshots/). Phase tiếp theo là **Phase 5: wizard nhập LaTeX, đối chiếu trùng/receipt và biên soạn đề** theo đặc tả đã duyệt.
