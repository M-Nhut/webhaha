# Phase 2 · Kiểm chứng bản mẫu

Ngày: 14/10/2026. **Kết quả bản mẫu: đạt trong phạm vi kiểm tra dưới đây.** Đây là QA của prototype độc lập, không phải kết quả kiểm thử ứng dụng Flask hoặc xác nhận thiết kế đã được người dùng duyệt.

## 1. Môi trường và kết quả

- Chrome headless qua Playwright có sẵn, hồ sơ tạm tách khỏi browser cá nhân.
- Máy chủ `preview.py` chỉ nghe `127.0.0.1`, phục vụ proposal và MathJax/logo cục bộ; không import ứng dụng hoặc dùng database.
- **30 kiểm tra tương tác/điều kiện đạt**; **32 kiểm tra bố cục đạt** = 8 khung xem × 4 chiều rộng 1440/1024/768/375px.
- Mỗi khung xem có một H1, font Be Vietnam Pro đã tải, document không rộng hơn viewport; bảng rộng cuộn trong wrapper.
- Không có page error, asset HTTP lỗi trong luồng kiểm tra hoặc request ra bên ngoài. Request thử `/.env` được server trả 404 theo thiết kế.
- **10 cặp màu đạt** ngưỡng đặt: 9 cặp chữ tối thiểu 4,5:1; viền control trên surface tối thiểu 3:1.
- Checksum **313 file ứng dụng hiện có không đổi** so với trước Phase 2; không import theme cũ vào prototype. Đặc tả không thiếu 32 page active, 12 component hoặc 6 error template.

Dữ liệu: [qa.json](qa.json), [contrast.json](contrast.json). Kết quả là lần chạy cuối sau sửa; các số đo là kiểm tra prototype, không đại diện dữ liệu hay hiệu năng thật.

## 2. Các nhóm tương tác đã kiểm tra

| Nhóm | Nội dung đã kiểm tra |
|---|---|
| Quyền bank | Teacher chỉ sửa 2 câu overlay riêng trong bank chung; admin sửa 5 câu demo; general bank riêng có nội dung sửa được |
| Bank tabs/filter | Bàn phím chuyển tab và giữ focus; common scope 3 câu; từ khóa không khớp có empty state |
| Nội dung toán | MathJax local render công thức; font UI local tải được |
| Dialog | Mở thêm câu native modal; Escape đóng; focus trả về nút mở |
| Quản lý đề | Tab nháp còn 2 hàng; tìm không khớp hiển thị empty state |
| Editor | Lưu nháp có phản hồi; tổng điểm sai bị chặn; giao demo khóa input trong editor |
| Làm bài | Một ý Đúng/Sai là partial; xóa đáp án ngắn bỏ trạng thái complete; đủ 3 câu được đếm chính xác |
| Kết quả | Câu trả lời đúng được tính 10 điểm demo; đổi ngữ cảnh tính lại và hiển thị đúng ngữ cảnh |
| Mobile drawer | Mở drawer, background inert, giữ focus trong drawer, Escape trả focus về trigger |
| Trạng thái | Empty/loading/error có nội dung tương ứng; thử lại từ error khôi phục nội dung mẫu |
| Tài nguyên | Không lỗi asset/page, không request ngoài, server không phục vụ file môi trường ứng dụng |

Đã sửa trong quá trình QA: focus tab sau khi DOM được dựng lại; nhãn ẩn cột Thao tác định vị ngoài bảng gây document rộng 560px ở viewport 375; bố cục wrapper giữ nhãn trong vùng cuộn; summary và ghi chú làm bài trên mobile được thu gọn. Hộp thoại native có sự kiện close bất đồng bộ, kiểm tra chờ đóng hoàn tất trước khi xác nhận return focus.

## 3. Ảnh lưu kèm

| Khung xem | Desktop | Mobile |
|---|---|---|
| Chi tiết bank research | [bank-desktop.png](screenshots/bank-desktop.png) | [bank-mobile.png](screenshots/bank-mobile.png) |
| Chi tiết bank general | [bank-general-desktop.png](screenshots/bank-general-desktop.png) | Kiểm tra layout 375px trong ma trận, không lưu ảnh riêng |
| Danh sách bank | [banks-desktop.png](screenshots/banks-desktop.png) | Kiểm tra layout 375px trong ma trận, không lưu ảnh riêng |
| Quản lý đề | [assessments-desktop.png](screenshots/assessments-desktop.png) | [assessments-mobile.png](screenshots/assessments-mobile.png) |
| Biên soạn | [editor-desktop.png](screenshots/editor-desktop.png) | Kiểm tra layout 375px trong ma trận, không lưu ảnh riêng |
| Làm bài | [take-desktop.png](screenshots/take-desktop.png) | [take-mobile.png](screenshots/take-mobile.png) |
| Kết quả | [result-desktop.png](screenshots/result-desktop.png) | Kiểm tra layout 375px trong ma trận, không lưu ảnh riêng |
| Thành phần | [components-desktop.png](screenshots/components-desktop.png) | Kiểm tra layout 375px trong ma trận, không lưu ảnh riêng |

Ảnh bank research/general được chụp viewport 1440×1000; các ảnh còn lại dùng desktop1440×900 hoặc mobile375×900, có full-page capture khi nội dung dài. Bản mẫu trực tiếp là cách kiểm tra tương tác; ảnh chỉ là trạng thái tại thời điểm chụp.

## 4. Giới hạn và việc kiểm chứng tiếp

- Chưa chạy functional/regression tests Flask, gọi AI, import file, giao đề, ghi điểm, xuất Excel hoặc thao tác DB. Các việc đó thuộc phase triển khai tương ứng và phải dùng dữ liệu thử cô lập.
- Prototype có3 câu mẫu để minh họa giao diện, không thay đề đầu vào/tự luyện 22 câu; đồng hồ không chạy; editor không đủ mọi trường đáp án/nhãn của sản phẩm cuối.
- Các trạng thái empty/loading/error từ thanh duyệt là thành phần mẫu. Không chứng minh toàn bộ failure/recovery server của 32 màn hình đã hoạt động.
- Tính điểm demo chạy tại trình duyệt với đáp án cố định; backend vẫn là nguồn quyết định khi triển khai. Không lưu lượt nộp/hồ sơ thật.
- Kiểm tra contrast là các cặp token đã liệt kê, không phải chứng nhận WCAG toàn diện. Chưa có audit screen reader, browser Safari/Firefox, landscape, mọi tổ hợp zoom hoặc dữ liệu toán/ảnh thực tế.
- General bank được kiểm tra quyền/nội dung ở desktop; ma trận32 layout sử dụng mode research mặc định của bank detail. General responsive và nội dung dài hơn vẫn cần kiểm tra thêm khi triển khai.
- Bản mẫu và đặc tả **chờ người dùng duyệt** trước Phase 3; QA đạt không thay cho phê duyệt thiết kế.
