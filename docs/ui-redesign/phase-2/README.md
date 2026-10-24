# Phase 2 · Bản thiết kế Modern White Academy

**Trạng thái: Phase 3–7 đã được người dùng yêu cầu và hoàn tất.** Ngày 14/10/2026. Thư mục này giữ bản thiết kế/prototype Phase 2; kết quả triển khai shell và tài khoản nằm trong [Phase 3](../phase-3/README.md), nhóm ngân hàng và kiến thức nằm trong [Phase 4](../phase-4/README.md), nhập và biên soạn đề nằm trong [Phase 5](../phase-5/README.md), quản lý kiểm tra/ma trận/làm bài/kết quả nằm trong [Phase 6](../phase-6/README.md), nhóm đầu vào/tự luyện/theo dõi nằm trong [Phase 7](../phase-7/README.md). Không có thao tác trên database, tài khoản hoặc bài làm thật.

## Xem bản mẫu

Từ thư mục gốc dự án:

```bash
python3 docs/ui-redesign/phase-2/preview.py --port 8765
```

Mở [bản mẫu ngân hàng](http://127.0.0.1:8765/prototype/index.html#bank), [quản lý đề](http://127.0.0.1:8765/prototype/index.html#assessments) hoặc [làm bài](http://127.0.0.1:8765/prototype/index.html#take).

Server chỉ nghe localhost và chỉ phục vụ bộ tài liệu/bản mẫu cùng tài nguyên logo/MathJax cần thiết. Không import Flask, không mở DB hoặc dùng `.env`. Font và icon được lưu cục bộ. Dừng server bằng Ctrl+C khi không cần xem.

Bản mẫu dùng JavaScript module nên cần xem qua server, không mở trực tiếp HTML bằng đường dẫn file.

## Những gì đã thiết kế

- **Hệ thống chung:** trắng/xám xanh nhạt, xanh học thuật, Be Vietnam Pro, token ba lớp, thành phần và trạng thái, responsive, accessibility và kiến trúc CSS đích.
- **8 khung xem tương tác:** danh sách ngân hàng, chi tiết ngân hàng, quản lý đề, biên soạn đề, làm bài, kết quả, thành phần và danh mục phạm vi thiết kế.
- **Biến thể trọng tâm:** bank research/general; teacher/admin và common/private; đề nháp/đã giao; làm bài standalone/đầu vào/tự luyện; câu chọn một/Đúng-Sai/trả lời ngắn.
- **Đặc tả toàn bộ:**32 template trang hoạt động, base, 12 component và6 template lỗi. Hai component không còn runtime được ghi hướng hợp nhất/dọn, không dựng lại để đủ số.
- **Kiểm tra bản mẫu:** kết quả và phạm vi cụ thể ở [QA.md](QA.md), dữ liệu kiểm tra ở [qa.json](qa.json), màu ở [contrast.json](contrast.json).

## Cách duyệt

1. Xem bố cục bank và mở “Đáp án và lời giải”; thử lọc và chuyển loại bank/ngữ cảnh quyền.
2. Xem danh sách đề, tab nháp/đã giao, editor và tổng điểm; thử lưu nháp/giao trong bản mẫu.
3. Làm đề minh họa 3 câu; thử trả lời Đúng/Sai một phần, xóa câu trả lời ngắn, nộp để xem kết quả tính từ câu vừa nhập.
4. Dùng bộ chọn Trạng thái để xem empty/loading/error; thu hẹp màn hình để xem mobile.
5. Đối chiếu nhóm màn hình còn lại trong [đặc tả toàn bộ](../phase-2-screen-specs.md).

Các thao tác chỉ thay dữ liệu trong bộ nhớ phiên xem, mất khi reload. Đồng hồ là minh họa cố định; không tạo đề, gửi bài, lưu điểm hoặc cập nhật hồ sơ thật. Bộ soạn mẫu chưa triển khai mọi trường đáp án/nhãn/ma trận và luồng import thật; các mục đó có đặc tả để thực hiện ở phase tương ứng.

## Tài liệu thiết kế

- [MASTER.md](MASTER.md): hướng thiết kế, token, thành phần, responsive và kiến trúc chuyển đổi.
- [tokens.css](tokens.css): primitive → semantic → component; nguồn token được đưa vào nền tảng chạy thật ở Phase 3.
- [Đặc tả từng màn hình](../phase-2-screen-specs.md): bố cục, states, quyền, hợp đồng và phase triển khai.
- [THIRD-PARTY.md](THIRD-PARTY.md): nguồn và giấy phép tài nguyên.
- [Ảnh kiểm chứng](screenshots/): desktop/mobile của các màn hình chính.

Phase 3–7 đã triển khai theo yêu cầu người dùng. Việc thay CSS/template thật và xóa giao diện cũ tiếp tục theo phase 8–9; prototype này giữ dữ liệu minh họa của Phase 2.
