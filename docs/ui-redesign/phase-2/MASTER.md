# LMath · Modern White Academy

**Cập nhật ngày 19/10/2026:** Người dùng chọn sidebar xanh icon trắng, mục active lõm vào nền trang; tiếp tục yêu cầu khung nội dung sáng bo góc lớn và chữ to, rõ, đồng bộ. Bản chạy theo [đặc tả sidebar](../sidebar-blue-rail/README.md) và [bố cục/chữ mới](../readable-shell/README.md); prototype Phase 2 giữ làm lịch sử. Token áp dụng trong web nằm ở `static/css/tokens.css`.

Ngày thiết kế: 14/10/2026. **Phase 3–7 đã được người dùng yêu cầu và hoàn tất.** Tài liệu này cùng `tokens.css` là nguồn thiết kế; nền tảng/shell/tài khoản/lỗi ghi ở [Phase 3](../phase-3/README.md), nhóm ngân hàng–kiến thức ghi ở [Phase 4](../phase-4/README.md). Phạm vi chức năng lấy từ Phase 1; nhập/biên soạn đề ghi ở [Phase 5](../phase-5/README.md), kiểm tra/ma trận/làm bài/kết quả ghi ở [Phase 6](../phase-6/README.md); đầu vào/tự luyện/tiến độ/theo dõi ghi ở [Phase 7](../phase-7/README.md); các nhóm còn lại triển khai theo phase 8–9.

## 1. Quyết định thiết kế

LMath là công cụ học tập và giảng dạy có ngân hàng nội dung toán, biên soạn đề và theo dõi bằng chứng học tập. Thiết kế mới ưu tiên tìm đúng nội dung, đọc rõ câu hỏi, biết trạng thái và hoàn thành thao tác. Modern White Academy ở đây là hướng thẩm mỹ riêng của LMath, không phải tên một thư viện hay bộ UI chính thức.

- **Bề mặt:** sidebar và khung ngoài xanh học thuật; khung nội dung/header xám xanh nhạt bo góc36px trên desktop, panel trắng. Các vùng được phân biệt bằng khoảng cách và viền 1px.
- **Phân cấp:** H1 → mô tả ngắn → context/filter → nội dung → thao tác theo nhiệm vụ. Mỗi màn hình có một hành động chính; chỉ đặt thêm nút nộp ở vị trí cuối khi nội dung dài.
- **Màu chính:** xanh học thuật cho CTA, đường dẫn, active và focus; màu thành công/cảnh báo/lỗi có mục đích cụ thể, kèm chữ.
- **Nội dung:** bỏ mascot, sticker, bóng cứng và badge trang trí. Logo trong shell giữ nhỏ; trang đăng nhập dùng logo192px cạnh chữ LMath và dòng nhỏ “Không gian học tập và giảng dạy” bên dưới tên. Nhận diện nằm trên nền trang, form là card riêng bên phải cách64px; xem [kết quả](../login-detached/README.md).
- **Mật độ:** 16px trong không gian quản lý; chú thích14px, câu hỏi/lời giải18–20px. Nút/ô nhập chính cao46px; số liệu không lấn át nội dung chính.
- **Chuyển động:** phản hồi màu150ms, không nâng/nhún control; không animation nền hoặc carousel. Logo đăng nhập là ngoại lệ được người dùng yêu cầu: float dọc±6px (mobile±4px), chu kỳ5s ease-in-out; tắt khi reduced-motion hoặc in.
- **Theme:** light-only theo brief; dark mode không thuộc Phase 2.

**Khối câu hỏi theo yêu cầu19/10/2026:** [Soft UI / Soft3D pha Claymorphism nhẹ](../soft-exam/README.md), nền xanh nhạt đồng bộ LMath, card trắng28px, đáp án22px có bóng hắt và chữ cái trong vòng tròn. [Bản đồng bộ hiện tại](../question-unified/README.md) áp dụng cùng thành phần cho làm bài, xem lại bài, ngân hàng, phân loại, xem trước thêm/sửa và nhập/đối chiếu câu trùng. `question-content.css` sở hữu hình dáng/chữ/khoảng cách chung; CSS trang chỉ giữ bố cục và trạng thái nghiệp vụ. `.academy-exam-focus` giữ riêng phần khung tập trung, thời gian và điều hướng khi làm bài. Rule dùng bóng cho khối câu hỏi thay thế hạn chế bóng của thiết kế ban đầu trong phạm vi này.

## 2. Token ba lớp

[tokens.css](tokens.css) chứa ba lớp. Primitive định nghĩa giá trị; semantic gán mục đích; component lấy từ semantic. Khi triển khai, CSS trang và màu chart/markup sinh từ JS cùng dùng token. Không sao chép hex vào từng màn hình, không tiếp tục ghi đè qua nhiều theme.

| Vai trò | Giá trị đề xuất | Token semantic |
|---|---|---|
| Canvas | `#F5F7FB` | `--color-canvas` |
| Surface | `#FFFFFF` | `--color-surface` |
| Chữ chính | `#0F172A` | `--color-text` |
| Chữ phụ | `#475569` | `--color-text-secondary` |
| Chữ muted | `#596579` | `--color-text-muted` |
| CTA/link/focus | `#1D4ED8` | `--color-primary`, `--color-focus` |
| Hover CTA | `#1E40AF` | `--color-primary-hover` |
| Nền active/info | `#EFF6FF` | `--color-primary-subtle` |
| Viền phân vùng | `#E2E8F0` | `--color-border` |
| Viền input | `#8895A7` | `--color-input-border` |
| Thành công | `#166534` trên `#F0FDF4` | `--color-success`, `--color-success-subtle` |
| Cảnh báo | `#92400E` trên `#FFFBEB` | `--color-warning`, `--color-warning-subtle` |
| Lỗi/nguy hiểm | `#B91C1C` trên `#FEF2F2` | `--color-danger`, `--color-danger-subtle` |

Viền panel là trang trí phân vùng, không dùng thay viền nhận diện control. Input/focus có màu đậm hơn. Trạng thái chưa đủ dữ liệu dùng chữ trung tính, không dùng màu lỗi hoặc điểm 0 để kết luận năng lực.

### Chữ, kích thước và khoảng cách

| Thành phần | Quy tắc |
|---|---|
| Font UI | Be Vietnam Pro 400/500/600/700, fallback Arial/sans-serif; bản mẫu tự lưu font có giấy phép |
| H1 | 30px desktop, 26px mobile; weight600, line-height1.35 |
| H2/H3 | 22/18px; title của panel có thể18px theo phân cấp |
| Nội dung quản lý | 16px, line-height1.65; metadata/chú thích14px, bảng và form16px |
| Câu hỏi | 20px cho nội dung chính, 18px cho ngữ cảnh/đáp án; line-height1.8–1.85; MathJax giữ font toán chuyên dụng |
| Control | Chính46px; thao tác phụ38px desktop, tối thiểu44px mobile; label hiện hoặc có tên truy cập và tooltip ở rail |
| Spacing | 4,8,12,16,20,24,32,40,48px; tránh margin ad hoc cho cùng cấp nội dung |
| Radius | 4px badge, 8px control, 12px panel/dialog; avatar tròn |
| Shadow | Không dùng thường xuyên cho card; mềm cho dialog/toast hoặc toolbar nổi |
| Numeric | Tabular nums cho điểm, đếm, thời gian; căn phải trong cột số khi phù hợp |

## 3. Bố cục theo nhiệm vụ

| Archetype | Cấu trúc | Áp dụng |
|---|---|---|
| List management | Header + filter + table/list + footer pagination | Ngân hàng, đề, lớp, users, teacher list |
| Content workspace | Knowledge context hẹp + filter và câu hỏi rộng; độ phủ thu gọn | Chi tiết bank, phân loại |
| Form | Các nhóm thông tin có nhãn, form max760px, actions rõ | Profile, bank/course/user form, AI settings |
| Wizard | Stepper + vùng thao tác + review + receipt | Import, diagnostic; giữ trạng thái/revision hiện có |
| Editor | Vùng nội dung rộng + summary điểm/thông tin bên phải; actions cuối/nổi | Biên soạn đề |
| Focused learning | Header gọn, vùng đọc + điều hướng câu/tiến độ, không sidebar quản lý | Làm bài; ngữ cảnh standalone/diagnostic/practice |
| Evidence/report | Context lớp/học sinh → tổng quan → bằng chứng → giả thuyết/hành động | Kết quả, progress, AI reports |
| Standalone | Khung xác thực hoặc thông báo lỗi riêng, cùng token | Login/register/errors |

### Responsive

- Desktop từ1200px: sidebar104px với icon trắng, nhãn khi hover/focus; active dùng nền canvas và hai cung lõm. Khung ngoài12px, bo góc36px; header80px, gutter32px. Max-width nội dung1600px, vùng làm bài1240px; cột summary272–280px. Khi JavaScript tắt, sidebar mở rộng280px và hiện nhãn.
- Tablet768–1199px: sidebar drawer, gutter24px. Hai cột còn dùng nếu đủ chỗ cho câu hỏi/form, không giữ sidebar desktop bằng cách thu chữ.
- Mobile dưới768px: gutter16px, một cột, control44px. Knowledge context thành danh sách ngang có cuộn, không làm cả trang cuộn ngang.
- Bảng có `table-wrap` cuộn cục bộ; giữ nhãn cột. Không che cột hoặc cắt dữ liệu im lặng để vừa màn hình.
- Trong làm bài, summary/điều hướng chuyển lên trước câu hỏi trên mobile và không sticky che vùng trả lời. Sticky editor chuyển static trên mobile.
- Overlay/dialog có max-height theo viewport, vùng nội dung cuộn; trả focus về nút mở. Drawer có Escape, focus trap và background inert trong bản mẫu.

## 4. Thành phần và trạng thái

| Nhóm | Thiết kế | Hợp đồng/trạng thái |
|---|---|---|
| Button | Primary xanh, secondary trắng viền nhẹ, ghost cho thao tác phụ, danger cho xóa | Hover/focus/active/disabled/busy; label và icon không nhảy vị trí |
| Form | Label + control + hint/error; native fields khi phù hợp | Required, invalid, readonly, disabled, submit lỗi không mất nội dung |
| Tab | Underline xanh, count nhỏ; không dùng pill lớn | Selected + aria, roving focus/arrow/Home/End khi là tablist |
| Table | Header muted, hàng đủ padding, tên chính và metadata phụ | Rỗng/no-match/busy/error, số hàng/phạm vi chọn rõ |
| Question | Meta ngắn, vùng nội dung, câu trả lời/giải thích tách cấp | Ba hình thức mới; các nhánh đọc dữ liệu lịch sử cần giữ |
| Badge | Màu nhẹ, radius4, thông tin ngắn | Cùng trạng thái dùng cùng nhãn/màu; không gộp readiness/phân loại/quyền |
| Notice | Icon + lời nhắc có nghĩa, đặt sát vùng thao tác | Info/warning/success/error; thông báo lỗi dài cần đọc đủ |
| Dialog | Title, mô tả, body, hủy/xác nhận | Native dialog trong prototype; Escape/click ngoài/focus trap/return focus |
| Math/media | Vùng đọc đủ rộng, công thức/table cuộn cục bộ khi cần | Local MathJax, loading/fallback/retry; giữ ảnh câu hỏi và lời giải |
| Empty/loading/error | Giải thích theo ngữ cảnh, hành động phục hồi | Không biến tải lỗi thành empty hoặc thiếu bằng chứng thành yếu |
| Chart/report | Palette từ semantic, có số liệu/bảng hỗ trợ | Observed khác AI hypothesis, stale/failed vẫn xem được số liệu sẵn có |
| Print/export | Bề mặt trắng, ngắt trang phù hợp, ẩn điều hướng | Ma trận và Excel không đổi dữ liệu/điểm |

## 5. Những quyết định quan trọng từ Phase 1

1. Bank có general/research và quyền theo từng câu. Teacher có thể thêm câu riêng vào bank chung, nhưng không sửa câu chung. Admin dùng nhãn riêng tư của giáo viên, không phải “chỉ bạn”.
2. Chọn nhiều để tạo đề là nhiệm vụ của luồng tạo đề từ bank. Không thêm checkbox hàng loạt vào trang detail và coi là tính năng cũ.
3. Import cần đủ lỗi nội dung, gợi ý nhãn, dò trùng, đổi đích, receipt, lưu một phần và resume phiên. Prototype giữ hướng luồng; Phase 5 đã triển khai đủ và nghiệm thu các trạng thái này.
4. Editor cần lưu nháp/giao rõ và khóa khi nghiệp vụ yêu cầu. Prototype cho sửa nội dung/metadata/điểm mẫu; không tuyên bố đã hoàn tất bộ soạn đáp án hoặc ma trận thật.
5. Làm bài phân biệt ba ngữ cảnh; tiến độ Đúng/Sai có trạng thái một phần. Phase 6 đã triển khai tiến độ theo trường trả lời thật, xác nhận và xử lý gửi bài; Phase 7 kiểm chứng tích hợp với luồng học tập.
6. Mở lại đề chưa nộp chưa có nghĩa đã lưu đáp án. Không có autosave/khôi phục đáp án, reorder hay lịch giao mới trong đặc tả hiện có.
7. Không mở role manager/parent hoặc quyền tạo đầu vào cho teacher dựa trên dấu vết UI/test cũ.

## 6. Kiến trúc CSS khi triển khai sau duyệt

Đề xuất tách theo trách nhiệm, dùng CSS thuần tương thích Flask/Jinja:

```text
static/css/
  tokens.css           # primitive, semantic, component
  base.css             # reset, typography, focus, helpers
  shell.css            # navigation/header/responsive/print shell
  components.css       # buttons/forms/table/dialog/status/pagination
  question-content.css # question/answer/math/media/solution
  pages/               # chỉ layout riêng theo domain
```

Phase 3 đã tạo nền tảng và biến `main.css` thành điểm import duy nhất. Phase 4 đã tách bank-list/bank-form/knowledge, viết lại bank/ID6 CSS và gỡ các rule bank/catalog hết consumer trong CSS chung. Phase 5 đã thay import/composer và gỡ CSS/editor/scope cũ hết consumer. Phase 6 đã viết lại assessments/take/result, đưa style trang vào `pages/exam-taking.css` và `pages/exam-results.css`, bỏ 34 selector cũ khỏi `pages/workspaces.css`. Phase 7 đã thay toàn bộ nhóm học tập, bỏ 38 lượt selector cũ khỏi CSS chung, viết lại `learning.css` cho ma trận/audit, đưa biểu đồ về Chart.js cục bộ và palette token. Phase 8 đã thay dashboard/lớp/người dùng/AI, gỡ bridge `pages/workspaces.css` và chuyển phần công thức còn dùng sang `question-content.css`; gỡ bộ báo cáo nhúng cũ và dùng CSS trang riêng. Trách nhiệm và một nguồn token được giữ. Không import theme cũ vào nền tảng mới. Pages dùng chung components; không thêm rule `.btn` toàn cục vào CSS của một trang. Style động như chart/rule dữ liệu được chuyển có kiểm soát, không xóa bằng regex.

Phase 9 đã kiểm tra lại toàn bộ consumer, assets, script preview, tests và hướng dẫn; xóa template analytics bỏ dùng, alias chuyển tiếp và các preview/theme cũ; đưa UI của renderer công thức về token/native dialog. `neo-pop.css` và phần theme cũ của `main.css` không tồn tại như lớp dự phòng trong bản chạy cuối. Code nghiệp vụ/formula/API còn dùng được giữ.

## 7. Bằng chứng và trạng thái duyệt

- Bản mẫu tương tác: [prototype/index.html](prototype/index.html), chạy bằng [preview.py](preview.py). Không cần import Flask hoặc đọc dữ liệu thật.
- Đặc tả toàn bộ trang: [phase-2-screen-specs.md](../phase-2-screen-specs.md).
- Kết quả kiểm tra bản mẫu: [QA.md](QA.md), [qa.json](qa.json), ảnh trong [screenshots](screenshots/).
- Font/icon: [THIRD-PARTY.md](THIRD-PARTY.md). Không phụ thuộc CDN để xem prototype; MathJax/logo tham chiếu tài nguyên cục bộ hiện có.
- Kết quả tìm kiếm design-system tổng quát của ui-ux-pro-max có phần landing/dark không phù hợp. Không persist đầu ra đó. Đã tra cứu hẹp `minimal white dashboard --domain style` đúng category Minimalism & Swiss Style và `Be Vietnam Pro --domain google-fonts` đúng font có subset Vietnamese; điều chỉnh radius/palette theo brief. Skill design-system cung cấp token ba lớp và component/state spec, không yêu cầu đổi sang React hoặc thêm thư viện UI.
- Người dùng đã yêu cầu triển khai Phase 3–9; kết quả và phạm vi kiểm chứng ghi ở [báo cáo Phase 3](../phase-3/README.md) , [báo cáo Phase 4](../phase-4/README.md), [báo cáo Phase 5](../phase-5/README.md), [báo cáo Phase 6](../phase-6/README.md), [báo cáo Phase 7](../phase-7/README.md) và [báo cáo Phase 8](../phase-8/README.md). [Báo cáo Phase 9](../phase-9/README.md) ghi kết quả nghiệm thu toàn giao diện và đối chiếu các lỗi kiểm thử đã có trước thay đổi.
