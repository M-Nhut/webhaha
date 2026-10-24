# Giai đoạn 5 — Đánh giá và thí điểm

Triển khai khung đánh giá local ngày 08/09/2026.

Lệnh đánh giá nhận một mảng JSON gồm nội dung câu, phạm vi và hai nhãn độc lập do giáo viên xác nhận: `expected_primary_code`, `expected_difficulty_level`.

```sh
python3 scripts/evaluate_question_classification.py services/data/math9_c6_evaluation_template.json
```

Mẫu cấu trúc ở [math9_c6_evaluation_template.json](/Users/mac/Documents/BTESTWEB%202/services/data/math9_c6_evaluation_template.json). Dữ liệu thật cần có khoảng 80–160 câu, phủ 8 dạng của Bài 4, bốn mức độ thực tế và ba hình thức D/T/S. Không dùng kết quả hệ thống tự gán làm nhãn đánh giá.

Để tạo gói nhãn cho giáo viên thứ hai từ một ngân hàng SQLite, dùng:

```sh
python3 scripts/export_classification_review_packet.py tutoring_center.db 12 --output labels-chapter6.json
```

Gói chỉ có nội dung câu và phương án/mệnh đề, bỏ đáp án, lời giải, dự đoán và câu lặp nội dung. Giáo viên điền hai trường `expected_primary_code` và `expected_difficulty_level`, cùng tên người gán nhãn, sau đó chạy lệnh đánh giá ở trên.

Báo cáo tách riêng độ đúng dạng, mức độ, cặp dạng–mức độ trong phần hệ thống tự gán, độ phủ tự gán theo dạng và các nhóm có nội dung trùng nhau. Nhóm nội dung trùng làm cổng chất lượng thất bại để tránh kết quả lạc quan do cùng câu xuất hiện ở nhiều tập.

Cổng mặc định chỉ cho phép cân nhắc bật tự gán rộng khi có ít nhất 240 nhãn hợp lệ, không có nhóm câu trùng và độ đúng cặp dạng–mức độ của phần tự gán đạt từ 95%. Mẫu hiện có chỉ là một câu minh họa: công cụ báo `ready_for_wider_auto_assignment: false`, vì vậy hệ thống chưa có cơ sở để công bố đạt ngưỡng hoặc bật tự gán rộng.

Kiểm thử bao phủ tính chỉ số, nhãn không hợp lệ, tập nhỏ và phát hiện nội dung lặp.
