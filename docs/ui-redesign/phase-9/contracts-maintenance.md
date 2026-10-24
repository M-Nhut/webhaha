# Phase 9 — bảo trì contract test lịch sử

Ngày nghiệm thu: **19/10/2026**. Phạm vi chỉ gồm `test_class_lesson4_report.py`, `test_ai_gateway_review.py`, `test_phase5_reports.py`, `test_route_contract.py` và `fixtures/route_contract.json`. Không sửa service, route, quyền hay luồng gọi nhà cung cấp để làm xanh test.

Audit trước Phase 8 đã tái hiện **24 lỗi, 13 test đạt** trong bốn module này. [Baseline và nguyên nhân](../phase-8/baseline-ai-report-route-audit.md) ghi rõ các fixture vẫn dùng scope cũ, khóa chưa xác minh, endpoint quản lý nhóm đã bỏ và fallback/cache không còn đúng contract hiện tại.

## Các contract đã cập nhật và giữ kiểm tra

- Scope báo cáo là `9C8-i`; fixture bài làm dùng mã kỹ năng hiện tại. Response AI tổng hợp được dựng từ đúng packet đã gửi, có tóm tắt, giả thuyết, nguy cơ chưa kiểm chứng và hướng dạy đủ trường bắt buộc.
- Test gateway dùng khóa tổng hợp đã có `last_test_status=ok` khi cần kiểm tra failover. Một test riêng chứng minh khóa chưa xác minh không gửi lượt gọi provider nào. Các kiểm tra lỗi 400/401/429, cooldown theo project, khóa bị thu hồi, đổi giáo viên giữa retry và che thông tin nhạy cảm được giữ.
- Thiếu khóa/cấu hình trả `failed` với `analysis_source=ai_api`, được thử lại và không trở thành cache thành công. Dữ liệu quan sát vẫn được kiểm tra riêng qua `present_observed_report`.
- Cache hoàn tất và hàng `processing` dùng đúng identity owner/group/revision/provider/model/prompt; vẫn kiểm tra thay bài làm, chấm lại và thêm roster làm thay fingerprint. Luồng route xác nhận báo cáo thành công, sau đó từ chối xác nhận khi bài làm mới làm báo cáo cũ.
- Validator loại dòng nguy cơ sai kỹ năng/ref hoặc ref thuộc học sinh khác; test vẫn giữ dòng hợp lệ, không để ref/nội dung bịa đi vào response đã lưu. Các cause/observed claim sai ref vẫn bị từ chối. Chế độ `require_teacher_support=True` vẫn từ chối risk tự đánh dấu đã xác nhận hoặc thiếu câu hỏi kiểm chứng.
- Test endpoint cũ được thay bằng save/retry/test/delete khóa mặc định hiện tại: quyền sở hữu, khóa trong nhóm cũ không được thao tác, CSRF, mã hóa/masked rendering, chỉ probe đúng khóa và admin không được dùng khóa giáo viên. Cột ánh xạ nhóm lớp lịch sử không ghi đè nhóm mặc định; endpoint gán nhóm theo lớp vẫn trả 404.
- Fixture báo cáo cá nhân dùng đề đầu vào đủ 22 câu (12 trắc nghiệm, 4 Đúng/Sai, 6 trả lời ngắn). Bằng chứng lớp được chọn phải có trong outbound request; bằng chứng lớp khác phải vắng cả request gửi và request lưu.

## Route fixture

Fixture có **94 entry**, khớp route thực tế đã tồn tại trước Phase 8. Thêm 15 entry thiếu cho AI reports, assessment, diagnostic review/delete, question choices/detail và favicon. Hai endpoint kiểm tra/thử lại khóa giữ đúng phương thức đã đăng ký `GET + POST`; không sửa phương thức backend. Không xóa entry cũ. [Danh sách và hash đối chiếu](contracts-maintenance.json).

## Kiểm chứng

```sh
python3 scripts/test_ui_redesign.py tests/test_class_lesson4_report.py tests/test_ai_gateway_review.py tests/test_phase5_reports.py tests/test_route_contract.py -q --tb=short --disable-warnings
```

Kết quả: **39 test và 3 subtest đạt**. Số test tăng từ 37 lên 39 nhờ kiểm tra khóa chưa xác minh và lọc nguy cơ sai trước khi lưu. SQLite memory, storage tạm, không nạp dotenv; HTTP/socket bị chặn với **0 lượt kết nối được thử**. Provider response và thời gian retry đều được mock. [Kết quả máy đọc được](contracts-focused-regression.json).

Hash của bảy service/route liên quan khớp snapshot trước Phase 9; chi tiết trong [contracts-maintenance.json](contracts-maintenance.json). Đây là bảo trì fixture theo chức năng đã có, không khôi phục group manager, khóa môi trường dùng chung hay fallback AI cũ.
