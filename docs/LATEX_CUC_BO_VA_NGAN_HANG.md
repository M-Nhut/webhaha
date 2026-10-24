# Nhập LaTeX cục bộ và tổ chức ngân hàng câu hỏi

## Những gì đã thay đổi

FNWEB2 mặc định xử lý hình TikZ bằng bộ TeX WebAssembly chạy trong một tiến trình Node trên chính máy chạy Flask. Không cần dựng thêm website, khai báo API hoặc gửi đề đến dịch vụ render. MathJax và Alpine được sao chép vào thư mục static của ứng dụng. Việc tải thư viện diễn ra khi cài đặt; biên dịch hình sau đó không cần kết nối dịch vụ bên ngoài.

Đây là dùng thư viện mã nguồn mở cài tại máy, không phải tự xây dựng lại toàn bộ trình biên dịch TeX. Các chức năng AI và các tài nguyên giao diện khác của ứng dụng có cấu hình mạng riêng; thay đổi này không có nghĩa toàn bộ ứng dụng đã hoạt động ngoại tuyến.

Ngân hàng được tổ chức theo **dạng kiến thức → mức độ → loại câu hỏi**. Tiêu đề dạng căn giữa; mỗi bảng có bốn mức nhận thức và ba cột Trắc nghiệm, Đúng/Sai, Trả lời ngắn. Mỗi ô cho biết tổng số câu và số sẵn sàng. Câu sẵn sàng phải được giáo viên duyệt, đủ điều kiện chấm và không bị loại khỏi luyện tập. Số lượng được tính sau khi kiểm tra quyền xem, nên không tiết lộ câu riêng của giáo viên khác.

## Cách sử dụng

1. Mở ngân hàng, chọn ô tương ứng với dạng, mức độ và loại câu cần bổ sung.
2. Chọn **Nhập câu hỏi** để gõ/dán văn bản thông thường; không cần biết LaTeX. Có thể nhập 1/2, ×, ÷, ≤, ≥. Người biết LaTeX có thể nhập `$\frac{1}{2}$` và dùng nút xem trước.
3. Nhập đáp án. Đúng/Sai cho phép chỉnh dạng và mức nhận thức của từng ý; mặc định cùng nhãn với câu. Trả lời ngắn cần chọn chấm số/phân số hoặc văn bản và sai số cho phép.
4. Đọc bản xem trước, xác nhận đã kiểm tra và lưu. Câu hợp lệ được duyệt để thuật toán sử dụng ngay. Câu trùng nội dung và đáp án không được lưu thêm; nếu cùng nội dung nhưng khác đáp án, hệ thống yêu cầu kiểm tra câu hiện có.
5. Hoặc chọn **Nhập từ file .tex** tại nhóm đang xem. Dạng và mức độ được điền cho câu thiếu nhãn; nhãn đã có trong file được giữ lại. Loại câu luôn đọc theo cấu trúc đáp án trong file, không ép toàn bộ file thành loại của ô đang chọn.
6. Xem trước hình/công thức, kiểm tra nhãn và báo cáo trùng, rồi xác nhận nhập. Câu có lỗi vẫn cần sửa trước khi dùng.

Mẫu thử gồm cả ba loại câu, hình TikZ và bảng: `docs/examples/nhap_cau_hoi_tikz.tex`. Mẫu này không cần ID6. Các mã trong file cũ vẫn được đọc làm metadata tương thích, không phải điều kiện bắt buộc để nhập câu mới.

## Cài đặt và kiểm tra

Trên máy hiện tại, các phụ thuộc Node và tài nguyên web đã được cài và build trong FNWEB2. Khởi động lại Flask theo cách đang sử dụng và tải lại trang để nhận các thay đổi.

Khi chuyển sang máy khác, cài Node.js, mở terminal trong FNWEB2 và chạy:

```powershell
npm install
npm run build
```

Nếu dùng pnpm, chạy `pnpm install --frozen-lockfile` rồi `pnpm build`. `pnpm-lock.yaml` ghi phiên bản phụ thuộc dùng cho bản kiểm thử. Không cần TeX Live, Docker hoặc API renderer cho các cấu trúc mà bộ TeX tích hợp hỗ trợ.

Lệnh build lưu đường dẫn Node đang dùng vào `.latex-node-path` (tệp cục bộ, không đưa vào Git), giúp Flask tìm được Node khi PATH của Python khác PATH của terminal. Khi chuyển máy hãy build lại. Có thể cấu hình `LATEX_NODE_BINARY` để chỉ định Node riêng.

Kiểm tra độc lập, không mở cơ sở dữ liệu hoặc đọc `.env`:

```powershell
.\.venv\Scripts\python.exe scripts/check_local_tex.py
```

Các biến dịch vụ cũ `LATEX_RENDERER_URL`, `LATEX_RENDER_MODE` không còn được sử dụng. Luồng chạy hiện tại chỉ gọi bộ TeX cục bộ.

## Phạm vi hỗ trợ và giới hạn

- Đọc cấu trúc `ex`, `bt`, `question`, `bai`, các lệnh `\choice`, `\choiceTF`, `\shortans`, `\loigiai` đã có trong trình nhập. Công thức được tách khỏi văn bản trước khi làm sạch định dạng.
- Đã kiểm thử thực tế hình TikZ có đường vẽ, mũi tên, hình tròn, hình xúc xắc và nhãn toán học; bảng `tabular` được đọc thành hàng/cột và hiển thị bằng bảng HTML, với MathJax cho công thức trong ô. Hỗ trợ chữ tiếng Việt, cột l/c/r/p/m/b, lặp cột và `\multicolumn`. Cấu trúc ngoài phạm vi này được chuyển sang bộ TeX để thử biên dịch, không tự bỏ nội dung.
- Font của SVG được nhúng ngay trong tệp, nên hình không phụ thuộc font từ một website khác.
- **Không đồng nghĩa hỗ trợ mọi gói và mọi cú pháp LaTeX.** Các gói không có trong bản TeX WebAssembly, PSTricks, macro riêng phức tạp hoặc chữ tiếng Việt chưa được hỗ trợ trong nhãn TikZ có thể biên dịch lỗi. Văn bản tiếng Việt bên ngoài hình hiển thị bình thường. Không tự bỏ dấu hoặc dựng hình gần đúng rồi coi là đúng.
- Khi không biên dịch được, giữ mã nguồn, báo lỗi và trạng thái cần kiểm tra. Một hình biên dịch được cũng vẫn cần giáo viên kiểm tra nội dung toán học; cờ kỹ thuật `verified` không chứng minh tính đúng của đề.
- Cài đặt ban đầu cần Internet để tải thư viện. Các gói được khóa: node-tikzjax 1.0.5, MathJax 3.2.2, Alpine 3.14.0. `static/vendor` và `node_modules` là tệp sinh khi cài/build, không đưa vào Git.

## Cấu trúc triển khai

```text
File .tex
  → tách câu và đáp án theo cấu trúc đề
  → tách hình/bảng trước khi làm sạch văn bản
  → Flask → tiến trình Node → TeX WebAssembly trong hệ thống tệp bộ nhớ
  → kiểm tra SVG, loại nội dung chủ động/liên kết ngoài, nhúng font
  → lưu ảnh SVG cục bộ theo mã băm nội dung + phiên bản renderer
  → xem trước → dò trùng → giáo viên duyệt → ngân hàng
```

Mỗi tiến trình có hạn thời gian 40 giây; Node giới hạn heap V8 384 MB (không phải hạn tổng RAM của tiến trình). Hệ thống tệp TeX là bộ nhớ của thư viện, không cung cấp tệp học sinh hay `.env` cho TeX. Đây là các biện pháp trong bản chạy cục bộ; triển khai công khai nhiều người dùng cần bổ sung hàng đợi và giới hạn tài nguyên ở hệ điều hành.

Lỗi xuống dòng bảng đã sửa: thao tác làm sạch trước đây có thể biến `\\` thành `\` trước dấu cách. Nay hình/bảng được trích trước và công thức được giữ nguyên trước khi chuẩn hóa văn bản.

## Kiểm thử

`tests/test_local_tex_bank.py` kiểm tra biên dịch TeX thật, SVG an toàn, bỏ mặc định gửi đến URL cũ, lọc theo nhóm, duyệt nhập thủ công, gắn nhãn từng ý Đúng/Sai, chặn đáp án số không hợp lệ, nhập file có ba loại câu/hình/bảng và nhập lại không tạo câu trùng. Dữ liệu dùng SQLite trong bộ nhớ, không dùng dữ liệu học sinh thật.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_local_tex_bank.py tests/test_personalization_v2.py -q
```

Một số bộ kiểm thử lịch sử đang không khớp ứng dụng trước đợt chỉnh này: `test_import_duplicates.py` dùng chương 6/bài 4 và quy trình xác nhận cũ; `test_route_contract.py` có snapshot thiếu các route đã tồn tại. Không hạ yêu cầu duyệt hoặc quyền truy cập để làm các test đó qua. Kết quả kiểm thử theo phạm vi được ghi trong `docs/reports`; không coi đó là xác nhận toàn bộ test cũ đều đạt.

Nguồn thư viện: [node-tikzjax](https://github.com/prinsss/node-tikzjax), [MathJax — lưu và phục vụ bản cục bộ](https://docs.mathjax.org/en/v3.2/web/hosting.html). Phần mới dùng để báo cáo khóa luận nên đặt trọng tâm ở thuật toán chọn câu, kiểm soát lặp và bằng chứng năng lực trong `CA_NHAN_HOA_V2_KHOA_LUAN.md`; tích hợp TeX là cải tiến kỹ thuật và tính thuận tiện, không tự nó chứng minh tính mới khoa học.

## Tinh chỉnh hiển thị ngày 25/09/2026

- Bảng đã lưu với trạng thái lỗi của dịch vụ cũ được đọc lại từ mã nguồn khi hiển thị; không cần sửa dữ liệu học sinh hoặc nhập lại câu chỉ để phục hồi bảng được hỗ trợ.
- Lệnh dàn trang như `\small` và `\renewcommand{\arraystretch}{...}` không còn xuất hiện trong văn bản. Mã nguồn gốc của bảng/hình vẫn được giữ.
- Lời giải có tiêu đề riêng ở đầu, chữ 17 px, bảng căn giữa và cuộn ngang khi màn hình hẹp. Thiết lập độ khó/ưu tiên được thu gọn và giải thích ngay tại câu.
- Màn hình nhập có bộ lọc Câu mới / Câu trùng / Cần đối chiếu; đối chiếu mở ngay tại câu, không còn bảng trùng dài phía trên.
- Nhập thủ công có bản xem trước công thức tự cập nhật và ảnh PNG/JPG/WebP tối đa 5 MB, 16 triệu điểm ảnh. Ảnh được kiểm tra, bỏ metadata và căn giữa.
- Kiểm thử bổ sung: `tests/test_latex_display_v3.py`. Xem giao diện hiện tại bằng dữ liệu tổng hợp trong DB bộ nhớ và thư mục tạm: `python scripts/preview_ui_phase9.py --port 8771`, rồi mở `http://127.0.0.1:8771/login`. Tài khoản `qa_admin`, `qa_teacher`, `qa_student` dùng mật khẩu `Academy123!`; bản xem thử chặn gọi mạng và không đọc tài liệu cá nhân trong uploads.

Các số liệu đọc được hoặc biên dịch thành công là kiểm chứng kỹ thuật, không phải đánh giá hiệu quả sư phạm hay độ đúng toán học.

## Khắc phục nhập lặp và hình cũ

Bộ dò trùng chuẩn hóa token toán học: bỏ lệnh cỡ ngoặc và giãn cách, giữ nguyên số, toán tử, thứ tự phần tử và ranh giới lệnh. Không dùng độ giống văn bản để tự gộp hai công thức khác dữ kiện. Lời giải không quyết định danh tính câu; đáp án khác vẫn phải đối chiếu.

`\immini[thm]{...}{...}` được tháo bố cục trước khi tách đáp án; hình vẫn được giữ khi `\choiceTF` nằm bên trong cột văn bản. Các định nghĩa màu ở trong câu được chuyển cùng hình đến bộ TeX. Hình lỗi từ dịch vụ cũ được thử biên dịch cục bộ khi mở; kết quả được lưu bộ nhớ đệm. Hình lỗi do cú pháp/gói không hỗ trợ vẫn báo lỗi, không tự dựng hình gần đúng.

Dữ liệu cũ đã bị bộ đọc trước đây cắt mất mã hình không thể phục hồi chỉ từ phần văn bản còn lại. Với những câu đó cần dùng lại file nguồn; kiểm tra hình ở bản xem trước trước khi lưu. Không sửa hàng loạt dữ liệu học sinh để che lỗi.

Mã phụ trách: `latex_parser.py` đọc cấu trúc, `tex_table.py` đọc bảng, `latex_renderer.py` quản lý biên dịch/bộ nhớ đệm, `local_tex.py` giới hạn tiến trình và kiểm tra SVG, `formula_display.py` phục hồi hiển thị cũ. Đã bỏ các nhánh gọi API và bộ vẽ gần đúng khỏi renderer đang chạy. Dịch vụ renderer cũ được chuyển vào `legacy/latex_renderer_service/`, giữ nguyên các thay đổi trước đó để tra cứu; không thuộc luồng chạy của web.

### Kết quả kiểm tra thực tế

D1: 14 câu, 4 bảng. D2: 40 câu, 23 bảng. D5: 6 câu, 3 bảng, 6 hình. Không còn lỗi biên dịch trong ba file đã kiểm tra. Sáu hình D5 tải ngay khi mở bản xem trước và căn giữa; nhãn “Tấm bìa A/B” giữ dấu bằng các lệnh dấu TeX tương đương. Đây chưa phải hỗ trợ đầy đủ mọi chữ Unicode hoặc mọi thư viện TikZ.

Đối chiếu chỉ đọc file D1 với nội dung ngân hàng hiện tại tìm được đủ 14 danh tính trùng. Hai trường hợp trước đây bị lọt chỉ khác `\left`, `\right` hoặc khoảng cách `\ ` trong công thức. Không thay đổi dữ liệu ngân hàng trong bước kiểm tra này.
