# FNWEB2 — bản gọn đã tích hợp đề kiểm tra và ma trận

Ứng dụng hỗ trợ quản lý ngân hàng câu hỏi, kiểm tra trên lớp và luyện tập cá nhân hóa. Bản này giữ cấu trúc đã tinh gọn, bổ sung chức năng mới từ FNWEB2; không cần dịch vụ biên dịch LaTeX riêng.

Giao diện hiện tại dùng Modern White Academy với một bộ token, nền tảng và thành phần chung; font Be Vietnam Pro, biểu tượng, biểu đồ và công thức đều dùng tài nguyên cục bộ. Quy chuẩn được duyệt ở [MASTER](docs/ui-redesign/phase-2/MASTER.md); tiến độ, ảnh và kết quả nghiệm thu nằm trong [hồ sơ thiết kế lại](docs/ui-redesign/README.md). Tài liệu Phase 1–8 ghi lại từng mốc triển khai, không thay thế mã nguồn hiện tại.

## Bản đồ mã nguồn

| Vị trí | Trách nhiệm |
|---|---|
| `app.py`, `config.py`, `extensions.py` | Khởi tạo ứng dụng, cấu hình và phần mở rộng |
| `models.py`, `database.py` | Mô hình và kết nối dữ liệu |
| `routes/` | Quyền truy cập, nhận yêu cầu và trả giao diện |
| `services/` | Quy tắc nghiệp vụ, nhập LaTeX, phân loại, cá nhân hóa, báo cáo |
| `templates/` | Giao diện Jinja |
| `static/js/modules/`, `static/css/` | Tương tác và trình bày theo chức năng |
| `resources/assessment_matrix_template.xlsx` | Mẫu xuất ma trận Excel |
| `vendor/tex/`, `static/vendor/` | Tài nguyên TeX và thư viện trình duyệt chạy tại máy |
| `scripts/` | Chuẩn bị thư viện, kiểm tra và công cụ bảo trì |
| `tests/` | Kiểm thử nghiệp vụ và hồi quy |
| `docs/` | Giải thích cơ chế, hướng dẫn và kết quả kiểm chứng |

## Đề kiểm tra: đọc mã theo luồng

1. `routes/assessments.py`: nhập đề, tạo đề từ ngân hàng, lưu nháp, giao đề, xem và tải ma trận.
2. `services/assessment_bank.py`: chọn câu đủ điều kiện và đúng quyền truy cập.
3. `services/standalone_assessment.py`: duyệt nội dung, lưu bản đề và khóa sửa khi đã giao/có bài làm.
4. `services/assessment_scoring.py`: phân bổ tổng 10 điểm theo hình thức và trọng số câu; cung cấp điểm mặc định cho giao diện.
5. `services/assessment_matrix.py`: tổng hợp nhãn đã xác nhận và điểm từ đề đã lưu.
6. `services/matrix_xlsx.py`: xuất dữ liệu ra mẫu Excel bằng Open XML, không cần Microsoft Office.
7. `static/js/modules/assessment_editor.js`: xem trước khi nhập, lưu thay đổi và cập nhật liên kết ma trận.

Kết quả đề kiểm tra được theo dõi riêng; không tự cập nhật hồ sơ năng lực dùng sinh bài tự luyện. Nhãn kiến thức chưa xác nhận vẫn được thể hiện rõ trong ma trận, không tự gán vào tám dạng xác suất.

## Chạy và kiểm tra

Dùng môi trường Python của dự án và cài các gói trong `requirements.txt`. Cấu hình kết nối dữ liệu riêng trước khi chạy ứng dụng. Không chép đè tệp môi trường hoặc cơ sở dữ liệu từ bản khác.

```powershell
python -m pip install -r requirements.txt
npm ci
node scripts/build_local_assets.cjs
python scripts/check_local_tex.py
python app.py
```

Bản gọn chứa MathJax, Alpine, Lucide và Chart.js trong `static/vendor`, cùng font và giấy phép cục bộ. Chương trình chuẩn bị chỉ cập nhật MathJax/Alpine nếu có gói tương ứng trong `node_modules`, rồi kiểm tra tài nguyên bắt buộc. `node_modules` là thư viện được cài đặt, không phải mã nghiệp vụ để dọn thủ công. Sau khi đổi máy/vị trí Node, chạy lại lệnh build để cập nhật `.latex-node-path`.

Chỉ kiểm tra tài nguyên mà không sao chép thư viện hoặc ghi đường dẫn Node:

```powershell
node scripts/build_local_assets.cjs --check
```

Xem thử toàn bộ giao diện với DB bộ nhớ, thư mục tạm và tài khoản tổng hợp:

```powershell
python scripts/preview_ui_phase9.py --port 8771
```

Mở `http://127.0.0.1:8771/login`; đăng nhập `qa_admin`, `qa_teacher` hoặc `qa_student`, mật khẩu `Academy123!`. Bản xem thử không đọc `.env`/DB thật và không gọi nhà cung cấp AI. Các script `preview_ui_phase3.py` đến `preview_ui_phase8.py` được giữ để tái hiện fixture và QA từng mốc; giao diện luôn được render từ template hiện hành.

Chạy hồi quy bằng runner cô lập (DB bộ nhớ, thư mục tạm, không dotenv hoặc HTTP/socket):

```powershell
python scripts/test_ui_redesign.py
```

Kết quả và các failure đã có trước Phase 9 được ghi rõ trong [báo cáo nghiệm thu](docs/ui-redesign/phase-9/README.md); bộ nghiệp vụ toàn dự án chưa xanh hoàn toàn. Runner vẫn trả exit code lỗi, không bỏ qua các failure đó.

Kiểm thử trọng tâm qua cùng runner:

```powershell
python scripts/test_ui_redesign.py tests/test_assessment_scoring.py tests/test_assessment_matrix.py tests/test_standalone_assessment.py tests/test_personalization_v2.py -q
```

Xem [cơ chế điểm và ma trận](docs/assessment-scoring.md), [ghi nhận tích hợp](docs/integration-20260930.md). Các tài liệu giai đoạn cũ được giữ làm lịch sử; không coi mọi thông tin trong đó là trạng thái hiện tại.
