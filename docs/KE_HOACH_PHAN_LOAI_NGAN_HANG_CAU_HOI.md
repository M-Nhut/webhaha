# Phương án và kế hoạch phân loại ngân hàng câu hỏi

> Phạm vi vận hành hiện tại đã được thu hẹp theo `docs/LESSON4_SCOPE_CLEANUP.md`: chỉ giữ Chương 6 Bài 4 và tám mã `9C6-4-1`…`9C6-4-8`. Các đoạn dưới đây mô tả lịch sử thiết kế phạm vi rộng hơn và không còn là catalog hoạt động.

Ngày lập: 05/09/2026. Cập nhật: catalog vận hành đã thu hẹp còn 8 dạng Bài 4 (`9C6-4-1`…`9C6-4-8`) và cleanup local đã hoàn tất; xem `docs/LESSON4_SCOPE_CLEANUP.md`. **Giai đoạn 2 đã hoàn thành và kiểm tra local ngày 07/09/2026**: ba hình thức, bảng phạm vi file và lưu/khôi phục phiên; xem `docs/GIAI_DOAN_2_NGAN_HANG.md`. Các đoạn dưới đây mô tả lịch sử thiết kế rộng hơn và không phải danh mục hoạt động. Hợp đồng upload hiện hành chỉ nhận `.tex`/`.latex`; xem `docs/IMPORT_FORMATS.md`.

## 1. Phạm vi và quyết định đề xuất

1. Toàn bộ luồng tạo mới, nhập file, sửa câu và tạo đề mới chỉ sử dụng ba hình thức: Trắc nghiệm một đáp án, Đúng/Sai THPT, Trả lời ngắn.
2. Sau khi tải file lên, người dùng chọn phạm vi Lớp, Chương, Bài và Chủ đề trong một bảng. Hệ thống tự chọn dạng bài và mức độ cho từng câu trong phạm vi đó.
3. Giữ cấu trúc ID6 hiện hành; giao diện hiển thị NB–TH–VD–VDC, mã dùng N–H–V–C. Dấu `?` trong danh mục người dùng cung cấp là vị trí mức độ chưa xác định.
4. Phạm vi tự phân loại hiện tại là Toán 9, Chương 6, Bài 4, gồm 8 dạng theo danh mục được giữ lại. Dữ liệu Bài 1–3 và câu hỏi/đề/lịch sử ngoài phạm vi không còn được seed hoặc tái tạo.
5. Kết hợp quy tắc xác định với mô hình AI đọc nội dung toán học. Câu đủ căn cứ được tự gán; câu thiếu dữ liệu, mâu thuẫn hoặc khó phân biệt được đưa vào danh sách cần kiểm tra.
6. Giáo viên có thể import để bổ sung câu vào một ngân hàng có sẵn. Hệ thống dò trùng trong ngân hàng đích và trong chính file trước khi tự phân loại; chỉ rõ số câu bị trùng, loại chúng khỏi danh sách thêm mới. Câu không trùng tiếp tục tự phân loại → xem kết quả → lưu vào ngân hàng đã chọn.

“Đúng/Sai THPT” được hiểu là hình thức câu có bốn mệnh đề a–d, áp dụng được cho nội dung Toán 9; yêu cầu này không đồng nghĩa mở rộng danh mục sang lớp 10–12. “Trắc nghiệm” được hiểu là bốn lựa chọn A–D và một đáp án đúng.

## 2. Kết quả khảo sát hệ thống

| Thành phần | Hiện trạng | Việc cần bổ sung |
|---|---|---|
| `services/question_normalizer.py` | Hỗ trợ năm hình thức; câu thiếu mức độ được đặt Nhận biết | Chính sách ba hình thức; tách giá trị mặc định cũ khỏi mức độ được xác định có căn cứ |
| `services/question_validator.py` | Một số lỗi đáp án hiện chỉ là cảnh báo; Đúng/Sai chưa buộc đủ bốn ý | Kiểm tra thống nhất trước khi câu được dùng trong đề |
| Dò trùng khi import | Đã so sánh văn bản với ngân hàng đích nếu có `bank_id`, nhưng chỉ cảnh báo; bước lưu vẫn nhận câu có cảnh báo | Dò trùng có tham chiếu câu nguồn/câu đích, loại câu trùng khỏi phân loại và lưu, kiểm tra lại trong giao dịch lưu |
| Import vào ngân hàng có sẵn | Trang chi tiết đã có liên kết import mang `bank_id` | Giữ ngân hàng đích xuyên suốt phiên; hiển thị rõ tên ngân hàng; đổi đích phải dò trùng lại |
| `templates/question_bank_import.html` | Có tải file, phân tích, xem trước, xác nhận; chưa có bảng phạm vi cho file | Thêm chọn phạm vi và xem trước phân loại |
| `models.py` | Có `CurriculumNode`, `ImportSession`, `BankQuestion`; chủ đề chủ yếu là chuỗi văn bản | Lưu phạm vi của lần nhập, kết quả tự phân loại, nguồn kết quả và lịch sử sửa |
| `services/id6_service.py` | Đã có sinh mã, bộ đếm giao dịch, chống trùng; còn hỗ trợ TL | Tái sử dụng bộ cấp số; tách đọc mã cũ với chính sách chỉ cấp mới D/T/S |
| `services/id6_metadata.py` | Đọc ID có sẵn và bổ sung metadata | Phân biệt ID nguồn, đề xuất tự động, kết quả giáo viên duyệt; tránh ghi đè khi tải lại preview |
| `app.py`, trang phân loại | Gán lớp/chương/bài/dạng/mức độ thủ công, có thao tác hàng loạt | Thêm tác vụ tự phân loại và duyệt các câu cần kiểm tra |
| `services/data/math9_curriculum.json` | Catalog hoạt động chỉ còn 8 mục Bài 4; dữ liệu Bài 1–3 đã cleanup | Dùng danh mục đúng yêu cầu và cleanup có backup khi nâng dữ liệu cũ |

Lúc khảo sát ban đầu, cơ sở dữ liệu local chưa có câu trong `bank_question`; Chương 6 có 24 nút danh mục phiên bản `math9-user-v2`. Giai đoạn 1 đã chuyển 24 nút local này sang `math9-c6-v4`; 148 dạng ngoài Chương 6 và 21 bảng dữ liệu khác không đổi. Đây chỉ là hiện trạng local, không suy ra dữ liệu của môi trường triển khai.

Các tài liệu và kiểm thử hiện có bảo vệ luồng đọc LaTeX, ảnh và công thức. Đặt bộ phân loại sau bước trích xuất; các parser DOC/DOCX/PDF và MathType trước đây đã được loại khỏi luồng hoạt động.

## 3. Luồng sử dụng

**Mở ngân hàng → Import thêm câu hỏi → tải file/chọn phạm vi → dò trùng và loại câu trùng → tự phân loại câu mới → xem kết quả → lưu vào ngân hàng đó.**

Việc đọc tài liệu có thể bắt đầu ngay khi tải lên. Tác vụ phân loại chỉ bắt đầu sau khi người dùng lưu phạm vi và hệ thống kiểm tra trùng. Khi nhập vào ngân hàng mới, bước dò trùng vẫn kiểm tra các câu lặp trong file.

### Import bổ sung vào ngân hàng có sẵn

Tại trang chi tiết ngân hàng, nút **Import thêm câu hỏi** mở luồng nhập với ngân hàng đích được chọn sẵn và tên ngân hàng luôn hiển thị. Xác nhận cuối cùng lưu vào chính ngân hàng này. Nếu người dùng chủ động đổi ngân hàng đích, hệ thống kiểm tra quyền và chạy lại dò trùng trước khi tiếp tục; không dùng kết quả dò của ngân hàng trước.

Phạm vi dò là toàn bộ câu trong ngân hàng đích, kể cả câu nháp chưa được phân loại, cùng các câu trong file đang nhập. Không chỉ dò ở chương/bài đã chọn vì câu cũ có thể chưa có hoặc có sai metadata. Câu giống nhau nằm ở ngân hàng khác không tự bị loại khỏi ngân hàng đang chọn.

### Bảng thông báo câu trùng

| Vị trí trong file | Kết quả đối chiếu | Xử lý |
|---|---|---|
| Câu 3 | Trùng với câu có ID `9C8Ni-1T.15` trong ngân hàng đích | Bỏ qua, không thêm |
| Câu 8 | Trùng với Câu 2 trong cùng file | Bỏ qua bản lặp; Câu 2 tiếp tục nếu hợp lệ |
| Câu 12 | Gần giống một câu trong ngân hàng, nhưng còn khác dữ kiện | Cần đối chiếu trước khi quyết định |

Đây là ví dụ minh họa. Mỗi dòng cho mở nội dung hai câu để đối chiếu; câu đã có trong ngân hàng được dẫn bằng ID ổn định hoặc mã nội bộ nếu chưa có ID6. Số câu nguồn lấy theo nhãn trong tài liệu, kèm phần/trang hoặc thứ tự trích xuất khi cần. Nếu tài liệu đánh lại số ở mỗi phần, hiển thị như “Phần II — Câu 3”; không đánh số lại sau khi lọc khiến giáo viên tìm nhầm câu.

Thông báo ví dụ: **“Đọc 50 câu. Bỏ qua 8 câu trùng: 3, 8, 12, 19, 25, 31, 40, 47. Còn 42 câu mới chuyển sang tự phân loại.”** Với lô có câu lỗi hoặc cần đối chiếu, báo riêng các nhóm và số còn chờ, không tính tất cả chúng là câu mới sẵn sàng lưu.

Câu trùng vẫn xuất hiện trong báo cáo của lần nhập nhưng không được gửi sang tự phân loại, không cấp ID6 và không tạo bản ghi câu hỏi mới. Nếu toàn bộ file bị trùng, thông báo “Không có câu mới để thêm”, giữ báo cáo và kết thúc mà không gọi AI hoặc tăng bộ đếm ID. Bước dò là tự động, không buộc giáo viên xác nhận riêng mỗi câu trùng đã xác định chắc chắn.

### Quy tắc xác định trùng

- **Trùng chắc chắn:** cùng nội dung bài toán sau chuẩn hóa an toàn, gồm ngữ cảnh, câu dẫn, hình thức, dữ kiện số/công thức, bảng/hình và tập phương án hoặc mệnh đề. Bỏ qua khác biệt trình bày, số thứ tự câu và ID nguồn. Bản lặp trong file chỉ giữ một bản đại diện đủ dữ liệu để đi tiếp; nếu chưa có bản đủ dữ liệu thì nhóm chờ kiểm tra.
- **Đổi thứ tự đáp án:** có thể coi là trùng khi các lựa chọn độc lập và giữ nguyên nội dung; không tự đảo/chuẩn hóa thứ tự nếu đề hoặc phương án tham chiếu A/B/C/D, “ý trên” hoặc vị trí cụ thể. Khóa đáp án được đối chiếu theo nội dung, không theo chữ cái sau khi hoán vị.
- **Cùng câu, khác đáp án/lời giải:** không coi là câu mới chỉ vì khác khóa đáp án hay lời giải. Đánh dấu trùng kèm xung đột nếu đáp án mâu thuẫn, không thêm và không tự sửa câu đã lưu; hiển thị khác biệt để giáo viên xử lý câu gốc riêng.
- **Nghi trùng:** câu diễn đạt gần giống hoặc hình/công thức chưa đối chiếu được chỉ được đánh dấu để xem hai bản. Câu xác nhận trùng bị bỏ qua; câu xác nhận khác mới đi tiếp. Các câu rõ ràng khác vẫn tiếp tục mà không chờ cả lô.
- **Không trùng:** cùng dạng hoặc cùng câu chữ khuôn mẫu nhưng khác số liệu, điều kiện, yêu cầu, hình/bảng hoặc phương án có ý nghĩa. Không loại chỉ vì cùng ID, cùng từ khóa hay điểm tương đồng văn bản cao.

Chuẩn hóa cần giữ dấu âm, dấu bất đẳng thức, số mũ, phân số, đơn vị và dấu tiếng Việt có ý nghĩa; không dùng phép xóa dấu câu/ký hiệu toán hiện tại làm bằng chứng đủ để tự loại. Hình và công thức được đối chiếu bằng nội dung/tài sản chuẩn hóa, không bằng URL hay UUID tạm vốn có thể đổi qua mỗi lần nhập. Khi tài sản chưa đọc hoặc chuẩn hóa được, kết quả cần kiểm tra thay vì đoán trùng.

Sau khi giáo viên sửa nội dung/đáp án trong preview, dò lại câu đó và các bản lặp liên quan trước khi phân loại hoặc lưu. Nếu sửa làm thay đổi nội dung bài toán, kết quả phân loại cũ cũng hết hiệu lực. Kiểm tra lại với trạng thái mới nhất của ngân hàng trong cùng giao dịch ghi để chặn câu vừa được người khác thêm sau lúc xem trước. Báo cáo cuối phân biệt số thực sự đã thêm và số bị bỏ qua lúc lưu; bấm lưu lặp hoặc thử lại sau lỗi mạng không thêm lần hai.

### Bảng chọn phạm vi file

| Tệp | Lớp | Chương | Bài | Chủ đề |
|---|---|---|---|---|
| `ngan_hang_chuong_6.docx` | Lớp 9 | Chương 6 — Một số yếu tố thống kê và xác suất | Tất cả bài / chọn nhiều bài | Thống kê và xác suất |

- Lựa chọn chương phụ thuộc lớp; lựa chọn bài phụ thuộc chương. Đổi cấp cha thì xóa lựa chọn con không còn hợp lệ.
- Cho chọn nhiều chương/bài nếu tệp là ngân hàng tổng hợp. Không ép tất cả câu vào một bài chỉ vì dùng chung tệp.
- Chủ đề là nhãn nội dung, tách khỏi dạng bài. Bài 4 dùng một chủ đề chung **Thống kê và xác suất**, bao gồm 8 dạng retained.
- Dạng bài không bắt buộc người dùng chọn tại bước này. Có thể thu hẹp đến một dạng khi biết chắc toàn bộ tệp cùng dạng.
- Nếu chỉ chọn Chương 6, hệ thống chỉ tìm trong 8 dạng Bài 4. Câu ngoài phạm vi được báo rõ và không tự gán ID.
- Phạm vi được lưu theo phiên nhập; khi lưu, từng câu nhận chương/bài/chủ đề của chính nó. Không ghi đè chủ đề của các câu cũ trong ngân hàng đích.

### Bảng kết quả theo câu

| Câu | Hình thức | Bài | Dạng được nhận diện | Mức độ | ID dự kiến | Trạng thái |
|---|---|---|---|---|---|---|
| 1 | Trắc nghiệm | §4 | Viết tập hợp không gian mẫu | NB | `9C8Ni-1T.1` | Đã tự phân loại |
| 2 | Đúng/Sai THPT | §4 | Tung đồng xu | VD | `9C8Vi-3D.1` | Đã tự phân loại |
| 3 | Trả lời ngắn | §3 | Chưa xác định do thiếu bảng dữ liệu | Chưa xác định | Chưa cấp | Cần kiểm tra |

Các dòng trên chỉ minh họa giao diện, không phải kết quả phân loại câu thực tế. ID xem trước chưa giữ chỗ; số chính thức được cấp khi lưu.

Mỗi dòng cho mở nội dung, hình/bảng, đáp án, giải thích ngắn về phân loại và phương án thay thế. Có lọc theo bài, dạng, NB–TH–VD–VDC và trạng thái; cho sửa từng câu hoặc áp dụng cho các câu đã chọn. Không yêu cầu giáo viên duyệt lại từng câu đã đạt điều kiện tự gán.

Phân biệt ba trạng thái độc lập: chất lượng nhập tài liệu, kết quả dò trùng và chất lượng phân loại. Câu đọc đủ nội dung vẫn có thể chưa xác định được mức độ. Chỉ câu đã xác định không trùng mới được lưu mới; cho lưu nháp các câu này khi còn cần kiểm tra đáp án/phân loại, nhưng chưa cấp ID chính thức hoặc đưa vào bộ chọn đề tự động cho đến khi đủ điều kiện. Câu trùng hoặc chưa giải quyết nghi trùng không được lưu thành bản nháp mới trong ngân hàng.

## 4. Chính sách ba hình thức

| Hình thức hiển thị | Giá trị lưu | Mã ID | Điều kiện được sử dụng trong đề |
|---|---|---|---|
| Trắc nghiệm | `single` | T | Đủ bốn lựa chọn A–D, đúng một đáp án đúng |
| Đúng/Sai THPT | `true_false` | D | Đủ bốn mệnh đề a–d, từng mệnh đề có đáp án đúng/sai |
| Trả lời ngắn | `short_answer` | S | Có trường trả lời ngắn và đáp án chấp nhận; quy tắc tương đương số/chữ được xác định rõ |

Áp dụng cùng một cấu hình loại được phép ở giao diện, API thêm/sửa, nhập file, cấp ID, thống kê, xuất mẫu và tạo đề. Chuẩn hóa bí danh cũ `truefalse` thành `true_false`.

File có câu tự luận hoặc nhiều đáp án vẫn được nhận diện để báo lỗi đúng vị trí. Người dùng sửa về một hình thức hợp lệ hoặc loại khỏi lô nhập. Không tự biến bài chứng minh/vẽ hình thành trả lời ngắn và không tự bỏ bớt đáp án đúng.

Dữ liệu cũ thuộc hai loại bị bỏ được giữ để tra cứu, giữ nguyên trong đề/bài làm lịch sử; loại khỏi nguồn tạo đề mới. Mã TL cũ vẫn đọc được để đối chiếu, nhưng không cấp mới. Việc chuyển câu cũ phải kiểm tra nội dung và cấu trúc đáp án.

Một số dạng trong danh mục có từ “vẽ”. Vẫn giữ các dạng đó như yêu cầu, nhưng chỉ nhận câu được biên soạn theo ba hình thức cho phép. Yêu cầu tự vẽ một biểu đồ hoàn chỉnh không thể tự động coi là câu trả lời ngắn.

## 5. Danh mục Chương 6 đã chuẩn hóa

**Tên chương:** Một số yếu tố thống kê và xác suất. Phạm vi hoạt động hiện tại có **8 dạng Bài 4** (`9C6-4-1`…`9C6-4-8`). Các bảng mô tả §1–§3 bên dưới chỉ là lịch sử thiết kế, không được seed.

### §1. Mô tả và biểu diễn dữ liệu trên các bảng, biểu đồ

| Dạng | Mẫu mã | Tên dạng |
|---|---|---|
| 1 | `9C6?1-1` | Biểu diễn dữ liệu trên bảng thống kê, biểu đồ tranh |
| 2 | `9C6?1-2` | Biểu diễn dữ liệu trên biểu đồ cột, biểu đồ cột kép |
| 3 | `9C6?1-3` | Biểu diễn dữ liệu trên biểu đồ đoạn thẳng |
| 4 | `9C6?1-4` | Biểu diễn dữ liệu trên biểu đồ hình quạt tròn |

### §2. Tần số. Tần số tương đối

| Dạng | Mẫu mã | Tên dạng |
|---|---|---|
| 1 | `9C6?2-1` | Xác định tần số của một giá trị |
| 2 | `9C6?2-2` | Lập bảng tần số của mẫu dữ liệu |
| 3 | `9C6?2-3` | Vẽ biểu đồ tần số |
| 4 | `9C6?2-4` | Xác định tần số tương đối của một giá trị |
| 5 | `9C6?2-5` | Lập bảng tần số tương đối của mẫu dữ liệu |
| 6 | `9C6?2-6` | Vẽ biểu đồ tần số tương đối |

### §3. Tần số ghép nhóm. Tần số tương đối ghép nhóm

| Dạng | Mẫu mã | Tên dạng |
|---|---|---|
| 1 | `9C6?3-1` | Xác định tần số ghép nhóm của một nhóm |
| 2 | `9C6?3-2` | Lập bảng tần số ghép nhóm của mẫu dữ liệu |
| 3 | `9C6?3-3` | Vẽ biểu đồ tần số ghép nhóm |
| 4 | `9C6?3-4` | Xác định tần số tương đối ghép nhóm của một nhóm |
| 5 | `9C6?3-5` | Lập bảng tần số tương đối ghép nhóm của mẫu dữ liệu |
| 6 | `9C6?3-6` | Vẽ biểu đồ tần số tương đối ghép nhóm |

### §4. Phép thử ngẫu nhiên và không gian mẫu. Xác suất của biến cố

| Dạng | Mẫu mã | Tên dạng |
|---|---|---|
| 1 | `9C6?4-1` | Viết tập hợp không gian mẫu của một phép thử |
| 2 | `9C6?4-2` | Xác định số phần tử của không gian mẫu của một phép thử |
| 3 | `9C6?4-3` | Tính xác suất của biến cố trong trò chơi Tung đồng xu |
| 4 | `9C6?4-4` | Tính xác suất của biến cố trong trò chơi Gieo xúc sắc |
| 5 | `9C6?4-5` | Tính xác suất của biến cố trong trò chơi Vòng quay số |
| 6 | `9C6?4-6` | Tính xác suất của biến cố trong trò chơi Rút thẻ từ trong hộp |
| 7 | `9C6?4-7` | Tính xác suất của biến cố trong phép thử viết số tự nhiên |
| 8 | `9C6?4-8` | Tính xác suất của biến cố trong trò chơi chọn một đối tượng trong một nhóm đối tượng |

## 6. Cách tự phân loại

### Đầu vào và thứ tự xử lý

1. Nhận các câu đã qua bước dò trùng và đủ điều kiện phân loại; đọc nội dung đã trích xuất, ngữ cảnh, các lựa chọn/mệnh đề, đáp án, lời giải và dữ liệu hình/bảng liên quan. Tách độ tin cậy đọc tài liệu khỏi độ tin cậy phân dạng và mức độ.
2. Nhận diện hình thức bằng cấu trúc đáp án và quy tắc ba loại. Nếu cấu trúc mâu thuẫn, yêu cầu kiểm tra thay vì dùng AI tự tạo hoặc sửa đáp án.
3. Dùng phạm vi người dùng chọn để lấy danh sách dạng hợp lệ. Quy tắc nhận diện tín hiệu hỗ trợ thu hẹp: “ghép nhóm”, khoảng lớp, phần trăm, đối tượng ngẫu nhiên, loại biểu đồ và yêu cầu cần trả lời.
4. Mô hình phân tích yêu cầu toán học, chọn một dạng chính trong danh mục, đề xuất mức độ và nêu căn cứ ngắn. Đầu ra theo cấu trúc cố định; máy chủ kiểm tra mã có tồn tại, còn hoạt động và thuộc phạm vi.
5. Chỉ áp dụng tự động khi cả dạng và mức độ đạt điều kiện đã kiểm chứng. Các ca ngoài danh mục, thiếu hình/bảng, mâu thuẫn đáp án hoặc không đủ căn cứ trả về trạng thái cần kiểm tra.
6. Bộ sinh ID6 hiện có nhận kết quả đã chấp nhận và cấp số khi lưu. AI không tự tạo chuỗi ID hay số thứ tự.

Không chỉ nhìn từ khóa bối cảnh. Ví dụ, câu tung đồng xu yêu cầu **viết không gian mẫu** thuộc §4 dạng 1; chỉ khi yêu cầu **tính xác suất** trong bối cảnh đó mới thuộc dạng 3. Câu có biểu đồ cột nhưng yêu cầu xác định tần số không tự động thuộc §1 dạng 2.

Giáo viên đã sửa và khóa một nhãn thì tác vụ chạy lại không ghi đè nhãn đó. ID có sẵn trong file được giữ như dữ liệu nguồn; khi trái phạm vi hoặc nội dung thì hiển thị xung đột. Tag không rõ phiên bản danh mục không được coi là nhãn chắc chắn.

### Tiêu chí mức độ đề xuất

Đây là bộ tiêu chí vận hành ban đầu cần thống nhất bằng câu mẫu, không phải tuyên bố về một quy định thi chính thức.

| Mức độ | Tiêu chí | Ví dụ định hướng |
|---|---|---|
| NB | Nhận diện khái niệm hoặc đọc trực tiếp dữ kiện đã biểu diễn | Đọc tần số của một giá trị từ bảng cho sẵn |
| TH | Giải thích, chuyển biểu diễn hoặc tính trực tiếp trong tình huống quen thuộc | Từ bảng tần số tính tỉ lệ phần trăm của một giá trị |
| VD | Chọn và kết hợp kiến thức để xử lý tình huống có nhiều bước | Lập không gian mẫu, chọn các kết quả thuận lợi rồi tính xác suất |
| VDC | Có suy luận bổ sung, ràng buộc không hiển nhiên hoặc tình huống ít quen thuộc | Suy ra dữ kiện còn thiếu từ nhiều điều kiện trước khi giải bài xác suất/thống kê |

Xét yêu cầu thực tế và kiến thức học sinh cần huy động, không lấy độ dài câu, số lớn hay số bước làm quy tắc quyết định duy nhất. Một dạng có thể xuất hiện ở nhiều mức; không ép mỗi dạng phải có đủ bốn mức.

Với Đúng/Sai, lưu mức đề xuất cho từng ý a–d. Quy ước ban đầu cho ID toàn câu là mức cao nhất trong các ý bắt buộc, đồng thời cho giáo viên điều chỉnh. Với câu có nhiều dạng, lưu một dạng chính và các dạng phụ trong metadata; nếu không xác định được dạng chính thì chuyển kiểm tra.

### Đánh giá chất lượng

- Chuẩn bị khoảng 80–160 câu mẫu có nhãn giáo viên, phủ 8 dạng Bài 4, các mức độ thực tế, ba hình thức và ca có hình/bảng. Dùng người thứ hai đối chiếu các ca khó hoặc bất đồng mức độ.
- Tách tập hiệu chỉnh và tập đánh giá độc lập; các câu gần giống nhau thuộc cùng một nhóm để tránh kết quả đánh giá quá lạc quan.
- Báo riêng độ chính xác dạng, mức độ, cặp dạng–mức độ, tỉ lệ tự gán và tỉ lệ chuyển kiểm tra. Không dùng điểm trích xuất mặc định hiện có làm độ tin cậy phân loại.
- Mục tiêu thí điểm đề xuất: ít nhất 95% cặp dạng–mức độ đúng trong phần được tự gán trên tập đánh giá độc lập. Đây là tiêu chí cần đo, chưa phải năng lực đã đạt. Luôn báo kèm số mẫu và độ phủ tự động để tránh đạt mục tiêu bằng cách chỉ xử lý vài câu dễ.
- Ngưỡng tự gán được chọn từ kết quả hiệu chỉnh; điểm AI tự báo không được hiểu trực tiếp là xác suất đúng. Nếu chưa đạt mục tiêu, vận hành ở chế độ gợi ý và tiếp tục hiệu chỉnh.

## 7. Quy tắc ID và chuyển danh mục

Giữ mẫu: `{lớp}C{chương}{mức}{bài}-{dạng}{hình thức}.{số thứ tự}`.

Ví dụ `9C8Hi-4T.15`: lớp 9, chương 8, bài kết hợp i, TH, dạng 4, trắc nghiệm, số thứ tự 15. NB → N; TH → H; VD → V; VDC → C. Hình thức T/D/S độc lập với mức độ.

Tiếp tục dùng số thứ tự chung trong một lớp/chương/bài/dạng, xuyên các ngân hàng, không tách theo hình thức hoặc mức độ. Đổi mức độ trong cùng dạng giữ số; đổi dạng cấp số ở dạng đích. Sắp xếp giao diện theo thứ tự NB → TH → VD → VDC bằng thứ hạng riêng, không sắp xếp chuỗi ID theo bảng chữ cái.

Việc đổi danh mục cần một migration rõ ràng, vì `canonical_code` đang duy nhất và `catalog_version` hiện chưa tạo được các bộ mã song song. Hàm seed hiện chỉ tự cập nhật bản `math9-v1`; sửa JSON đơn thuần sẽ không cập nhật các nút `math9-user-v2` đang tồn tại.

Đề xuất chuyển sang một danh mục Chương 6 hoạt động duy nhất, có lưu snapshot danh mục cũ và lịch sử phân loại:

1. Kiểm kê câu, nút danh mục, bộ đếm và các tham chiếu ở môi trường đích; chạy thử migration trên bản sao dữ liệu.
2. Lưu mã cũ, phiên bản, tên dạng cũ, nhãn mức độ và liên kết câu để đối chiếu. Không chỉ giữ `original_source_id`, vì một mã cũ có thể mang ý nghĩa khác mã mới.
3. Lập bảng đối chiếu theo ý nghĩa. Mục tương đương rõ có thể chuyển trực tiếp; mục rộng hoặc khác nghĩa phải phân loại lại theo nội dung.
4. Tạm khóa tác vụ cấp ID Chương 6 trong bước chuyển dữ liệu, đánh dấu câu bị ảnh hưởng là cần kiểm tra, cập nhật nút danh mục và đồng bộ ID bằng bộ cấp số hiện có. Với câu chưa phân loại lại được, giữ mã cũ trong lịch sử và không trình bày nó như ID thuộc danh mục mới.
5. Bảo toàn số đã sử dụng và ràng buộc chống trùng; có bảng ánh xạ mã trước/sau, kiểm tra tham chiếu và phương án phục hồi bản sao nếu migration lỗi. Không sửa nội dung đề hoặc bài làm đã lưu.

Ví dụ dễ gây nhầm: mã bài 2, dạng 2 trước đây là “Tần số tương đối”, trong danh mục mới là “Lập bảng tần số”. Không thể chỉ đổi tên nút mà giữ nguyên phân loại các câu đã gắn vào đó.

## 8. Thiết kế kỹ thuật cần thực hiện

| Hạng mục | Thiết kế đề xuất |
|---|---|
| Chính sách hình thức | Một cấu hình dùng chung cho D/T/S; bộ đọc dữ liệu lịch sử vẫn hiểu loại cũ |
| Phạm vi nhập | `ImportSession` lưu lớp, tập chương/bài/chủ đề, phiên bản danh mục và phiên bản nội dung preview |
| Ngân hàng đích và vị trí nguồn | Lưu `bank_id` xuyên suốt phiên, khóa định danh từng dòng nhập, nhãn câu gốc, phần/trang hoặc thứ tự trích xuất; không dùng chỉ số sau lọc để nhận diện câu |
| Dịch vụ dò trùng | Thêm `services/question_duplicate_service.py`; chuẩn hóa nội dung có phiên bản, tạo fingerprint, truy tìm câu ứng viên trong ngân hàng đích và đối chiếu đầy đủ; so gần đúng chỉ đưa ra nghi trùng |
| Kết quả dò trùng | Lưu `duplicate_status`, `matched_question_id` hoặc khóa dòng trong file, căn cứ, phiên bản nội dung và ngân hàng đã đối chiếu; phân biệt `new`, `duplicate_bank`, `duplicate_file`, `needs_review` |
| Chặn ghi câu trùng | Backend chọn đúng các dòng đủ điều kiện, kiểm tra lại trong giao dịch đồng bộ theo ngân hàng trước khi tạo câu/cấp ID. Mọi đường ghi vào ngân hàng dùng cùng quy tắc đồng bộ để không lọt hai bản giống nhau do đồng thời |
| Tối ưu đối chiếu | Lập chỉ mục fingerprint theo ngân hàng; bổ sung fingerprint cho câu cũ và cập nhật khi sửa. Ca gần giống được thu hẹp ứng viên; không so mọi cặp bằng AI. Không tự xóa các bản trùng đã tồn tại từ trước |
| Lưu lặp và báo cáo | Phiên xác nhận có cơ chế chỉ ghi một lần, lưu kết quả cuối để trả lại khi retry; báo số thêm mới, trùng, lỗi và chờ kiểm tra; giữ báo cáo câu trùng sau khi dọn file tạm |
| Metadata phân loại | Lưu dạng chính/phụ, mức độ, trạng thái, nguồn nhãn, căn cứ, điểm đánh giá riêng, phiên bản mô hình/quy tắc, thời gian và người sửa |
| Câu chưa phân loại | Mức độ có thể chưa xác định; luồng thống kê/tạo đề dựa trên trạng thái để không coi mặc định NB là nhãn thật |
| Dịch vụ phân loại | Thêm `services/question_classification_service.py`; tách khỏi parser và bộ sinh ID |
| Cấu hình sư phạm | Thêm dữ liệu tiêu chí nhận diện, loại trừ và câu mẫu cho 8 dạng Bài 4; không hard-code toàn bộ trong giao diện |
| Tác vụ nền | Lưu trạng thái chờ/chạy/xong/lỗi; xử lý theo lô nhỏ, có giới hạn thời gian và số lần thử lại; giao diện hiển thị tiến độ thực tế |
| Chống kết quả cũ | Kết quả gắn với hash nội dung, phạm vi và phiên bản danh mục; người dùng sửa câu khi tác vụ chạy thì không áp dụng kết quả cũ |
| Chạy lại | Chỉ chạy câu thay đổi hoặc câu được chọn; giữ nhãn giáo viên đã khóa; tránh lặp chi phí trên cùng nội dung |
| Lưu kết quả | Bảo toàn metadata khi normalize/sửa preview; truyền rõ sang `BankQuestion`, không chỉ suy ngược từ chuỗi ID |
| API | Bổ sung lưu phạm vi/ngân hàng đích, đọc kết quả dò trùng, giải quyết nghi trùng, bắt đầu phân loại, đọc tiến độ và duyệt kết quả; kiểm tra quyền sở hữu phiên/ngân hàng, CSRF và phiên hết hạn |
| Xử lý lỗi AI | Giữ kết quả đọc tài liệu; cho thử lại hoặc gán thủ công; không rơi về NB khi dịch vụ lỗi |

Dùng adapter cho nhà cung cấp AI để có thể cấu hình mô hình và giới hạn chi phí mà không thay đổi luồng nhập. Khả năng đọc hình/bảng phải được kiểm thử với tài liệu thực tế; ảnh hoặc công thức chưa đọc được sẽ làm câu cần kiểm tra. Nội dung file chỉ là dữ liệu, không phải chỉ dẫn được phép thay đổi nhiệm vụ hoặc mã danh mục.

## 9. Các giai đoạn triển khai

Ước lượng cập nhật **10–15 ngày làm việc cho một lập trình viên**, gồm thêm 2–3 ngày cho dò trùng và tích hợp chặn ghi so với kế hoạch 8–12 ngày ban đầu, với giả định đã có dịch vụ AI dùng được và bộ câu mẫu được chuẩn bị kịp. Chưa tính thời gian chờ thống nhất nhãn chuyên môn hoặc bổ sung OCR cho tài liệu scan chưa đọc được. Thời gian phần dò trùng cần rà lại nếu phải nhận diện tương đương giữa nhiều kiểu ảnh/công thức chưa chuẩn hóa được.

| Giai đoạn | Công việc | Đầu ra/điều kiện hoàn thành | Dự kiến |
|---|---|---|---|
| 1. Chốt dữ liệu và chuyển đổi | Chuẩn hóa 8 dạng Bài 4, chủ đề, tiêu chí mức độ; kiểm kê dữ liệu; thiết kế cleanup và backup | Danh mục đúng 8 mã; cleanup chạy thử không đổi sai nghĩa câu Bài 4 | 1–2 ngày |
| 2. Ba hình thức và bảng phạm vi | Thống nhất D/T/S từ API đến UI, mẫu DOCX; lưu phạm vi theo file; xử lý loại cũ | Chỉ ba lựa chọn tạo mới; tải lại vẫn giữ phạm vi; file nhiều bài hoạt động | 2 ngày |
| 2a. Import bổ sung và dò trùng | Giữ ngân hàng đích; fingerprint và đối chiếu nội dung; báo số câu trùng; xử lý nghi trùng; kiểm tra lại khi lưu và chống retry ghi lặp | Câu trùng bị loại trước phân loại, số câu nguồn truy ngược đúng, hai lượt nhập đồng thời không tạo bản trùng | 2–3 ngày |
| 3. Bộ phân loại | Quy tắc, adapter AI, dữ liệu đầu ra, tác vụ nền, trạng thái chưa xác định, per-statement cho Đúng/Sai | Chạy được 8 dạng Bài 4; có căn cứ và trạng thái kiểm tra; không mặc định NB | 2–3 ngày |
| 4. Duyệt và cấp ID | Bảng kết quả, sửa hàng loạt, khóa nhãn giáo viên, ID xem trước và lúc lưu, sắp xếp mức độ | Duyệt xong lưu đúng mã, không trùng, không mất sửa khi chạy lại | 1–2 ngày |
| 5. Đánh giá và phát hành | Đánh giá tập độc lập; kiểm thử nhập/chấm/tạo đề; thử migration; thí điểm Chương 6 | Báo cáo chất lượng/độ phủ, hồi quy đạt, có phương án quay lại | 2–3 ngày |

Giai đoạn 2 triển khai sau khi cấu trúc dữ liệu được chốt; giai đoạn 2a là cổng đầu vào cho tự phân loại và lưu. Giai đoạn 3 có thể hiệu chỉnh trên tập câu mẫu trong khi hoàn thiện UI; giai đoạn 4 phụ thuộc hợp đồng đầu ra của bộ phân loại và kết quả dò trùng. Chỉ bật tự gán rộng sau khi giai đoạn 5 đạt tiêu chí.

Kết quả đã triển khai: giai đoạn 1, giai đoạn 2, giai đoạn 2a, giai đoạn 3, giai đoạn 4 và khung đánh giá của giai đoạn 5 hoàn tất trên môi trường local. Giai đoạn 2a dò trùng toàn ngân hàng đích và trong file, giữ vị trí nguồn, có đối chiếu thủ công cho ca chưa chắc chắn, kiểm tra lại trong giao dịch ghi và biên nhận chống ghi lặp. Giai đoạn 3 gợi ý dạng/mức độ có căn cứ và fingerprint, chuyển ca mơ hồ sang kiểm tra thay vì đặt mặc định NB. Giai đoạn 4 bổ sung lọc, xác nhận nhiều gợi ý và khóa nhãn giáo viên, đồng thời kiểm tra fingerprint trước khi áp dụng. Giai đoạn 5 đo độ đúng dạng/mức độ/cặp nhãn, độ phủ và câu lặp trước khi mở rộng tự gán. Xem `docs/GIAI_DOAN_2A_DO_TRUNG_NGAN_HANG.md`, `docs/GIAI_DOAN_3_TU_PHAN_LOAI.md`, `docs/GIAI_DOAN_4_DUYET_PHAN_LOAI.md` và `docs/GIAI_DOAN_5_DANH_GIA_THI_DIEM.md`. Chưa có tập nhãn giáo viên độc lập đủ 240 câu nên cổng chất lượng vẫn chưa đạt và không bật tự gán rộng.

Giai đoạn 6 đã đưa luồng thí điểm vào giao diện: xuất gói nhãn mù từ ngân hàng, tải lại JSON đã được gán nhãn và xem kết quả cổng chất lượng. Xem `docs/GIAI_DOAN_6_VAN_HANH_THI_DIEM.md`. Việc mở rộng tự gán vẫn phụ thuộc dữ liệu nhãn thật, không được suy ra từ dữ liệu mẫu.

## 10. Tiêu chí nghiệm thu

- Tạo/nhập/sửa câu và tạo đề mới chỉ nhận ba hình thức; gọi API trực tiếp cũng không tạo được loại ngoài phạm vi.
- Mẫu DOCX tải xuống có đúng ba hình thức; dữ liệu và đề lịch sử vẫn đọc được.
- Mọi file có bảng chọn chương/bài/chủ đề; hỗ trợ nhiều bài, đổi phạm vi và tải lại trang không mất lựa chọn.
- Mở import từ một ngân hàng có sẵn tự chọn đúng ngân hàng; quyền ghi được kiểm tra ở upload, đổi đích, preview và lưu. Đổi ngân hàng đích bắt buộc dò trùng lại.
- Dò toàn bộ ngân hàng đích và trong file, kể cả câu cũ chưa có ID/chương/bài; không loại vì giống câu ở một ngân hàng khác.
- Báo đúng nhãn/số câu gốc và câu đích trùng, kể cả tài liệu đánh lại số theo phần hoặc một số câu bị loại/sửa trong preview; người dùng mở được hai bản để đối chiếu.
- Câu trùng chắc chắn không gọi AI phân loại, không được lưu mới hoặc cấp ID. File 100% trùng thêm 0 câu; nhập lại cùng file thêm 0 câu; bản lặp trong file chỉ có một bản đại diện được thêm.
- Có ca khác số liệu, dấu âm, bất đẳng thức, số mũ, phương án hoặc hình nhưng giống câu chữ để bảo đảm không bị loại nhầm; ca đảo đáp án độc lập được đối chiếu đúng, ca có tham chiếu vị trí không bị chuẩn hóa sai.
- Cùng câu khác khóa đáp án được báo xung đột và không tạo bản mới; không ghi đè đáp án/lời giải câu gốc. Ảnh/công thức đổi URL/UUID vẫn được đối chiếu qua nội dung nếu đủ dữ liệu.
- Câu nghi trùng phải có kết quả đối chiếu trước khi lưu; không chặn các câu mới khác của lô. Sửa nội dung trong preview làm chạy lại kiểm tra trùng và vô hiệu kết quả phân loại đã cũ khi cần.
- Kiểm tra hai phiên nhập đồng thời và thao tác thêm/sửa khác: câu phát sinh trùng sau preview bị bỏ qua khi lưu, báo đúng số thực thêm; bấm xác nhận lặp hoặc retry sau lỗi mạng không nhân bản câu.
- Danh mục Chương 6 đúng toàn bộ 8 mã/tên Bài 4; seed/cleanup chạy lại không nhân bản hoặc tái tạo dữ liệu ngoài phạm vi.
- Không phân loại chỉ theo từ khóa: có ca cùng bối cảnh nhưng khác yêu cầu; có ca tần số/tần số tương đối và dữ liệu ghép nhóm dễ nhầm.
- NB–TH–VD–VDC được xác định từ tiêu chí, có căn cứ; câu thiếu mức độ không tự thành NB. Câu ngoài danh mục hoặc thiếu hình/bảng được báo đúng.
- Đúng/Sai giữ bốn ý và đáp án từng ý; kiểm tra mức từng ý và quy tắc tổng hợp toàn câu.
- Metadata không mất qua sửa preview, refresh, retry, xác nhận nhập; giáo viên sửa khi tác vụ chạy không bị ghi đè.
- ID dự kiến và ID chính thức dùng cùng bộ sinh; lưu đồng thời không cấp trùng; đổi mức giữ số trong cùng dạng; đổi dạng cấp số đúng phạm vi.
- Câu chưa đủ đáp án hoặc chưa phân loại chỉ lưu nháp, không lọt vào bộ chọn đề tự động. Thống kê phân biệt rõ “chưa xác định” với NB.
- DOC/DOCX/PDF/TEX giữ nội dung, bảng/hình, công thức và đáp án qua toàn bộ luồng nhập. Ca scan chưa đọc được báo trạng thái rõ.
- Thử quyền giáo viên, phiên hết hạn, AI lỗi/timeout, gửi lặp yêu cầu và hai người lưu đồng thời; kiểm tra cả SQLite và PostgreSQL nếu môi trường triển khai dùng PostgreSQL.
- Báo cáo độ chính xác dạng, mức độ, cặp nhãn và độ phủ tự động trên tập đánh giá độc lập trước khi bật tự gán.

Khi triển khai, chạy các bộ kiểm thử nhập file, công thức, ID6 và phân loại hiện có trên cơ sở dữ liệu kiểm thử riêng; bổ sung kiểm thử hành vi cho ba hình thức, phạm vi file, dò trùng ngân hàng/nội bộ file, kết quả AI lỗi và chuyển danh mục. Các kiểm thử cũ kỳ vọng tạo mới `essay` cần đổi theo chính sách mới, đồng thời giữ ca đọc dữ liệu lịch sử.
