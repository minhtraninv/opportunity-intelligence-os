# Opportunity Intelligence OS — V3 Official

Một **evidence-first information radar** cho Việt Nam.

Mục tiêu của hệ thống không phải săn cổ phiếu, không phải săn thầu và cũng không phải tự động nói người dùng nên mở business gì. Mục tiêu là:

> **Tăng xác suất để một người bình thường gặp được những thay đổi đáng chú ý đủ sớm để mở hồ sơ nghiên cứu, trước khi chúng trở thành câu chuyện quá hiển nhiên.**

## Product promise

Opportunity Intelligence OS cố trả lời theo chuỗi:

**Macro / Policy → Money Flow → Regional Divergence → Entities / Projects → Convergence → Counter-evidence → Lifecycle → Possible entry points → Small test**

Một entity có thể là doanh nghiệp, dự án, địa phương, ngành, KCN, công nghệ hoặc tổ chức. `DON'T IGNORE` chỉ có nghĩa **đáng điều tra**, không có nghĩa `BUY` hay `DO THIS`.

## Mặt tiền

### Bức tranh
Dùng hàng ngày để biết:

- nền kinh tế thực đang chạy ra sao;
- luật chơi/chính sách nào đang đổi;
- tiền và hoạt động đang hội tụ ở theme nào;
- địa bàn nào đang phân kỳ;
- entity nào đang xuất hiện ở nhiều lớp bằng chứng;
- điều gì có thể khiến thesis sai;
- hệ thống đang mù ở domain dữ liệu nào.

### DON'T IGNORE · Attention Queue
Hàng đợi ngắn các thay đổi đáng mở hồ sơ nghiên cứu. Đây là lớp tạo **cơ duyên thông tin**, không phải recommendation engine.

### Bằng chứng / Chi tiết
Dùng để mở source, Change Detector, curated signals, lifecycle và các evidence phía sau Bức tranh.

### Small Bets
Chỉ chứa những hypothesis đã dịch được thành buyer + test nhỏ + kill criteria. Đây **không phải toàn bộ cơ hội của nền kinh tế**.

### Advanced
Procurement, buyer/vendor history, relationship graph và execution. Đây là phòng máy xác minh một thesis cụ thể, không phải trung tâm sản phẩm.

## Personal Action Layer

Vốn, thời gian có tín hiệu và địa lý **không được hard-filter radar**.

Personal Action Layer chỉ xếp hạng Small Bets theo khả năng thực thi hiện tại. Một cơ hội chưa phù hợp vẫn phải được nhìn thấy.

Các lựa chọn cá nhân được lưu trên `localStorage`; không upload lên GitHub.

## Source contract

Hệ thống phân biệt rõ:

1. **Source health** — truy cập được nguồn hay không.
2. **Qualified evidence** — nguồn có tạo candidate/curated evidence đủ chuẩn hay không.
3. **Source independence** — nhiều bài đăng lại cùng một sự kiện không được tính như nhiều evidence độc lập.
4. **Coverage blind spot** — domain yếu/broken/missing phải được hiển thị công khai.

Ưu tiên nguồn:

**official / primary disclosure > official operator > reputable media discovery > hypothesis**

Media được dùng để phát hiện thứ hệ thống chưa biết phải tìm. Kết luận mạnh vẫn cần primary evidence.

## Stable architecture

- Macro Pulse
- Policy Radar
- Money Flow Intelligence
- Regional Divergence
- Open-world Entity Discovery
- Entity Convergence
- Contradiction / Falsification
- Thesis Lifecycle
- Source Coverage Audit
- Personal Action Layer
- Small Bet Validation
- Advanced Procurement / Partner / Execution

## Non-goals

- Không phải stock screener.
- Không dự báo giá cổ phiếu.
- Không coi policy là dòng tiền đã xảy ra.
- Không coi FDI đăng ký là vốn đã giải ngân.
- Không coi procurement là toàn bộ nền kinh tế.
- Không gọi supply gap nếu chưa có supply-side evidence.
- Không ép hệ thống phải luôn có một “câu chuyện hot”.

## Automation

GitHub Actions cập nhật pipeline nhiều lần mỗi ngày. Dữ liệu lịch sử được dùng để học baseline và lifecycle. Một ngày có nhiều workflow runs vẫn chỉ tính là **một observation day** khi đánh giá xu hướng dài hơn.

## Chạy local

```bash
python -m http.server 8000
```

Mở `http://localhost:8000`.

## Release philosophy

Từ V3, kiến trúc sản phẩm được coi là **stable**. Việc phát triển tiếp ưu tiên:

- tăng độ phủ nguồn;
- sửa precision/recall;
- giảm blind spot;
- nâng chất lượng entity resolution;
- bổ sung evidence lịch sử;
- sửa bug.

Không tăng version kiến trúc chỉ để thêm dashboard hoặc feature không làm tăng khả năng nhìn thấy thay đổi quan trọng.
