# Sidebar theo mẫu người dùng · 19/10/2026

Đã thay sidebar bản chạy bằng thanh xanh học thuật `#1E40AF`, icon viền trắng và mục active màu canvas `#F5F7FB`. Hai cung lõm 28px phía trên/dưới nối active với nền trang. Thay thế rule sidebar cũ trong `static/css/shell.css`, không thêm theme dự phòng hoặc thư viện mới.

- Desktop từ1200px: rail104px, icon26px, mục cao tối thiểu58px. Logo và hồ sơ gọn; tên menu xuất hiện khi hover hoặc focus. Mỗi link luôn có tên truy cập và active có `aria-current="page"`.
- Tablet/mobile: drawer280px có tên chức năng, nút đóng, Escape, focus trap, scrim và background inert. Khi thay breakpoint, focus chuyển tới điều hướng đang hiển thị.
- Không JavaScript: nhãn menu hiện; desktop mở rộng280px. Bản in ẩn sidebar.
- Menu giữ theo vai trò: teacher/admin10 mục, student4 mục. Bổ sung active parent đúng cho chỉnh sửa học sinh/giáo viên, evaluation ngân hàng và hồ sơ.
- Tooltip đặt ngoài vùng cuộn để không bị cắt; menu có thể cuộn ở màn hình thấp. Cập nhật cache version cho CSS chung và script shell.

## Kiểm chứng

[15 kiểm tra Python đạt](python-tests.json), gồm CSRF, tài khoản/hồ sơ, quyền menu và route contract. Chạy với SQLite memory và file tạm; không nạp `.env` hoặc dữ liệu thật.

[Kiểm tra tĩnh đạt](static-qa.json): CSS parse không lỗi, không token thiếu, 6 trường hợp render menu theo role/route đều đúng. `node --check static/js/ui-shell.js` đạt. Review độc lập đã kiểm tra hình học cung lõm, quyền, tên truy cập và focus theo breakpoint.

**Chưa xác minh trực quan bằng trình duyệt.** Hai lần yêu cầu chạy Chrome bị hệ thống duyệt tự động từ chối thực thi vì model duyệt đang quá tải (`Selected model is at capacity`). Đây là lỗi hạ tầng duyệt, không phải kết luận hành động không an toàn. Không đổi công cụ để vượt kiểm tra duyệt. Script [qa-sidebar.cjs](qa-sidebar.cjs) sẵn để chạy với preview dữ liệu giả lập, kiểm tra desktop/mobile, tooltip, cuộn, focus, fallback không JS, bản in và chụp ảnh; chưa có kết quả đạt hoặc ảnh của lượt này.

Bản xem trước dữ liệu giả lập: `python3 scripts/preview_ui_phase9.py --port 8771`. Tài khoản `qa_teacher`, `qa_admin`, `qa_student`; mật khẩu `Academy123!`.

**Bổ sung khi kiểm tra logo đăng nhập:** Chrome đã khởi chạy được cho một lượt kiểm tra tổng hợp. Xem [trạng thái sidebar/chữ](../readable-shell/browser-status.json); lượt này chưa hoàn tất ở bước focus responsive, chưa thay thế giới hạn nghiệm thu ở trên.
