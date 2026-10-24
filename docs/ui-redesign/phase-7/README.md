# Phase 7 · Đầu vào, tự luyện và theo dõi học tập

**Hoàn tất 17/10/2026**, theo yêu cầu người dùng và hệ thống Modern White Academy đã duyệt với UI/UX Pro Max. Toàn bộ S14–S20 đã thay giao diện, gồm các trạng thái rỗng, thiếu bằng chứng, lỗi, nguồn không hợp lệ và khóa theo quyền. Take/result của Phase 6 đã được kiểm chứng lại với luồng học tập. Phase 8–9 tiếp tục theo kế hoạch; chưa thay dashboard, quản lý lớp/người dùng hoặc workspace AI của Phase 8.

## Phạm vi đã hoàn tất

| Màn hình | Kết quả |
|---|---|
| S14 · Danh sách đầu vào | Danh sách quản lý mới, trạng thái và số bài nộp thật, quyền tạo/xem/xóa đúng vai trò; native dialog xóa có tên đề, mô tả ảnh hưởng và mặc định hủy. |
| S15 · Tạo đầu vào | Wizard nguồn → chọn câu → kiểm tra/giao. Giữ cấu trúc 22 câu = 12 chọn một + 4 Đúng/Sai + 6 trả lời ngắn, bao phủ 8 dạng, 40 phút. Có quota, nguồn/lớp, phân trang/lọc, đáp án lazy, tiến độ đọc đủ 22 câu và xác nhận giao. |
| S16 · Tự luyện | Chọn lớp trước; một hành động chính phản ánh trạng thái: làm đầu vào, tiếp tục đề hiện có, xem kết quả để quyết định hoặc sinh bài mới. Bài giáo viên giao và bằng chứng nằm ở vùng hỗ trợ. |
| S17 · Kết quả và tiến bộ | Chọn môn, trạng thái bằng chứng, KPI có mẫu số rõ; điểm 0–10, mastery 0–1 và tỷ lệ theo mức độ là ba biểu đồ riêng. Bảng dữ liệu và liên kết bài làm hoạt động khi biểu đồ lỗi. |
| S18 · Theo dõi học tập | Chọn lớp, bảng/card học sinh; tách số bài tự luyện và kiểm tra, điểm trung bình chỉ đầu vào/tự luyện; thiếu dữ liệu khác điểm 0; giữ liên kết quá trình và báo cáo lớp. |
| S19 · Quá trình học sinh | Phạm vi lớp, hồ sơ môn, bản đồ kiến thức thu gọn, lỗi quan sát từ bài đã chấm, bằng chứng kiểm tra riêng và lịch sử. Form giao bài củng cố kiểm tra nguồn theo lớp, mức nhận thức và tỷ lệ tổng 100%. |
| S20 · Duyệt bài luyện | Căn cứ lựa chọn thu gọn, thông tin phát hành và toàn bộ câu/đáp án/lời giải chỉ đọc. Tiêu đề, thời gian 5–180 phút và phát hành khớp gate khóa bài nộp, quyền lớp và nguồn hiện tại. Có ảnh phóng to/thử lại và bản in. |

Đã kiểm tra **375/768/1024/1440px**, focus/bàn phím/native dialog, reduced motion, công thức, hình lỗi/thử lại, disclosure và cuộn bảng cục bộ. Dùng font cục bộ và token trắng/xám xanh/xanh học thuật chung. Không thêm framework UI.

## Dữ liệu và tương tác

- Wizard vẫn chỉ cho admin tạo; teacher giữ phạm vi creator hiện có. Review chỉ đọc, server kiểm tra lại digest trước khi tạo; không ghi đề hoặc assignment trước xác nhận cuối. Metadata lựa chọn có thể khôi phục trong tối đa một giờ và phải được tái xác minh.
- Mỗi học sinh chỉ có một bước tiếp theo phù hợp trạng thái. Sinh bài khi đã có đề/decision đưa về đúng đề/kết quả, không tạo đề thứ hai. Nguồn vẫn do class resolver quyết định, không mở thêm ngân hàng riêng.
- Đổi lớp trong form giáo viên sẽ bỏ chọn và khóa nguồn không còn hợp lệ. Nội dung/đáp án/nhãn và manifest của bản nháp giữ nguyên khi lưu thông tin phát hành.
- Bản đồ 8 × 4 phân biệt “Chưa biết”, bằng chứng còn ít và mức đã đủ bằng chứng. Phần trăm không được mô tả như điểm kiểm tra hoặc dự báo bài tiếp theo.
- Lịch sử chưa chấm giữ điểm `null`; bài đã chấm nhưng thiếu thang điểm ghi “Chưa có thang điểm”. Snapshot thiếu/sai dữ liệu là khoảng trống biểu đồ, không tự tạo 50%. Điểm 0 và mastery 0 hợp lệ vẫn được hiển thị.
- Biểu đồ dùng **Chart.js 4.5.1 cục bộ**, màu từ token; không còn CDN trên trang tiến độ. Dưới bốn điểm dữ liệu không nối đường xu hướng; thiếu giá trị giữ khoảng trống. Có bảng tương đương và thông báo khi thư viện chưa tải được.
- Giữ CSRF, một lần nộp, quy tắc chấm điểm, selection/source policy và cách ly kiểm tra độc lập khỏi hồ sơ sinh bài luyện. Mã dịch vụ chấm/chọn đề/AI không thay đổi trong Phase 7.

**Giới hạn giữ nguyên:** chưa có autosave đáp án. Mở lại đề không khôi phục câu trả lời chưa nộp; tải lại trang vẫn khởi tạo thời lượng theo runtime hiện có. Không thêm deadline DB, reorder câu, thay nguồn trong bản nháp hoặc chức năng AI mới.

## Dọn giao diện cũ

- Viết lại 7 template, CSS wizard và hai module tiến độ/theo dõi; thêm CSS theo trang và script nhỏ cho native dialog/ảnh/phát hành. Không lưu bản UI cũ làm lớp dự phòng.
- Gỡ **83 inline style** ở 7 màn hình và **10** ở component bản đồ kiến thức: tổng **93 → 0**. Gỡ **5 inline event handler**, script khởi tạo cũ, global initializer không còn consumer và palette hex cũ trong module biểu đồ.
- Gỡ **38 lượt selector** learning/question cũ hết consumer khỏi `question-document.css` và `pages/workspaces.css`. `learning.css` được viết lại cho ma trận/audit dùng chung; các layout trang Phase 7 dùng CSS mới.
- Những rule còn consumer ở trang lớp/báo cáo Phase 8 được giữ tới khi chuyển nhóm đó. Dọn toàn bộ dự án và partial legacy không còn runtime vẫn được kiểm toán ở Phase 9.
- Sửa `min-width` của disclosure bằng chứng trong màn hình làm bài để bảng cuộn trong vùng của nó khi mở trên mobile; không làm cả trang tràn ngang. Phiên bản asset đã được cập nhật.

## Kiểm chứng

| Nhóm | Bằng chứng |
|---|---|
| Python | **126 test đạt**, gồm 16 test Phase 7, authoring đầu vào, xóa/lời giải, learning workspace/loop, fixed22/source inventory/resolver và hồi quy Phase 6/standalone/scoring/matrix. |
| Đầu vào | **68 browser checks + 16 kiểm tra API thật + 18 tạo/xóa đề thật**. [Giao diện](diagnostics-browser-qa.json), [API](diagnostics-real-api-qa.json), [publish/delete](diagnostics-publish-qa.json), [nguồn](diagnostics-static-qa.json). |
| Học sinh | **303 browser checks**: 263 theo 11 tài khoản/trạng thái và 40 về ma trận/đổi môn. [QA chính](student-browser-qa.json), [ma trận](student-matrix-qa.json), [nguồn](student-static-qa.json). |
| Giáo viên | **197 browser checks + 57 render Jinja**: 162 workspace/form, 15 media/print và 20 lỗi quan sát. [QA](teacher-qa.json), [media](teacher-media-qa.json), [quan sát](teacher-observations-qa.json), [Jinja](teacher-render-qa.json), [nguồn](teacher-static-qa.json). |
| Nghiệm thu tích hợp | **83 kiểm tra đạt** với POST thật: sinh bài, resume, nộp, tiếp tục, kết thúc, tạo/phát hành draft và xem bài được giao. [Báo cáo](browser-qa.json). |
| Preview cuối | [QA chỉ đọc sau reset](capture-qa.json), gồm 7 màn hình và take/result mở bảng bằng chứng ở mobile/desktop; [kiểm tra toàn vẹn](integrity-qa.json). |
| Bản in | [Báo cáo in](teacher-print-qa.json), [PDF A4](qa/teacher-draft-a4.pdf): đủ 22 tiêu đề câu, card câu không bị cắt qua trang, trạng thái disclosure được khôi phục sau in. |

Số lượng ở các bộ QA có phần giao nhau, không cộng để suy ra số tình huống độc lập. Ảnh trong [screenshots](screenshots/); script chuyên đề nằm trong [qa](qa/); script tích hợp tại `scripts/qa_ui_phase7.cjs`.

Hồi quy đã phát hiện và xử lý phần lỗi quan sát bị thiếu trong lần dựng đầu tiên của S19. Các test cũ cũng được đồng bộ với hợp đồng đang chạy: admin duyệt/chọn thủ công, disclosure lời giải native và mock AI response đủ schema/cache/force. Những kiểm tra tương thích recovery cũ được giữ ở ranh giới dịch vụ/bản chụp; không nới quyền hoặc sửa backend để làm test đạt. [Chi tiết cập nhật fixture](test-contract-qa.json).

Lệnh đã chạy:

```bash
python3 -m pytest tests/test_ui_redesign_phase7.py tests/test_diagnostic_phase2.py tests/test_diagnostic_delete_and_explanation.py tests/test_learning_workspace.py tests/test_learning_loop_phase4.py tests/test_practice22.py tests/test_practice_source_inventory.py tests/test_source_resolver_phase4.py tests/test_ui_redesign_phase6.py tests/test_standalone_assessment.py tests/test_assessment_scoring.py tests/test_assessment_matrix.py --disable-warnings --tb=short -q
```

Đây là bộ hồi quy theo phạm vi Phase 7 và các consumer liên quan, không phải tuyên bố mọi test của toàn dự án đã được chạy.

## Xem preview sạch

```bash
python3 scripts/preview_ui_phase7.py --port 8769
```

[Đăng nhập Phase 7](http://127.0.0.1:8769/login), mật khẩu chung **`Academy123!`**:

- `qa_admin`: danh sách/tạo đầu vào.
- `qa_teacher`: theo dõi lớp/học sinh, duyệt bản nháp.
- `qa_student`: kết quả nhiều lượt và bài giáo viên giao. Chọn lớp **Toán 9 · Lớp 9A** trong trang tự luyện.
- `qa_start`, `qa_resume`, `qa_pending`, `qa_cold`, `qa_no_course`, `qa_no_diagnostic`, `qa_blocked`: các trạng thái học tập cụ thể.

Preview chỉ dùng SQLite bộ nhớ, tài khoản/câu hỏi tổng hợp và storage tạm. Không đọc `.env`, khóa hoặc nội dung DB/upload thật. Metadata file DB thật đã được đối chiếu không đổi. Tạo/xóa/nộp trong QA chỉ tác động dữ liệu giả; preview được reset sau nghiệm thu. Fixture 22 câu dùng để kiểm tra giao diện, không phải bằng chứng đánh giá thuật toán chọn câu. Không deploy hoặc thay dữ liệu production.

Chart.js được lưu tại `static/vendor/chartjs/chart.umd.js`; giấy phép MIT đi kèm `static/vendor/chartjs/LICENSE.md`. Nguồn: [hướng dẫn tích hợp chính thức](https://www.chartjs.org/docs/latest/getting-started/integration.html) và [giấy phép của phiên bản 4.5.1](https://github.com/chartjs/Chart.js/blob/v4.5.1/LICENSE.md).
