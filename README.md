# Opportunity Intelligence OS — V1

Một hệ thống **evidence-first** để thu hẹp bất cân xứng thông tin cho cá nhân vốn nhỏ tại Việt Nam.

## V1 cố tình làm ít nhưng đúng

V1 không tự nhận là “AI biết cơ hội tương lai”. Nó tách rõ:

1. **Evidence** — dữ liệu/tín hiệu từ nguồn chính thức.
2. **Signal** — thay đổi đáng chú ý có thể kiểm chứng.
3. **Opportunity hypothesis** — giả thuyết kinh doanh, chưa phải sự thật.
4. **Validation** — test nhỏ, có ngân sách và kill criteria.

Điều này tránh lỗi nguy hiểm nhất: AI đọc vài bài báo rồi tạo ra một câu chuyện nghe hợp lý nhưng không có buyer thật.

## Màn hình

- **Hôm nay**: thay đổi đáng chú ý + cơ hội phù hợp với mức vốn đã chọn.
- **Signals**: feed dấu chân tiền/chính sách/nhu cầu kèm nguồn.
- **Opportunities**: xếp hạng theo vốn, time-to-cash, evidence, buyer clarity và cạnh tranh.
- **Buyer Radar**: ai có thể đang cầm ngân sách và họ thường mua gì khi trigger xuất hiện.
- **Validate**: kế hoạch test nhỏ + kill criteria + field notes.

## Công thức FIT SCORE

Điểm được tính lại theo vốn bạn chọn:

- 30% Evidence strength
- 25% Capital fit
- 20% Time-to-cash
- 15% Buyer clarity
- 10% Competition inverse

Đây là **fit score**, không phải xác suất thành công.

## Chạy local

Do frontend đọc JSON qua `fetch()`, hãy chạy HTTP server thay vì mở file trực tiếp:

```bash
python -m http.server 8000
```

Mở `http://localhost:8000`.

## Deploy GitHub Pages

1. Tạo repository mới.
2. Upload toàn bộ thư mục này vào root repo.
3. Settings → Pages → Deploy from a branch → `main` / root.
4. GitHub Actions `Update Opportunity Feed` chạy 4 lần/ngày.

## Pipeline tự động hiện tại

`pipeline/update.py` thu thập headline mới từ một số nguồn chính thức và ghi vào:

`data/raw_feed.json`

Nó chỉ gắn nhãn theo từ khóa và đánh dấu `unverified-headline`; **không tự biến headline thành opportunity**.

Đây là chủ ý. V2 mới nên thêm bộ phân tích AI có schema bắt buộc, citation bắt buộc và cơ chế từ chối tạo opportunity nếu evidence yếu.

## Việc cần làm ở V2

Ưu tiên theo thứ tự:

1. **Change detector theo chuỗi thời gian**: phát hiện tuyển dụng/CAPEX/đấu thầu/FDI tăng bất thường.
2. **Buyer database**: company + role + trigger + contact path, không chỉ buyer archetype.
3. **Evidence graph**: một opportunity phải liên kết được nhiều signal độc lập.
4. **Supply-gap estimator**: demand proxy tăng nhanh hơn supply proxy.
5. **AI analyst có output schema**: `claim`, `evidence`, `counter_evidence`, `buyer`, `test`, `kill_criteria`, `confidence`.
6. **Alert delta-only**: chỉ báo khi score hoặc evidence thay đổi đáng kể.

## Nguyên tắc dữ liệu

- Nguồn chính thức > công bố doanh nghiệp > nguồn báo chí uy tín > social chatter.
- Tin tức chỉ là một evidence type, không phải truth engine.
- Không dùng score để thay thế kiểm chứng thị trường.
- Không tạo “cơ hội” nếu không xác định được buyer hoặc cách test nhỏ.
- Không khuyến khích ôm tồn kho/tài sản khi chưa có demand validation.

## Seed evidence hiện tại

V1 được khởi tạo bằng dữ liệu công khai đến 30/08/2026 từ Cục Thống kê, Báo Chính phủ và Cổng Đăng ký kinh doanh quốc gia. Mỗi card có link nguồn trong UI.
