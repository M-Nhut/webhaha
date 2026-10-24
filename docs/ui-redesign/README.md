# LMath — Thiết kế lại giao diện Modern White Academy

**Khối câu hỏi hiện tại:** Đã đồng bộ kiểu Soft UI xanh LMath cho làm bài, xem lại bài đã làm, ngân hàng và các bản xem trước câu hỏi. Card trắng bo28px, đáp án22px có bóng hắt, vòng tròn A/B/C/D và a–d, vùng đọc20px. Đã bỏ liên kết “Đến cuối bài” trong từng câu. [Bản đồng bộ và kiểm chứng](question-unified/README.md); [bản thiết kế làm bài ban đầu](soft-exam/README.md) giữ làm lịch sử.

**Điều chỉnh theo mẫu người dùng ngày 19/10/2026:** Sidebar chuyển sang thanh xanh104px với icon trắng, mục đang chọn nối nền trang bằng hai cung lõm. Khung nội dung sáng bo góc36px trên desktop; chữ nội dung16px, tiêu đề30px, câu hỏi18–20px, font Be Vietnam Pro thống nhất. Trên tablet/mobile dùng drawer có nhãn. [Báo cáo sidebar](sidebar-blue-rail/README.md) và [báo cáo bố cục/chữ](readable-shell/README.md) ghi thay đổi và giới hạn kiểm chứng; đây là cập nhật sau nghiệm thu Phase 9.

**Thương hiệu hiện tại: LMath.** Trên laptop, logo đăng nhập192px nằm cạnh tên LMath; dòng nhỏ “Không gian học tập và giảng dạy” nằm dưới tên. Nhận diện nằm trực tiếp trên nền trang; form bên phải là card riêng, hai vùng cách64px. Tên hiển thị, tiêu đề trang, nhãn truy cập và footer đã đồng bộ. [Bản tách khối hiện tại —100 kiểm tra browser đạt](login-detached/README.md); [cập nhật thương hiệu](lmath-brand/README.md) và [bản logo lớn trước đó](login-brand/README.md) giữ làm lịch sử.

**Cập nhật 19/10/2026:** Phase 3–9 đã hoàn tất phần giao diện Modern White Academy cho toàn bộ 32 trang hoạt động, shell, component và trang lỗi. Phase 9 đã dọn theme/markup/alias/script cũ, kiểm tra consumer và nghiệm thu toàn giao diện; xem [báo cáo cuối](phase-9/README.md). Full pytest còn 75 failure nghiệp vụ và một lỗi collection đã tồn tại trước Phase 9; không có failure mới, chi tiết và phạm vi kiểm chứng ghi rõ trong báo cáo. Tài liệu kiểm kê Phase 1–8 được giữ làm lịch sử triển khai.

**Mốc Phase 1: hoàn tất kiểm kê mã nguồn ngày 13/10/2026.** Ở mốc này chưa triển khai giao diện mới, chưa chốt token hoặc tạo bản mẫu Phase 2, chưa xóa giao diện cũ. Yêu cầu đích là thiết kế lại toàn bộ web theo Modern White Academy, đặc biệt ngân hàng câu hỏi và bài kiểm tra; sau chuyển đổi chỉ còn một hệ thống giao diện.

## 1. Đầu ra và phạm vi xác minh

| Tài liệu | Nội dung |
|---|---|
| [Ma trận toàn bộ màn hình](phase-1-screen-matrix.md) | Liệt kê đủ 52 template, chức năng, liên kết nguồn, endpoint, phase phụ trách và chỉ số style inline |
| [Ngân hàng, nhập câu hỏi và phân loại](phase-1-bank-import.md) | 7 template trang; quyền common/private/overlay, research/general, wizard import, phân loại, catalog, API và trạng thái |
| [Đề kiểm tra, đánh giá đầu vào và học tập](phase-1-assessments-learning.md) | 13 template trang, 18 màn hình/biến thể; chọn câu, biên soạn, làm bài, kết quả, tiến độ, draft và nguồn |
| [Tài khoản, quản lý và báo cáo](phase-1-management-reports.md) | 14 template trang đang dùng, 6 template lỗi và analytics cũ; dashboard, lớp, người dùng, AI và quyền |
| [Khung chung và tài nguyên](phase-1-shared-assets.md) | Toàn bộ CSS/JS, thứ tự tải, thành phần chung, dữ liệu cần giữ, ứng viên dọn và điều kiện xóa |
| [Inventory máy đọc được](phase-1-inventory.json) | Template dependency graph, assets, hook HTML/Alpine, render sites, routes và so sánh fixture |

Các tài liệu chuyên đề có phần giao nhau: hai trang theo dõi giáo viên được kiểm kê ở cả học tập và quản lý. Khi tính tổng dùng ma trận template duy nhất, không cộng số template ở ba báo cáo.

Đã đọc skill **ui-ux-pro-max** và áp dụng cách kiểm kê theo nhiệm vụ, trạng thái, quyền và khả năng truy cập của web Flask/Jinja. Tra cứu UX cục bộ tập trung vào modal/focus và bảng/empty states; hệ thống màu/font/bố cục sẽ được chốt ở Phase 2 theo yêu cầu Modern White Academy.

Mức xác minh: đọc trực tiếp template, routes, services liên quan, CSS/JS, tests; phân tích AST Python và tham chiếu template/static literal; đối chiếu thủ công các alias, render động và script preview. **Chưa khởi chạy Flask, chưa đăng nhập, chưa có ảnh browser và chưa chạy bộ kiểm thử nghiệp vụ.** Không truy cập DB thật hoặc `.env`. Mọi phát hiện về hành vi hiển thị cần runtime đều được đánh dấu để kiểm chứng, không coi là lỗi đã tái hiện.

## 2. Độ phủ kiểm kê

| Hạng mục | Kết quả |
|---|---:|
| Template tổng | **52** |
| Template trang cấp cao | **33**: 32 đang có route render, 1 ứng viên màn hình cũ |
| Component/partial | **12** |
| Template lỗi | **6**: master + 400/403/404/405/500; master còn fallback cho 429/mã khác |
| Base ứng dụng | **1** |
| CSS ứng dụng | **12**, tổng 3.305 dòng nguồn |
| JavaScript ứng dụng | **17**, tổng 2.998 dòng nguồn |
| `style=` trong template | **788** lần xuất hiện trong nguồn |
| Khối CSS/script inline | **2 / 16** |
| Route khai báo trong nguồn | **94**, gồm cả API, action, file và redirect; không phải 94 màn hình |
| Tham chiếu literal template/static bị thiếu | **0 / 0** trong phạm vi quét |

Không lấy số dòng làm đánh giá chất lượng hoặc kết luận mã chết. `inventory.json` ghi giới hạn của phép quét: URL/template tạo động, dữ liệu upload và branch theo endpoint cần đọc thủ công. Liên kết template từ handler là quan hệ cấp hàm, chưa chứng minh mọi URL dùng handler đó đều render; ví dụ `/ai-reports` redirect còn hai URL class/individual render cùng file.

Tất cả 32 template trang đang hoạt động, các component đang dùng, base và trang lỗi đều phải chuyển sang thiết kế mới. Không miễn trừ trang đang dùng `main.css`, trang ít dùng, CRUD hoặc trang ngoài shell.

## 3. Quyền thật cần giữ trong bản thiết kế

| Nhiệm vụ | Admin | Teacher | Student |
|---|---|---|---|
| Ngân hàng | Kiểm toán toàn bộ, tạo bank chia sẻ | Bank chung + bank riêng; có thể thêm/import overlay riêng vào bank chung; không sửa câu chung | Không truy cập |
| Tạo/biên soạn kiểm tra | Trong phạm vi route/session/lớp được phép | Lớp phụ trách, session của mình | Không tạo |
| Làm kiểm tra | Xem quản lý/kết quả | Xem quản lý/kết quả trong quyền lớp | Đề được giao và lớp đang học; một lần nộp |
| Tạo đánh giá đầu vào | Có | Hiện không được tạo; danh sách theo dữ liệu/quyền hiện có | Làm bài được giao qua Tự luyện |
| Tự luyện và tiến độ | Theo dõi học sinh | Theo dõi và tạo bản nháp củng cố trong quyền | Học tập cá nhân theo đầu vào/nguồn lớp |
| AI reports | Xem/đối chiếu theo route; không phát sinh AI như teacher | Lớp mình, phát sinh/đối chiếu theo trạng thái | Không vào workspace AI giáo viên |
| Khóa AI cá nhân | Không vào cài đặt khóa teacher | Chỉ khóa thuộc chính mình | Không truy cập |
| Quản lý lớp/người dùng | Có | Xem lớp/học sinh trong quyền | Xem lớp của mình |

`manager` và `parent` còn dấu vết UI/comment nhưng không có bằng chứng luồng hỗ trợ xuyên suốt như ba vai trò trên. Phase 2 không tự tạo thêm dashboard cho hai vai trò này hoặc mở quyền backend để khớp nút cũ. `role_required("teacher")` cho admin đi qua, nhưng nhiều handler còn kiểm tra hạn chế thêm; bảng trên là tóm tắt, bảng endpoint trong chuyên đề là chi tiết.

## 4. Yêu cầu ưu tiên cho ngân hàng và bài kiểm tra

### Ngân hàng câu hỏi

- Thiết kế lại cả danh sách, tạo/sửa, chi tiết, soạn câu, phân loại, evaluation và danh mục kiến thức.
- Hai chế độ **general** và **research Toán 9 C8-i/ID6** có dữ liệu và quyền khác nhau; không dựng một layout chỉ phù hợp bank nghiên cứu.
- Phân biệt bank chung, bank riêng và câu overlay riêng; số liệu/phạm vi/CTA phải phản ánh quyền từng câu.
- Tổ chức lại header, ma trận độ phủ, filter, kết quả và thao tác để vùng đọc không bị đẩy quá sâu.
- Giữ lazy load chi tiết/đáp án, phân trang giữ bộ lọc, render toán theo viewport, trạng thái retry/error và quyền bị thay đổi.
- Ba hình thức câu hỏi mới: chọn một, Đúng/Sai, trả lời ngắn; vẫn kiểm tra nhánh đọc dữ liệu lịch sử trước khi loại bỏ.
- Chọn nhiều để tạo đề hiện nằm ở màn hình tạo đề từ ngân hàng, không phải chức năng sẵn có của trang chi tiết bank. Chuyển vị trí hay mở rộng cần ghi rõ tác động chức năng.

### Nhập câu hỏi và biên soạn đề

- Thiết kế lại wizard `.tex` với kết quả kiểm tra nội dung, gợi ý phân loại và dò trùng là ba chiều trạng thái riêng.
- Giữ resume phiên import, so sánh hai bản, đổi đích, revision token, lưu một phần và receipt; phân biệt nhập bank với chuyển sang biên soạn đề.
- Thiết kế màn hình chọn câu có ngữ cảnh lớp/ngân hàng, quota theo hình thức và tổng điểm; làm rõ phần chọn thủ công/tự động.
- Editor có vùng thông tin đề, nội dung/đáp án/lời giải, nhãn kiến thức, trọng số, preview, tổng điểm, lưu nháp/giao và trạng thái khóa.
- Giữ dirty-state và lỗi lưu không làm mất DOM nhập liệu; không mô tả reorder/thêm câu/auto-save là sẵn có khi backend chưa hỗ trợ.

### Làm bài và kết quả

- Cùng `exam_take.html`/`exam_result.html` phục vụ kiểm tra standalone, đánh giá đầu vào và tự luyện; thiết kế đủ từng ngữ cảnh.
- Cần phân cấp rõ câu hỏi, dữ kiện/công thức, đáp án, tiến độ, thời gian và nộp bài; Đúng/Sai phải biểu thị câu chưa đủ ý.
- Kết quả có bản cá nhân, danh sách bài nộp, dữ liệu lịch sử chưa chấm và quyết định tiếp tục/kết thúc tự luyện.
- Phải giữ thang điểm standalone và rule chấm theo nguồn; không gộp điểm kiểm tra vào hồ sơ năng lực tự luyện.
- Mở lại đề chưa nộp **không đồng nghĩa lưu đáp án**. Chưa thấy autosave hoặc khôi phục câu trả lời đang nhập.
- Ma trận đề có dữ liệu chưa xác nhận, bảng rộng, bản in và Excel; thiết kế đủ các trạng thái này.

## 5. Backlog cần kiểm chứng, chưa sửa trong Phase 1

| Ưu tiên khi chuyển đổi | Phát hiện từ mã nguồn | Hành động kế tiếp |
|---|---|---|
| Trước chốt soạn câu | Nút Lưu general phụ thuộc `curriculum_node_id`, trong khi mode general có thể để null | Tái hiện bằng dữ liệu thử; chốt điều kiện hợp lệ theo backend rồi mới sửa |
| Trước nghiệm thu sửa bank | `edit_question_bank` tham chiếu `dt` nhưng file chưa thấy import tương ứng | Test POST cô lập để tách lỗi cũ khỏi thay đổi giao diện |
| Trước chốt điều hướng ngân hàng | Link câu gốc từ import có anchor ID nhưng chưa kèm page của câu | Kiểm tra bank nhiều trang; bảo đảm link đưa tới đúng câu |
| Trước chốt làm bài | Timer khởi tạo lại theo GET; `form.submit()` khi hết giờ bỏ qua submit listener; answered chỉ thêm không xóa | Kiểm chứng countdown, tracking, double submit và đếm partial/bỏ đáp án; xử lý cùng phần tương tác mới |
| Trước chốt hướng dẫn ngắn | Rule numeric hiển thị phụ thuộc metadata được inject theo ngữ cảnh | Kiểm tra standalone/diagnostic/practice cùng rule để hint đúng cách chấm |
| Trước chốt biểu đồ | Progress có fallback dữ liệu 0, chuỗi mastery/điểm cần đối chiếu trục; AI và progress đều có màu hard-code trong JS | Phân biệt thiếu dữ liệu với điểm 0; chuyển palette cả CSS và JS |
| Khi chuyển form quản lý | Option role admin/điều kiện manager trong template không khớp quyền handler | Làm UI khớp quyền thật; không nới quyền |
| Trước chạy regression | Route fixture có 79 entry, mã nguồn có 94; 15 endpoint mới và 2 endpoint lệch methods | Xác minh baseline trong DB test riêng; cập nhật fixture theo contract được xác nhận, không đổi route để làm test cũ pass |

Hai endpoint lệch methods: `teacher_ai_test_key` và `teacher_ai_retry_key` hiện khai báo GET/POST, fixture chỉ POST. Nhóm endpoint mới gồm assessments, AI reports, diagnostics review/choices/delete, lazy question detail và favicon; xem chi tiết trong JSON. Đây là so sánh tĩnh, chưa phải kết quả chạy test.

## 6. Chuyển giao theo phase, không bỏ sót màn hình

| Phase | Phạm vi và điều kiện đầu ra |
|---|---|
| **1 — hoàn tất** | Ma trận đủ template/asset/route, quyền, trạng thái, hook và danh sách dọn có chứng cứ |
| **2 — đã duyệt để triển khai** | Hệ thống Modern White Academy, kiến trúc CSS, bản mẫu tương tác và đặc tả đầy đủ; được người dùng tiếp tục bằng yêu cầu Phase 3 |
| **3 — hoàn tất** | Shell + login/register/profile/errors đã áp dụng; nền tảng chung mới, tài nguyên local, gỡ theme/asset cũ thuộc phạm vi; có QA và ảnh browser |
| **4 — hoàn tất** | Danh sách/form/chi tiết bank, soạn câu, phân loại, catalog, classification evaluation đã thay toàn bộ; đủ general/research/overlay, có POST/browser QA và dọn style cũ |
| **5 — hoàn tất** | Import `.tex`, dò trùng/receipt/resume, chọn từ bank và editor đề đã thay toàn bộ; có QA POST/desktop/mobile và gỡ giao diện cũ trong phạm vi |
| **6 — hoàn tất** | Quản lý kiểm tra, ma trận/in/Excel, làm bài và kết quả; đủ standalone/đầu vào/tự luyện trong hai màn hình dùng chung; có QA nộp bài, responsive và dọn giao diện cũ trong phạm vi |
| **7 — hoàn tất** | Đầu vào/wizard, tự luyện/tiến độ, theo dõi giáo viên và duyệt bản nháp đã thay toàn bộ; biểu đồ cục bộ, bản đồ kiến thức trung tính, QA POST và kiểm tra take/result dùng chung; AI workspace tiếp tục Phase 8 |
| **8 — hoàn tất** | Dashboard theo role, lớp/người dùng/danh bạ, đủ bốn chế độ AI reports và khóa AI đã thay; có CRUD/CSRF/role/browser QA, dọn CSS/partial/script cũ và sửa validation trùng tài khoản |
| **9 — hoàn tất giao diện** | 49 template có consumer, dọn alias/theme/preview cũ, renderer công thức mới, QA toàn bộ màn hình/in/Excel; bảo trì 94 route fixture và đối chiếu full pytest trước/sau, không phát sinh lỗi mới |

Mỗi màn hình có phase phụ trách trong [ma trận](phase-1-screen-matrix.md). Khi triển khai, cập nhật tiến độ theo màn hình và trạng thái; không kết luận xong cả trang chỉ vì đã thay màu hoặc shell.

## 7. Tiêu chí dọn sạch cuối dự án

1. Chỉ một bộ token/nền tảng/thành phần mới; không nạp `neo-pop.css` hoặc giữ theme cũ làm lớp ghi đè. Phần giao diện cũ trong `main.css` cũng phải được thay thế.
2. Tất cả layout độc lập, trang cấp cao, component đang dùng và JS sinh markup/chart đã chuyển; không còn trang cũ sót sau menu.
3. Mọi ứng viên bỏ dùng có quyết định giữ/chuyển/xóa dựa trên consumer thật. `import_scope.js` còn `restoreImport` đang dùng; API báo cáo còn dùng; không xóa theo tên cũ.
4. Asset cũ được thay và gỡ link trước khi xóa; không xóa avatar/ảnh upload, công thức, dữ liệu import hoặc thư viện theo phép tìm kiếm literal.
5. Script preview/test/tài liệu mô tả theme cũ được chuyển hoặc loại cùng consumer; không giữ thư mục UI cũ trong bản chạy. Dùng Git để truy vết phiên bản trước.
6. Kiểm tra không URL asset 404, selector/hook hỏng, request thay đổi trái phép hoặc mất MathJax/CSRF/quyền; đối chiếu các phát hiện baseline để không nhầm lỗi sẵn có với regression.
7. Nghiệm thu 375/768/1024/1440px, nội dung toán dài, bảng, keyboard/modal focus, reduced-motion, empty/loading/error và bản in/Excel. Chỉ ghi đạt sau kiểm chứng thực tế.

## 8. Kiểm tra tài liệu Phase 1

- Đối chiếu đủ 52 file `templates/**/*.html` với ma trận, không thiếu hoặc trùng file.
- Đối chiếu 12 CSS và 17 JS ứng dụng với danh mục tài nguyên; không tính vendor là code giao diện tự viết.
- Kiểm tra liên kết nội bộ trong tài liệu và asset/template literal; các alias/render động được chú thích.
- Kiểm tra checksum các file ứng dụng trước/sau kiểm kê để bảo đảm Phase 1 chỉ thêm tài liệu, không sửa UI hoặc nghiệp vụ.
- Bộ test chức năng và việc xóa giao diện cũ ghi riêng theo phase triển khai. Phase 2 và Phase 3 được người dùng yêu cầu ngày 14/10/2026; QA của bản mẫu và của web thật ghi trong thư mục tương ứng.
