# Metric contract · T02 Raw QC Triage

- **Đơn vị:** một ảnh. Ghép prediction và gold theo `image_id`. Sắp score giảm dần, hòa điểm theo ID tăng dần.
- **Primary:** Defect Recall@20 = TP trong top 20 / tổng số ảnh lỗi trên eval. FN là số ảnh lỗi ngoài top 20. Precision@20 = TP / 20. False alarm theo ánh sáng = số ảnh sạch lọt vào top 20 / tổng ảnh sạch trong slice. Báo thêm theo loại lỗi và camera.
- **Pool:** tất cả ảnh eval của fixture. Dùng dev theo cảnh để khảo sát feature, chốt tham số trong `configs/lab.yaml` trước khi xem nhãn hoặc score eval. Cả hai phương pháp dùng B=20, cùng pool, seed 42. Không đổi score sau review.
- **Baseline:** ngưỡng Laplacian toàn ảnh 300. **PoC:** ngưỡng sắc nét theo camera, ngưỡng sáng theo điều kiện, lóa cục bộ theo ô 4×6 và tỷ lệ gradient tại ranh giới khối 8 px. Chốt bằng metadata và quan sát phân bố dev.
- **Gold nội bộ:** xem ảnh eval ở thứ tự ID trước khi mở dự đoán. Gán loại lỗi trội qua cạnh vật thể, khả năng đọc chi tiết, vùng cháy sáng và khối nén. Một lượt đánh giá thị giác bằng Codex. Không dùng hidden GT. Ghi nhãn `none` khi ảnh vẫn đủ chi tiết trong điều kiện sáng đã khai báo.
- **Độ bất định:** báo tử số/mẫu số. Các ảnh cùng cảnh phụ thuộc lẫn nhau, nên tỷ lệ là mô tả của pool cố định. Không suy diễn khoảng tin cậy hay hiệu quả ngoài phân phối từ mẫu này.
- **Stress test:** 10 ảnh sinh độc lập gồm nền kết cấu, ca sạch theo ánh sáng và bốn nhóm suy giảm có nhãn theo phép biến đổi. Dùng ngưỡng đã chốt, báo riêng khỏi metric chính.
- **Cổng quyết định:** HOLD khi hàng review chưa xong hoặc còn escalation. REWORK nếu đã duyệt xong và còn ảnh cần chụp lại. GO khi không còn pending, escalation hoặc RECAPTURE trong pool eval.
