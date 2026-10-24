# Phase 3 · Shell, tài khoản và trang lỗi

**Hoàn tất ngày 14/10/2026**, theo yêu cầu “Thực hiện phase 3” và “tiếp tục hoàn thành phase3”. Tài liệu này giữ kết quả tại mốc Phase 3. Nhóm ngân hàng/kiến thức đã tiếp tục hoàn tất ở [Phase 4](../phase-4/README.md); trạng thái mới nhất ghi tại [kế hoạch chung](../README.md).

## Kết quả

| Nhóm | Thay đổi |
|---|---|
| Nền tảng | Một nguồn token ba lớp; nền trắng/xám, xanh học thuật, Be Vietnam Pro local; button, input, table, panel, badge và flash chung |
| Shell | Sidebar 240px, header 64px, điều hướng theo admin/teacher/student; drawer dưới 1200px, gutter 32/24/16px; skip link, Escape, focus trap, trả focus và background inert |
| Đăng nhập/đăng ký | Khung xác thực mới, trường luôn có nhãn, nhóm thông tin rõ, hiện/ẩn mật khẩu, lỗi tại trường và summary dẫn đến trường; giữ WTForms, CSRF, native POST và URL `next` |
| Hồ sơ | Nhận diện tài khoản, panel thông tin và bảo mật; preview ảnh, trạng thái chọn ảnh, lỗi trường, kiểm tra mật khẩu nhập lại; giữ hai form độc lập và tên submit hiện có |
| Trang lỗi | Bố cục gọn cho 400/403/404/405/429/500 và fallback; phục hồi điều hướng, thông tin kỹ thuật thu gọn, sao chép mã tham chiếu và fallback thủ công |
| Tài nguyên | Font và Lucide local, avatar fallback mới; bỏ tải Google Fonts, Lucide CDN và HTMX không còn consumer |

Thông báo quan trọng ở lại đến khi người dùng đóng. Toggle mật khẩu chỉ xuất hiện khi JavaScript hoạt động. Menu vẫn truy cập được khi tắt JavaScript. Mô tả lỗi mặc định của Werkzeug được hiển thị bằng tiếng Việt; thông báo riêng từ server và phản hồi JSON giữ nguyên.

## Kiến trúc và dọn mã cũ

`static/css/main.css` đã thay hoàn toàn nội dung theme cũ và trở thành điểm import:

```text
tokens.css → base.css → components.css → shell.css → pages/workspaces.css
```

`auth.css`, `profile.css`, `errors.css` chỉ định nghĩa bố cục riêng. `learning.css` không còn định nghĩa lại sidebar/header/mobile shell. Các tham chiếu `--pop-*` và `--ink` trong hai CSS domain đã chuyển sang semantic token mới để không phụ thuộc Neo Pop.

Đã xóa các file hết consumer trong phạm vi chuyển đổi:

- `static/css/neo-pop.css`
- `static/css/login.css`
- `static/images/pop-avatar.svg`
- `static/images/pop-study.svg`

Không giữ bản CSS cũ dưới tên backup trong ứng dụng, không import Neo Pop làm lớp dự phòng. Các tên token phổ biến còn có consumer (`--accent`, `--text-1`, `--surface-1`…) trỏ về cùng hệ thống semantic mới, không chứa palette cũ.

`pages/workspaces.css` hỗ trợ bố cục của các template còn hoạt động trong lúc chuyển đổi. Các CSS/template nghiệp vụ riêng và style inline của bank, import, kiểm tra, học tập, quản trị/báo cáo tiếp tục được thay ở phase 4–8. Dashboard chỉ chuyển các consumer của theme chung và heading; chưa nghiệm thu như bản thiết kế Phase 8. Tài liệu theme cũ là lịch sử, không tải vào web; rà soát tài liệu/preview/assets toàn cục thuộc Phase 9.

## Kiểm chứng

| Kiểm tra | Kết quả |
|---|---|
| Tích hợp Phase 3 và error contract hiện có | **18/18 đạt** với CSRF bật và DB trong bộ nhớ |
| Chrome trên ứng dụng thật, dữ liệu giả | **175/175 đạt**; dữ liệu từng mục ở [browser-qa.json](browser-qa.json) |
| Responsive | 375/768/1024/1440px cho login/register/profile/404; 375/1440px cho home, bank list/detail, courses, assessments; student practice ở 375px |
| Runtime | Không JS exception, không request font/script ngoài localhost trong phiên kiểm tra; icon/ảnh đầy đủ, MathJax local render khi câu vào viewport |
| Tĩnh | 52 template parse được; 5 JS ứng dụng mới/thay đổi và script QA kiểm tra syntax; không CSS variable thiếu định nghĩa hoặc tham chiếu runtime tới asset/theme đã xóa |
| Phạm vi dữ liệu/mã | Backend không đổi so với mốc trước Phase 3; `formula_renderer.js` không đổi; metadata DB thật giữ nguyên. Xem [integrity-qa.json](integrity-qa.json) |

Kiểm tra trình duyệt bao gồm POST thật cập nhật hồ sơ/đổi mật khẩu, đăng nhập sai/đúng, avatar preview hợp lệ/không hợp lệ, flash close, password mismatch, drawer hai chiều Tab/Escape/scrim/resize/link, role navigation, error status/JSON/copy/back và fallback không JavaScript. Trường đăng ký đã được chỉnh để các control cùng chiều cao khi hint khác nhau; drawer đã được sửa để nhận focus ngay lúc mở.

Các kiểm thử chức năng bổ sung cho bank list, learning workspace và luồng làm/nộp/xem bài luyện có **6 đạt, 3 chưa đạt** trong môi trường cô lập. Ba mục chưa đạt được chạy lại với `base.html` tối giản, không có shell/CSS/JS Phase 3, và vẫn có cùng kết quả:

| Test hiện có | Kết quả quan sát |
|---|---|
| `test_shared_detail_is_read_only_in_the_rendered_page_and_js_config` | Mong nhãn “Import câu riêng”; template hiện có dùng “Nhập câu riêng”. Quyền `canEdit: false`, `canAdd: true` vẫn đúng. |
| `test_observed_error_detail_is_readable_without_writing_profile` | HTTP 200 nhưng fixture observation không hiện chữ “Cần đối chiếu” theo kỳ vọng test. |
| `test_force_keeps_completed_snapshot_and_new_roster_changes_it` | Report từ cấu hình/provider mock có trạng thái `failed`, test mong `completed`; xảy ra trước render UI. |

Code bank/detail, teacher detail, services và các test đó không thay trong Phase 3. Không sửa test hoặc nới hợp đồng nghiệp vụ để che các kết quả này. Đối chiếu contract ở phase 4/7/8; chưa tuyên bố toàn bộ test suite của dự án đạt.

## Xem giao diện và chạy lại

```bash
python3 scripts/preview_ui_phase3.py --port 8766
```

Mở [đăng nhập](http://127.0.0.1:8766/login). Tài khoản minh họa: `qa_teacher`, `qa_student`, `qa_admin`; mật khẩu chung `Academy123!`. Preview không đọc `.env`/`.env.local`, dùng SQLite trong bộ nhớ, upload trong thư mục tạm, không nạp khóa provider. Dữ liệu này mất khi dừng server; không phải tài khoản thật.

```bash
python3 -m pytest tests/test_ui_redesign_phase3.py tests/test_error_pages.py -q
PLAYWRIGHT_MODULE=/path/to/playwright node scripts/qa_ui_phase3.cjs
```

Script browser cần Playwright và Google Chrome đã có; đặt `PLAYWRIGHT_MODULE` tới module trên máy hoặc bỏ biến khi module ở Node resolution path. Browser QA chạy sau khi khởi động preview, lưu ảnh và JSON vào thư mục này. Test tích hợp tự vô hiệu hóa dotenv trước import app và chặn DB khác `sqlite:///:memory:`.

## Ảnh nghiệm thu

| Trang | Desktop | Mobile |
|---|---|---|
| Đăng nhập | [1440px](screenshots/login-1440.png) | [375px](screenshots/login-375.png) |
| Đăng ký | [1440px](screenshots/register-1440.png) | [375px](screenshots/register-375.png) |
| Hồ sơ và shell | [1440px](screenshots/profile-1440.png) | [375px](screenshots/profile-375.png) |
| Lỗi 404 | [1440px](screenshots/error404-1440.png) | [375px](screenshots/error404-375.png) |
| Dashboard trong shell mới | [1440px](screenshots/home-1440.png) | [375px](screenshots/home-375.png) |

Font Be Vietnam Pro lấy từ bộ Phase 2, giấy phép tại `static/fonts/be-vietnam-pro/OFL.txt`. Lucide 1.8.0 từ runtime cục bộ, ISC license tại `static/vendor/lucide/LICENSE`; avatar fallback dùng node paths của Lucide UserRound. MathJax/Alpine/logo giữ tài nguyên local hiện có.

Phase kế tiếp theo kế hoạch là **Phase 4: toàn bộ ngân hàng câu hỏi, soạn câu, phân loại, catalog và classification evaluation**, đủ general/research và quyền common/private/overlay.
