# Day 06 · T02 Raw QC Triage

| Mục | Giá trị |
|---|---|
| Học viên | Phùng Danh Khoa · 2A202603206 |
| Phạm vi | T02 · Bài làm trên fork cá nhân. Mã học viên dùng làm mã lần chạy. |
| Báo cáo và artefact | [GitHub fork](https://github.com/phungdanhkhoa/K5-Day6-L2A-PhungDanhKhoa-2A202603206-DataGovernanceAndPrivacy) · [final-24h-reviewed](https://github.com/phungdanhkhoa/K5-Day6-L2A-PhungDanhKhoa-2A202603206-DataGovernanceAndPrivacy/tree/final-24h-reviewed) |
| Phiên bản tạo evidence | `67ffafd` · cấu hình và phương pháp chốt ở `411ab92` |
| Xác nhận | Phung Danh Khoa đã duyệt cả 20 mục trong contact sheet. Gold thị giác nội bộ do Codex lập. |

## 1. Vấn đề và quyết định

Nhóm thu thập cần biết ảnh nào nên chụp lại trước khi chuyển cho người gán nhãn. Nếu bỏ qua lóa cục bộ, biển số tổng hợp có thể mất chi tiết dù phần còn lại của ảnh sắc nét. Nếu dùng cùng một ngưỡng sắc nét cho mọi camera và điều kiện sáng, ảnh đêm còn đọc được chi tiết có thể bị loại, làm giảm độ phủ dữ liệu.

Đầu vào gồm ảnh và metadata ánh sáng/camera. Hệ thống tạo điểm nghi ngờ, đề xuất KEEP hoặc RECAPTURE, đưa 20 ảnh eval có điểm cao nhất vào hàng review và xuất quyết định cấp lô. HOLD khi còn mục chờ duyệt hoặc escalation. REWORK khi review đã xử lý xong nhưng còn ảnh cần chụp lại. GO khi hàng ưu tiên đã xử lý và pool eval không còn ảnh bị đánh dấu chụp lại hoặc giữ lại để xử lý. Quyết định GO chỉ có ý nghĩa trong bài kiểm tra kỹ thuật này.

## 2. Dữ liệu và provenance

| Tập | Ảnh | Cảnh | Nguồn |
|---|---:|---:|---|
| Dev | 56 | 14 | Fixture T02 tổng hợp từ starter, CC0-1.0 |
| Eval | 40 | 10 | Cùng fixture, tách theo cảnh gốc |
| Stress ngoài fixture | 10 | 10 | Ảnh hình học do script tạo, CC0-1.0 |

[Manifest T02](../fixtures/t02_raw_qc/manifest.csv) ghi nguồn, giấy phép, split, group ID và SHA-256. Kiểm tra 14 manifest đầu vào đều đạt. Test sửa byte trong metadata xác nhận pipeline dừng với exit 2. Ảnh trong lab đều tổng hợp và không có người hay biển số thật. Mọi lần chạy dùng seed 42. Không tải model hay trọng số khi chạy.

Gold nội bộ là [40 nhãn thị giác](t02_visual_gold.csv). Codex xem contact sheet theo thứ tự ID trước khi mở dự đoán, xét độ đọc được của cạnh và chi tiết, vùng cháy sáng và artefact nén. Nhãn gồm 20 ảnh sạch và 20 ảnh lỗi. Có bốn ảnh blur, bốn dark, bốn glare và tám compression. Ảnh khác cùng cảnh giúp đối chiếu dấu hiệu suy giảm. Đây là một lượt đánh giá của AI. Điểm chính thức cần ground truth của giảng viên.

## 3. Thiết kế

`Ảnh + metadata → xác minh manifest → tính feature → xếp hạng top 20 → contact sheet / override → audit + quyết định`

Baseline dùng một ngưỡng Laplacian toàn ảnh, 300. Điểm nghi lỗi là 300 chia cho max(variance, 1). PoC dùng bốn tín hiệu.

| Tín hiệu | Ngưỡng hoặc phép đo |
|---|---|
| Blur | Laplacian variance tối thiểu 75 cho cam_A, 45 cho cam_B, 60 cho camera khác |
| Dark | Luma trung bình tối thiểu 45 ban ngày, 32 lúc chạng vạng, 14 ban đêm |
| Glare | Chia lưới 4×6. Kiểm tra ô có tỷ lệ pixel luma >245 lớn nhất, ngưỡng tỷ lệ 0.07 |
| Compression | Gradient tuyệt đối tại ranh giới 8 px so với phần trong khối, ngưỡng tỷ lệ 1.8 |

Mỗi tín hiệu là một tỷ lệ mức độ so với ngưỡng, tăng khi bất thường mạnh lên. PoC chuyển từng tỷ lệ x sang x/(1+x) rồi lấy giá trị lớn nhất. Điểm từ 0.5 đề xuất RECAPTURE. Đề xuất dưới ngưỡng vẫn vào hàng review nếu nằm trong top 20. Khi hòa điểm, ID tăng dần quyết định thứ tự. Tham số được chọn sau khi khảo sát dev và giữ nguyên qua eval lẫn stress. Bright-tile có chi phí thấp và dễ kiểm tra, nhưng sót lóa tán xạ khi vùng sáng chưa bão hòa. Blockiness có thể nhầm kết cấu tuần hoàn với nén.

## 4. Kết quả trước review

[Bảng so sánh do evaluator tạo](table1_baseline_vs_poc.md) · [JSON baseline](metrics_baseline.json) · [JSON PoC](metrics_poc.json)

Trên 40 ảnh eval, Recall@20 và Precision@20 đều tăng từ 17/20 lên 18/20, tương đương 5 điểm phần trăm. Sai số loại lỗi trên ảnh có lỗi giảm từ 16/20 xuống 3/20. Hai mô hình dùng cùng pool, cách ghép theo ID, B=20 và seed 42. Thời gian của lần chạy chứng cứ là 0.1796 và 0.1771 giây trên 100 ảnh, gồm xác minh, giải mã, chấm và xuất HTML. Đây là một lần đo trên macOS ARM64, Python 3.11.12. Chênh lệch thời gian nhỏ chưa đủ để kết luận về tốc độ.

| Slice | Ảnh lỗi tìm thấy, baseline | Ảnh lỗi tìm thấy, PoC | Ảnh sạch trong top 20, baseline → PoC |
|---|---:|---:|---:|
| Day | 9/10 | 10/10 | 0/10 → 2/10 |
| Dusk | 2/2 | 2/2 | 1/2 → 0/2 |
| Night | 6/8 | 6/8 | 2/8 → 0/8 |
| cam_A | 11/14 | 14/14 | 0/14 → 2/14 |
| cam_B | 6/6 | 4/6 | 3/6 → 0/6 |

Recall theo loại lỗi cho thấy compression tăng từ 6/8 lên 8/8, còn glare giảm từ 3/4 xuống 2/4. Blur và dark cùng đạt 4/4 ở cả hai phương pháp. Các tỷ lệ mô tả pool cố định. Chỉ có 10 cảnh eval và ảnh cùng cảnh có tương quan. Một ảnh lỗi làm Recall@20 đổi 5 điểm phần trăm.

### Trường hợp cần kiểm tra lại

- **Ảnh đêm hữu ích và camera mềm.** `img_06_0` là ảnh sạch từ cam_B. Laplacian 275.7 khiến baseline đề xuất RECAPTURE và xếp hạng 9. PoC đề xuất KEEP, hạng 22. [Ảnh img_06_0](../fixtures/t02_raw_qc/images/img_06_0.jpg)
- **Lóa cục bộ trên ảnh nét.** `img_05_3` có Laplacian 1324.5, nhưng lóa nằm trên cụm xe. Baseline xếp hạng 31. Tỷ lệ bão hòa 0.258 tại ô sáng nhất đưa ảnh lên hạng 10 trong PoC. [Ảnh img_05_3](../fixtures/t02_raw_qc/images/img_05_3.jpg)
- **Lóa tán xạ ban đêm.** `img_03_2` và `img_06_3` chỉ có tỷ lệ bão hòa 0.025 và 0.027 ở ô sáng nhất. Cả hai dưới ngưỡng 0.07, xếp hạng 29 và 25 và bị bỏ sót. Cần thử đo tương phản cục bộ hoặc chỉ báo vùng sáng theo camera trên một tập dev mới. [Ảnh img_03_2](../fixtures/t02_raw_qc/images/img_03_2.jpg) · [Ảnh img_06_3](../fixtures/t02_raw_qc/images/img_06_3.jpg)
- **Nén nhẹ với quyết định KEEP.** `img_19_2` có tỷ lệ blockiness 1.62. PoC đưa ảnh vào hàng review ở hạng 18 và đề xuất KEEP. Gold thị giác nội bộ ghi nhận artefact nén quanh viền vật thể. Người duyệt chấp thuận KEEP. Hai kết quả phản ánh hai câu hỏi khác nhau, nhận diện dấu hiệu nén và quyết định có cần chụp lại. [Ảnh img_19_2](../fixtures/t02_raw_qc/images/img_19_2.jpg)

Trong 10 ảnh stress với bố cục khác, PoC đánh dấu đúng 8/8 ảnh có lỗi và giữ 2/2 ảnh sạch tại ngưỡng vận hành. Baseline đánh dấu 4/8 ảnh lỗi và giữ 2/2 ảnh sạch. Nhãn stress đến từ phép biến đổi đã biết. Bài kiểm tra dùng cùng thư viện mô phỏng của starter và kích thước ảnh tương đương, nên sức khái quát ra camera thật vẫn chưa được kiểm chứng. [Kết quả từng ảnh](evidence/stress_results.csv)

## 5. Review, audit và quyết định

Contact sheet nhúng thumbnail để mở offline. Reviewer có thể nhập tên, chọn quyết định, điền lý do và xuất CSV. Pipeline kiểm tra ID thuộc queue hiện tại, tên reviewer và giá trị override. Nhật ký ghi actor, hành động, giá trị trước/sau và lý do. `skip` giữ mục ở trạng thái chưa giải quyết. `escalate` khiến ảnh chuyển HOLD. File chấm giữ nguyên score qua review.

CSV xuất từ contact sheet ghi 20 `approve` của **Phung Danh Khoa**. Pipeline áp dụng các quyết định, giữ nguyên 17 RECAPTURE và 3 KEEP trong hàng review, rồi chuyển HOLD sang REWORK với lý do `RECAPTURE_REQUIRED`. Nhật ký lưu thời điểm review do CSV cung cấp. Điểm benchmark và thứ tự xếp hạng giữ nguyên. [Contact sheet](../demo/contact_sheet.html) · [CSV review](evidence/review_queue_reviewed.csv) · [Audit](evidence/audit_log.jsonl) · [Decision log](evidence/decision_log.csv)

## 6. Tái lập

Dùng Python 3.11–3.13. Cài dependency một lần bằng `make setup` khi `python3` trỏ đến phiên bản hỗ trợ. Trên máy có Python 3.15 mặc định, có thể dùng `python3.11 -m venv .venv` và `.venv/bin/python -m pip install -r requirements.txt`.

```bash
source .venv/bin/activate
python -m src.main --input fixtures/t02_raw_qc --config configs/lab.yaml --output out/ --offline --seed 42
python -m src.evaluate --track t02 --gt reports/t02_visual_gold.csv --pred out/ranked_review.csv
python -m pytest -ra
python -m tools.t02_evidence
```

Kết quả kiểm tra là 49 passed, 39 skipped. Các skip cần overlay giảng viên. Preflight có 0 lỗi và hai cảnh báo về dữ liệu thật và model tùy chọn. Công cụ tạo evidence chạy lại baseline và PoC, xuất bảng metric, áp dụng lại CSV review của học viên và tạo lại stress pack. Hai bản `run_info` ghi hash cấu hình, commit, seed, môi trường và runtime của mỗi lần chạy.

## 7. Giới hạn và đóng góp

Cần một reviewer độc lập cho ca nghi ngờ, tập camera thực có quyền sử dụng và theo dõi miss theo điều kiện sáng. Khi số ảnh tăng 10 lần, B=20 làm giảm tỷ lệ ảnh được xem. Có thể tăng ngân sách theo tỷ lệ hoặc đặt quota theo camera, rồi đo lại trên holdout mới. Trước khi áp dụng cho dữ liệu thật, owner và DPO cần xác nhận quyền lưu giữ, quyền truy cập bản gốc và cách ghi audit. Kết quả chỉ đánh giá chất lượng ảnh tổng hợp.

Codex hỗ trợ triển khai, lập nhãn thị giác, kiểm thử và soạn báo cáo. Lịch sử Git ghi các thay đổi trên fork. Phùng Danh Khoa duyệt 20 ảnh ưu tiên. Phần trình bày nhóm chưa được ghi nhận. [Bảng đóng góp](team_contributions.csv) · [Bốn slide demo](../demo/showcase.md)

## 8. Tài liệu tham khảo

- Xem ngày 14/11/2026. Mô tả đạo hàm bậc hai theo hai trục làm cơ sở cho feature sharpness. [OpenCV Laplace Operator](https://docs.opencv.org/4.x/d5/db5/tutorial_laplace_operator.html)
- Xem ngày 14/11/2026. Chuẩn JPEG làm cơ sở cho phép kiểm tra sai khác tại ranh giới khối. [ITU-T T.81](https://www.itu.int/rec/T-REC-T.81/en)
