# Phase 9 — Dọn giao diện và nghiệm thu toàn hệ thống

Hoàn tất phần giao diện ngày **19/10/2026** theo Modern White Academy đã duyệt. Phase 3–9 đã chuyển toàn bộ **32 template trang đang hoạt động**, cùng shell, component và trang lỗi. Không giữ theme cũ làm lớp ghi đè hoặc một bản giao diện dự phòng trong runtime.

## Kết quả chính

| Phạm vi | Kết quả |
|---|---|
| Template | 49/49 có consumer: 32 trang, 10 component, 6 template lỗi và 1 base; không có include/asset literal bị thiếu |
| CSS/JS | 31 CSS parse được, 32 JS kiểm tra cú pháp đạt; không có token CSS chưa định nghĩa |
| Trình duyệt | **932 kiểm tra đạt**: 758 toàn giao diện, 86 công thức/ảnh, 88 kiểm tra chốt sau sửa; 0 lỗi JS, asset thiếu hoặc tràn trang trong các lượt đạt |
| Thiết bị/tương tác | 375/768/1024/1440px, reduced motion, 140 trường hợp trang, bàn phím/drawer/dialog, bảng cuộn, công thức, trạng thái lỗi |
| Ma trận | Excel Open XML hợp lệ; bản in A4 ngang được xem lại, sửa trang gần trắng do một dòng chú thích bị tách, từ 3 còn 2 trang ở fixture nghiệm thu |
| Contract hiện tại | 94 route khớp fixture; 39 test + 3 subtest của nhóm AI/report/route đạt sau bảo trì fixture |
| Toàn bộ pytest | 59 module đầu vào: **445 test + 33 subtest đạt, 75 test lỗi, 1 lỗi collection**; không có failure hoặc collection error mới so với trước Phase 9 |
| Dữ liệu/tài nguyên | 84 file Python backend và 52 tài nguyên brand/font/vendor/TeX khớp hash trước thay đổi; metadata DB thật không đổi |

[Kết quả tổng hợp](qa-summary.json) · [đồ thị consumer/integrity](integrity-qa.json) · [browser](browser-qa.json) · [kiểm tra chốt](final-browser-qa.json) · [công thức](cleanup-formula-browser.json).

## Đã dọn gì

- Xóa `teacher_analytics.html` không có route render; giữ alias `/analytics/teacher` chuyển hướng tới theo dõi học tập hiện hành.
- Xóa **37 alias token chuyển tiếp**, **20 tên class không còn consumer** và metadata Finder trong các thư mục UI. `main.css` chỉ nhập nền tảng mới.
- Xóa bốn script xuất HTML preview ad hoc đã bị thay thế và hai hướng dẫn theme/logo lỗi thời. README và hướng dẫn LaTeX trỏ tới preview hiện hành.
- Chuyển phần UI trong renderer công thức — lỗi, trạng thái cần kiểm tra, thử lại và phóng ảnh — sang CSS token. Hộp phóng ảnh dùng native dialog, có nút đóng, Tab/Shift+Tab, Escape, đóng bằng backdrop và trả focus. Các nhánh API, dữ liệu, kích thước nội dung toán và render vẫn được giữ.
- Sửa spacing chỉ trong bản in ma trận để hai đoạn chú thích ở cùng trang với bảng; giữ cảnh báo nhãn chưa xác nhận và toàn bộ cột dữ liệu.
- Cập nhật cache URL cho các tài nguyên đã đổi. Thêm `node scripts/build_local_assets.cjs --check` để xác minh 26 tài nguyên bắt buộc mà không tải thư viện, copy asset hoặc ghi đường dẫn Node.

Từng quyết định xóa/giữ có chứng cứ trong [cleanup UI](cleanup-ui.md), [inventory](cleanup-runtime-inventory.json) và [audit tài nguyên](assets-audit.md). Không xóa theo tên file đơn thuần: `import_scope.js`, class thông báo sinh động, ảnh/avatar tải lên, dữ liệu câu hỏi, công thức, thư viện MathJax/Chart.js/Alpine/Lucide và tài nguyên TeX vẫn có consumer hoặc URL tương thích cần giữ. Prototype thiết kế được duyệt và hồ sơ nghiệm thu Phase 1–8 là tài liệu tham chiếu; chúng không được nạp vào ứng dụng.

## Code giao diện sau bàn giao

Ứng dụng tiếp tục dùng Flask/Jinja và JavaScript hiện có. Một nguồn token cung cấp primitive → semantic → component; font Be Vietnam Pro và toàn bộ thư viện trình duyệt nằm tại máy.

```text
main.css
  tokens.css → base.css → components.css → shell.css → question-content.css

template block head → CSS trang/nhóm chức năng
learning.css        → ma trận kiến thức và bằng chứng dùng chung
question-document.css → bảng TeX
static/js/modules   → tương tác theo chức năng
formula_renderer.js → công thức, hình, retry và dialog phóng ảnh
```

Khi sửa tiếp, dùng token semantic và style có phạm vi; không thêm theme global hoặc khôi phục alias chuyển tiếp. Kiểm tra cả producer JS/Alpine, class sinh theo trạng thái và URL tài nguyên động trước khi xóa. Các style động phục vụ số đo/nội dung toán không bị xóa bằng regex.

## Kiểm thử còn lỗi trước Phase 9

Toàn bộ test được chạy trên cả snapshot trước thay đổi và nguồn hiện tại. Baseline có **419 test + 30 subtest đạt, 99 test lỗi, 1 lỗi collection**. Sau bảo trì contract, còn 75 failure thuộc 12 module; toàn bộ node và chữ ký lỗi đầu tiên đều khớp baseline. Không có failure mới; các bộ UI chuyên biệt Phase 3–8 đều đạt.

Không coi 75 failure này là đạt hoặc khẳng định chúng đều chỉ sai câu chữ. Chúng gồm fixture/phạm vi Chapter 6 cũ, migration/catalog, nhập/phân loại, học tập, quyền và hai assertion render trong bộ adaptive lịch sử. Lỗi collection là test nhập một CLI cleanup không tồn tại: `scripts.cleanup_math9_chapter6_lesson4`. Không khôi phục CLI dọn dữ liệu phá hủy hoặc sửa quy tắc nghiệp vụ để làm xanh test trong đợt dọn giao diện này.

[Đối chiếu đầy đủ trước/sau](regression-comparison.md) · [từng nhóm còn lỗi](baseline-failure-categories.json) · [log hiện tại](python-regression.log) · [JSON](python-regression.json) · [bảo trì contract](contracts-maintenance.md). Kết quả Phase 9 xác nhận giao diện và phạm vi thay đổi; bộ nghiệp vụ toàn dự án **chưa xanh hoàn toàn**.

## Chạy lại và xem thử

```sh
python3 scripts/preview_ui_phase9.py --port 8771
node scripts/build_local_assets.cjs --check
python3 scripts/qa_ui_phase9_integrity.py
python3 scripts/test_ui_redesign.py
```

Preview tại [127.0.0.1:8771/login](http://127.0.0.1:8771/login). Tài khoản `qa_admin`, `qa_teacher`, `qa_student`, `qa_resume`; mật khẩu `Academy123!`. Fixture có thêm trạng thái lớp, báo cáo, khóa và phiên nhập tại `/qa/fixture`. Preview/test runner dùng SQLite memory, storage tạm, khóa mã hóa mới và mock AI; không nạp dotenv, DB/upload hoặc khóa thật. Test runner chặn HTTP/socket, vẫn trả exit code lỗi cho các failure/collection error nêu trên.

Các công cụ QA cần môi trường có pytest, tinycss2 và Playwright/Chrome; đây là công cụ kiểm chứng, không phải thư viện runtime mới của web. Browser QA dùng `scripts/qa_ui_phase9.cjs`, `scripts/qa_ui_phase9_final.cjs` và [script công thức](qa/qa-formula.cjs). Chỉ định `PLAYWRIGHT_MODULE` tới runtime Playwright đã cài; các script chỉ nhận localhost. Mutation retry công thức được intercept; kiểm thử backend thực hiện trên DB tổng hợp. [PDF](qa/matrix-a4.pdf), [Excel](qa/matrix.xlsx), [kiểm tra in/xuất](qa/print-export-qa.json) và 72 ảnh nằm trong hồ sơ này.

Không commit, deploy, tạo PR hoặc gọi nhà cung cấp AI thật. Những thay đổi và dữ liệu đã có trước lượt làm được giữ nguyên.
