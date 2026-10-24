# Phase 5 · Nhập học liệu và biên soạn đề

**Hoàn tất ngày 15/10/2026** theo yêu cầu “hoàn thành phase 5”. Phạm vi là S07–S09 trong [đặc tả được duyệt](../phase-2-screen-specs.md): wizard LaTeX, đối chiếu trùng/receipt/resume, chọn câu từ ngân hàng và biên soạn đề kiểm tra. Áp dụng skill UI/UX Pro Max và hệ thống Modern White Academy đã duyệt.

## Giao diện và tương tác

- **Nhập LaTeX:** năm bước Tải file → Đọc tài liệu → Kiểm tra → Duyệt và lưu → Kết quả; đọc file có trạng thái chờ, không mô phỏng phần trăm xử lý. Tên tài liệu, đích, phạm vi và mục đích luôn rõ. Mẫu research/general/assessment, lỗi file, bộ lọc, sửa ba loại câu, preview, xác nhận duyệt và hủy phiên đều dùng thiết kế mới.
- **Đối chiếu:** dialog native “Đang nhập / Hiện có”, hai cột desktop và xếp dọc mobile; nội dung, đáp án, lời giải, công thức riêng từng bản, ảnh và thử lại. Quyết định đúng quyền, lỗi token 400/409 có tải lại; đổi đích cần xác nhận và dò lại. Câu đã lưu được khóa trong phiên. Liên kết câu gốc mở đúng trang ngân hàng và đưa focus tới câu.
- **Receipt/resume:** số thêm/cập nhật/bỏ trùng/cần đối chiếu/lỗi và kết quả từng câu; có thể tiếp tục phần chưa lưu. Nhập lại không tạo bản sao hoặc cấp lại danh tính cho câu đã lưu. Phiên đề LaTeX chuyển sang editor, không hiển thị receipt nhập ngân hàng.
- **Chọn câu:** lớp và nguồn trước danh sách; chọn thủ công hoặc quota ngẫu nhiên cho ba hình thức. Sidebar cấu trúc hiển thị số câu, điểm từng phần và tổng 10; chuyển mode giữ lựa chọn, phần không dùng được vô hiệu hóa. Nguồn thể hiện quyền từng câu và các trường thực tế được gửi khi tạo nháp.
- **Editor:** thông tin đề, cấu trúc điểm, preview câu 18px và disclosure chỉnh nội dung/đáp án/nhãn/trọng số/lời giải. Trọng số và điểm phân bổ có nhãn riêng. Lưu báo chưa lưu/đang lưu/đã lưu/lỗi, lỗi giữ DOM nhập liệu; giao đề yêu cầu reviewed và dialog xác nhận lớp, thời gian, số câu, thang 10 và khóa nội dung.

Responsive kiểm tra ở **375, 768, 1024, 1440px**. Dùng cùng font, token, control, renderer công thức và ID6 picker đã triển khai; không thêm framework hoặc bộ theme thứ hai.

## Dọn giao diện cũ

- **160** khai báo `style=` đã được gỡ khỏi bốn template Phase 5; còn **0** style trực tiếp, CSS inline và handler DOM cũ trong nguồn các template này. Alpine có thể tạo style động cho `x-show` khi chạy.
- **67** selector cũ của import/dialog/editor đã được cắt khỏi `question-document.css`; gỡ CSS editor cũ trong `assessments.css`, giữ phần ma trận còn dùng ở Phase 6.
- Xóa `components/import_scope.html` và `import_scope.css` sau khi xác nhận không có include runtime. `import_scope.js` giữ duy nhất phần khôi phục phiên còn dùng; bỏ các state/hàm của form phạm vi đã ngừng sử dụng.
- Viết lại các module wizard, duplicate và editor; bỏ helper không có consumer, alert/confirm cũ và CSS backup. `main.css` vẫn là nền tảng chung; CSS trang nằm trong `pages/import-wizard.css`, `pages/assessment-composer.css` và `import_duplicates.css`.

Các giao diện còn có consumer ở Phase 6–8 được giữ để chuyển theo kế hoạch; không xóa code toán, ảnh, quyền hoặc transaction đang hoạt động.

## Sửa chức năng tối thiểu và giới hạn

1. Lỗi thiếu đáp án của câu general khi lưu một phần được giữ qua resume cho tới khi giáo viên sửa câu; không hạ điều kiện đủ đáp án.
2. Update/confirm không bắt lỗi HTTP ownership/missing-session rồi chuyển thành 400/500: giữ 404 của phiên ngoài quyền/đã hủy.
3. Link câu gốc bổ sung `question_id` để chọn trang bằng truy vấn chỉ ID đã lọc quyền và thứ tự hiện có. ID không được phép không làm lộ câu hoặc đổi quyền.
4. S08 nhận nhãn nguồn từng câu từ policy hiện có. Không thay resolver nguồn lớp, scoring, quota, identity, quyền thay thế, revision/token, transaction/replay hoặc khóa đề đã giao.

Test import còn lỗi từ Phase 4 đã được xử lý ở fixture: mã trắc nghiệm dùng **T** đúng chuẩn hiện tại, và fixture materialize metadata từ nguồn trước khi validate scope giống luồng upload thật. Không sửa validator để chấp nhận thiếu dạng kiến thức. Test ownership này hiện đạt, đồng thời có kiểm tra upload và overlay thực tế trong bộ Phase 5.

## Kiểm chứng

| Phạm vi | Kết quả |
|---|---|
| Python tích hợp/regression | **111 đạt**: 28 case Phase 5 cùng overlay, ngân hàng general, standalone, scoring/matrix và hồi quy Phase 3–4/errors |
| POST trình duyệt đầy đủ | **138 đạt**: upload/update/confirm, receipt/resume/partial, đối chiếu/đổi đích, manual/auto tạo nháp, lỗi lưu giữ DOM, lưu thật và giao đề; không lỗi JavaScript/asset hoặc tải script/font/CSS ngoài localhost |
| Ảnh cuối trên bản thử sạch | **109 kiểm tra đạt**, chỉ đọc các màn hình và giữ các phiên mẫu để người dùng xem |
| Wizard kiểm tra trình duyệt riêng | **74 đạt**, giữ draft khi request lỗi và đủ bốn kích thước |
| Đối chiếu kiểm tra trình duyệt riêng | **44 đạt**, native modal/quyền/đổi đích/keyboard |
| Đóng/mở editor qua lưu thành công/lỗi/hủy | **22 đạt**, không lỗi teardown Alpine |
| Đóng/đổi đích/tải lại dialog đối chiếu | **7 đạt**, gồm destination POST thật trên phiên giả; không lỗi teardown |
| Chọn câu/editor kiểm tra trình duyệt riêng | **49 đạt**, mode/quota, ba loại đáp án, preview/lỗi/lưu/xác nhận |
| Trạng thái JavaScript | Resume/CSRF/cancel **27**, wizard **29**, duplicates **41**, ID6 **18**, bank **24** assertion đạt |
| Kiểm tra tĩnh | **51** template parse; CSS parse và token trang không lỗi; JS/Python syntax được kiểm tra |

Vòng POST trình duyệt đầy đủ và **22 ảnh** được ghi ở [browser-qa.json](browser-qa.json); [capture-qa.json](capture-qa.json) ghi vòng chụp cuối sau khi khởi tạo lại dữ liệu thử sạch. Các harness và báo cáo nằm trong [qa](qa/), [duplicates-qa.json](duplicates-qa.json), [duplicate-teardown-qa.json](duplicate-teardown-qa.json). [Kiểm tra tính toàn vẹn](integrity-qa.json) xác nhận metadata DB thật, FormulaRenderer và ID6 picker không thay đổi. Không tuyên bố toàn bộ test suite lịch sử của dự án đã chạy hoặc đạt.

Lệnh kiểm tra chính:

```sh
python3 -m pytest tests/test_ui_redesign_phase5.py tests/test_question_overlay_phase2.py tests/test_standalone_assessment.py tests/test_general_bank.py tests/test_assessment_scoring.py tests/test_assessment_matrix.py tests/test_ui_redesign_phase4.py tests/test_ui_redesign_phase3.py tests/test_error_pages.py --tb=short --disable-warnings -q
PLAYWRIGHT_MODULE=/path/to/playwright node scripts/qa_ui_phase5.cjs
```

Ứng dụng thử dùng SQLite trong bộ nhớ; môi trường local được bỏ qua trước import app. Upload/source/ảnh/render và đường dẫn ứng dụng dùng thư mục tạm, chỉ sao chép ba mẫu TeX công khai. Không dùng DB, tài khoản, bài làm hoặc khóa AI thật. `preview_ui_phase5.py` chạy riêng tại localhost, không thêm QA route vào ứng dụng sản phẩm.

## Ảnh và bản thử

- [Wizard desktop](screenshots/import-general-1440.png) · [mobile](screenshots/import-general-375.png)
- [Đối chiếu desktop](screenshots/duplicate-dialog-1440.png) · [mobile](screenshots/duplicate-dialog-375.png)
- [Chọn câu desktop](screenshots/bank-selection-1440.png) · [mobile](screenshots/bank-selection-375.png)
- [Editor desktop](screenshots/editor-latex-1440.png) · [mobile](screenshots/editor-latex-375.png)
- [Kết quả nhập một phần](screenshots/import-partial-1440.png) · [Lỗi lưu giữ nội dung](screenshots/editor-save-error-1440.png)
- [Xác nhận giao đề desktop](screenshots/publish-confirm-1440.png) · [mobile](screenshots/publish-confirm-375.png)

```sh
python3 scripts/preview_ui_phase5.py --port 8767
```

Tài khoản minh họa `qa_teacher`, `qa_admin`, `qa_student`; mật khẩu `Academy123!`. Phase tiếp theo là **Phase 6: quản lý đề, ma trận, làm bài và kết quả standalone** theo kế hoạch đã duyệt.
