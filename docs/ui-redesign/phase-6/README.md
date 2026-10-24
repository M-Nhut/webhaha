# Phase 6 · Quản lý kiểm tra, ma trận, làm bài và kết quả

**Cập nhật 17/10/2026:** nhóm đầu vào/tự luyện/tiến độ/theo dõi đã được chuyển ở [Phase 7](../phase-7/README.md). Phạm vi và các giới hạn bên dưới ghi tại mốc nghiệm thu Phase 6.

Hoàn tất ngày 15/10/2026 theo yêu cầu người dùng, áp dụng UI/UX Pro Max và hệ thống Modern White Academy đã duyệt. Phạm vi S10–S13 được thay toàn bộ giao diện; hai màn hình dùng chung đã bao phủ kiểm tra độc lập, đánh giá đầu vào, tự luyện 22 câu và bài luyện lịch sử. Phase 7 chưa triển khai: danh sách/tạo đầu vào, trang tự luyện, tiến độ và theo dõi giáo viên vẫn thuộc phase kế tiếp.

## Giao diện đã hoàn tất

| Màn hình | Thay đổi |
|---|---|
| Danh sách kiểm tra | Header, nhóm đề đã giao/nháp, metadata và hành động theo quyền teacher/admin; danh sách học sinh chỉ có hành động backend hỗ trợ; trạng thái rỗng riêng. Không suy diễn “đã làm/chưa làm” khi route không cung cấp dữ liệu đó. |
| Ma trận đề | Context và tổng điểm, cảnh báo nhãn chưa xác nhận/không xác định; bảng đủ 19 cột, cuộn trong vùng có tên truy cập; xuất Excel và in A4 ngang. Giữ phân biệt dữ liệu Vận dụng cao với biểu mẫu xuất hiện có. |
| Làm bài | Bố cục tập trung, câu hỏi/dữ kiện/công thức/ảnh rõ; cột tiến độ và giờ trên desktop, điều hướng thu gọn trên mobile; ba loại câu hỏi và nhánh lịch sử. Đúng/Sai thiếu ý được tính một phần, xóa câu trả lời ngắn giảm tiến độ. |
| Nộp bài | Xác nhận số câu đầy đủ/một phần/bỏ trống, Escape và trả focus; trạng thái đang gửi, chặn gửi lặp; lỗi gửi giữ nguyên trường trả lời để thử lại. Hết giờ dùng cùng luồng gửi và ghi thời gian, tự thử lại khi có mạng. |
| Kết quả cá nhân | Điểm/thang điểm thật, phân biệt đúng/một phần/sai/bỏ trống/chưa chấm; đối chiếu đáp án, lời giải thu gọn, dữ kiện và ảnh có phóng to/thử lại; quyết định tiếp tục/kết thúc chỉ hiện theo gate server. |
| Kết quả quản lý | Bảng bài nộp, xem chi tiết trong phạm vi lớp/đề; trạng thái chưa có bài nộp và điểm lịch sử chưa chấm; không quy điểm thiếu thành 0 đã chấm. |

Màu, font Be Vietnam Pro cục bộ, khoảng cách, viền, focus, control mobile và trạng thái theo token chung. Không thêm framework hoặc tài nguyên script/font bên ngoài. Đã kiểm tra các chiều rộng **375/768/1024/1440px**, bàn phím/dialog, reduced motion, ảnh lỗi, bản in và công thức.

## Giữ hợp đồng và dọn mã cũ

- Viết lại bốn template S10–S13, `assessments.css`, module làm bài; thêm CSS/JS trang kết quả và script in ma trận. **69 khai báo inline style cũ đã về 0** trong bốn template; không còn inline event handler của chúng.
- Gỡ **34 lượt selector CSS** làm bài/kết quả cũ khỏi `pages/workspaces.css`. CSS `assessments.css` cũ được thay trực tiếp, không lưu bản giao diện dự phòng. Những rule chung còn consumer ở `practice_draft` và trang Phase 7–8 được giữ tới khi chuyển consumer đó.
- `main.css` tiếp tục là điểm import nền tảng duy nhất; phiên bản asset được cập nhật để tải giao diện mới.
- Chỉ có hai điều chỉnh nhỏ ở route runtime: truyền rule trả lời số vào hướng dẫn cho mọi ngữ cảnh và đưa học sinh chưa nộp kiểm tra độc lập về đúng danh sách kiểm tra. Không thay dịch vụ chấm điểm, quy tắc chọn đề, ma trận, phân quyền hoặc cập nhật năng lực.
- Giữ CSRF, tên trường đáp án/thời gian, thang điểm từng ngữ cảnh và cơ chế chỉ ghi nhận một bài nộp. Kiểm tra độc lập không cập nhật hồ sơ năng lực tự luyện. Native form vẫn là fallback khi không chạy JavaScript.

**Giới hạn hiện có được ghi rõ:** chưa có autosave/khôi phục đáp án. Tải lại hoặc rời trang có thể mất nội dung đang nhập. Đồng hồ mới tính theo thời gian thực trong lượt mở trang, nhưng một GET mới vẫn nhận đủ thời lượng từ server như trước; Phase 6 không thêm deadline lưu trong DB hoặc phiên lưu bài làm. Khi gửi lỗi, đáp án chỉ còn trong DOM của trang đang mở.

## Kiểm chứng và bằng chứng

- **128 test Python đạt**: Phase 6, standalone assessment/scoring/matrix, practice 22 câu, learning loop và hồi quy Phase 4–5. Bao gồm POST thật với CSRF trong DB bộ nhớ: đủ/sai/bỏ trống, nộp lặp, rollback khi chấm lỗi, quyền và cách ly hồ sơ năng lực; bài luyện/đầu vào 22 câu đều chấm đúng 10/10 khi trả lời đúng.
- Danh sách/ma trận: **149 kiểm tra trình duyệt + 54 trường hợp Jinja**, [báo cáo](list-matrix-qa.json). [Bản in](matrix-print-qa.json) xác minh đủ 19 cột; PDF nháp và đã giao đều hai trang A4 ngang.
- Kết quả: **88 kiểm tra trình duyệt + 27 trường hợp Jinja**, [QA chính](result-qa.json), [ảnh/in/reduced motion](result-media-qa.json), [kiểm tra nguồn](result-static-qa.json).
- Làm bài: **62 kiểm tra trình duyệt đạt**, [QA trạng thái và tương tác](taking-qa.json), [phạm vi riêng của bộ QA](qa/TAKING.md). Nghiệm thu tích hợp **88 kiểm tra đạt**, gồm POST thật ở cả ba ngữ cảnh, lỗi gửi giữ đáp án và hết giờ; [báo cáo](browser-qa.json). Sau khi reset preview, **73 kiểm tra chỉ đọc đạt** trên dữ liệu sạch ở bốn chiều rộng và bốn ngữ cảnh làm bài; [báo cáo](capture-qa.json). Không có lỗi JavaScript, static asset hoặc tài nguyên font/script/style bên ngoài trong lượt tích hợp. Xem thêm [kiểm tra toàn vẹn](integrity-qa.json).
- Ảnh minh chứng trong [screenshots](screenshots/), script QA chuyên đề và PDF trong [qa](qa/). Script tích hợp: `scripts/qa_ui_phase6.cjs`; regression mới: `tests/test_ui_redesign_phase6.py`.

Một lượt chạy mở rộng phát hiện **6 test tạo đánh giá đầu vào đã lỗi từ baseline**: fixture giáo viên POST vào endpoint hiện chỉ cho admin. Đã tái hiện HTTP 403 với handler chụp trước Phase 6, xác nhận nguồn authoring không đổi. Không mở quyền để làm test cũ đạt; việc đồng bộ fixture authoring thuộc Phase 7. Chi tiết: [baseline-authoring-qa.json](baseline-authoring-qa.json). Vì vậy 128 test nêu trên là bộ hồi quy có phạm vi, không phải tuyên bố toàn bộ test dự án đều đạt.

Lệnh kiểm thử đã chạy:

```bash
python3 -m pytest tests/test_ui_redesign_phase6.py tests/test_standalone_assessment.py tests/test_assessment_scoring.py tests/test_assessment_matrix.py tests/test_practice22.py tests/test_learning_loop_phase4.py tests/test_ui_redesign_phase5.py tests/test_ui_redesign_phase4.py --tb=short --disable-warnings -q
```

## Xem trên dữ liệu minh họa

```bash
python3 scripts/preview_ui_phase6.py --port 8768
```

Mở [đăng nhập preview Phase 6](http://127.0.0.1:8768/login). Tài khoản `qa_teacher`, `qa_admin`, `qa_student`, mật khẩu `Academy123!`. `/qa/fixture` chỉ tồn tại ở script preview để xác định ID mẫu. Preview chạy SQLite bộ nhớ, storage tạm, không đọc `.env` hoặc dữ liệu thật; mọi bài nộp thử mất khi khởi động lại preview. Dữ liệu đề 22 câu là fixture giao diện tổng hợp, không được dùng làm bằng chứng thuật toán chọn câu.

Đã kiểm chứng metadata file DB thật không đổi. Không truy cập nội dung DB thật, khóa dịch vụ hoặc upload người dùng; không triển khai lên production.
