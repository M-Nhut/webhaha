# Baseline AI/report/route trước Phase 8

Đã tái hiện **24 lỗi, 13 test đạt** trong bản copy tạm của 4 module test cũ, sử dụng nguyên templates/routes/services/tests từ snapshot trước Phase 8. Thời gian pytest 19,49 giây. Toàn bộ root Python module khớp SHA-256 trước Phase 8; các dịch vụ AI/report, route AI settings, test và fixture liên quan cũng khớp snapshot. Các hàm đăng ký route không đổi.

Không nạp dotenv; SQLite memory; không copy DB/credential; socket bị chặn và có **0 lượt kết nối được thử**. Không sửa app, UI hay test nghiệp vụ trong audit.

| Nhóm nguyên nhân | Số lỗi |
|---|---:|
| Fixture kỹ năng/scope cũ 9C6-4 so với scope hiện tại 9C8-i | 5 |
| Trạng thái fallback/cache cũ khi chưa có AI teacher hợp lệ | 5 |
| Test kỳ vọng raise trong khi validator hiện tại loại dòng risk không hợp lệ | 2 |
| Khóa tổng hợp chưa có last_test_status=ok bị từ chối trước provider | 7 |
| Test gọi endpoint group/course assignment đã bỏ | 4 |
| Route fixture cũ 79 so với 94 route đã có trước Phase 8 | 1 |

Route fixture thiếu 15 entry, hai entry test/retry key cần phương thức GET+POST thay cho POST-only. Không có route cũ bị loại trong so sánh fixture. Không tự cập nhật fixture trong audit; root có thể xác minh 94 route và bảo trì fixture riêng. Không mở lại quyền/group management/process-key fallback để làm xanh các test lịch sử.

[JSON đầy đủ từng test, lỗi, command, hash và route diff](baseline-ai-report-route-audit.json). [Runner đã dùng trong bản copy tạm](qa/run-prephase8-baseline-audit.py) yêu cầu đặt tại thư mục source copy tương ứng; runner không tự tạo bản copy.
