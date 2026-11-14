# T02 · Raw QC Triage

## 1 · Một hàng review cho ảnh nghi lỗi

- 96 ảnh tổng hợp, tách theo 24 cảnh.
- Hàng review có 20 ảnh ưu tiên từ 40 ảnh eval.
- Đầu ra là KEEP, RECAPTURE hoặc HOLD kèm audit.

---

## 2 · Bốn dấu hiệu chất lượng

- Baseline dùng Laplacian toàn ảnh.
- PoC thêm ngưỡng sắc nét theo camera, độ sáng theo điều kiện, vùng bão hòa và ranh giới khối JPEG.
- Demo chạy `python -m src.main --offline --seed 42` rồi mở `out/contact_sheet.html`.

---

## 3 · Truy tìm lỗi

- Recall@20 trên gold thị giác nội bộ tăng từ 17/20 lên 18/20.
- Compression tăng từ 6/8 lên 8/8. Glare giảm từ 3/4 xuống 2/4.
- Mở `img_05_3` để xem lóa cục bộ và `img_03_2` để xem lóa tán xạ bị bỏ sót. [Bảng kết quả](../reports/table1_baseline_vs_poc.md)

---

## 4 · Review và phát hành

- REWORK sau review của Phung Danh Khoa. 20 approve xác nhận 17 RECAPTURE và 3 KEEP, giữ nguyên điểm xếp hạng.
- Tái lập bằng CSV đã xuất từ contact sheet hoặc chạy công cụ tạo evidence.
- Câu hỏi thảo luận: với cùng B=20, làm sao cải thiện lóa ban đêm mà không tăng bỏ sót nén ban ngày? [Review và audit](../reports/evidence)
