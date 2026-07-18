# Finance-duy — Hệ thống hỗ trợ quyết định đầu tư có kiểm chứng

Ứng dụng cá nhân để so sánh **Vàng, hai cổ phiếu đang theo dõi VCB/CTD và gửi tiết kiệm**. VCB/CTD không đại diện toàn thị trường chứng khoán. Hệ thống không dự báo chắc chắn và không phát lệnh mua/bán; nó chỉ mở khóa phân tích khi dữ liệu đủ mới, đúng đơn vị, có nguồn chính thức và vượt các kiểm tra nhất quán.

## Trạng thái an toàn hiện tại

- Dashboard mới nằm tại `dashboard/index.html`.
- Snapshot lịch sử ban đầu còn thiếu nguồn cho vàng, lãi suất và dữ liệu cơ bản doanh nghiệp, vì vậy kết quả hiện tại chủ động là **CHỜ DỮ LIỆU**.
- Giá đóng cửa VCB/CTD ngày thị trường 17/07/2026 đã được đối chiếu lại từ HOSE; các con số legacy không có nguồn không được dùng để ra quyết định.
- Workflow GitHub Pages chỉ build lại dashboard và làm trạng thái chuyển sang quá hạn. Nó **chưa tự thu thập rồi duyệt snapshot mới**.

## Những gì đã có

- Decision engine cho Vàng, VCB, CTD và tiết kiệm: điểm sàng lọc, confidence, blocker cứng, rủi ro và điều kiện làm luận điểm mất hiệu lực.
- Registry nguồn chính thức tại `config/sources.json`; URL đúng nhưng khai sai field vẫn không được tính.
- Kiểm tra độ mới theo `collected_at`, `market_date`, `gold.observed_at`, `retrieved_at` và ngày báo cáo cơ bản.
- Hợp đồng đơn vị rõ: giá cổ phiếu bằng VND; thanh khoản dùng duy nhất `volume_million_shares`.
- Premium vàng được đối chiếu lại từ SJC, XAU/USD và tỷ giá bán VCB.
- Lãi suất được kiểm tra theo từng sản phẩm: ngân hàng, nguồn, ngày lấy, kỳ hạn, kênh, min/max, điều kiện, cách trả lãi và ngày hiệu lực.
- Bộ mô phỏng khóa toàn bộ số tiền nếu một trong ba nhóm chưa READY hoặc khoản gửi nằm ngoài dải tiền của sản phẩm đã xác minh.
- Scorecard chỉ đánh giá sau đủ kỳ quan sát khác nhau; không công bố tỷ lệ đúng trước 20 kết quả.
- Danh mục cá nhân trên web chỉ nằm trong bộ nhớ tab. File local và raw data đều bị Git bỏ qua.
- CI chạy toàn bộ test trên Windows và Ubuntu, kiểm tra JavaScript và khả năng tạo dashboard.

## Chạy trên máy

```powershell
python -X utf8 scripts\build_dashboard.py
python -X utf8 -m http.server 8000 --directory dashboard
```

Mở `http://localhost:8000`.

```powershell
python -X utf8 -m unittest discover -s tests -v
python -X utf8 scripts\decision_engine.py report
python -X utf8 scripts\scorecard.py review
```

## Thu thập dữ liệu chính thức

Collector chỉ lưu bản thô trong `data/raw/`; không tự đưa dữ liệu vào lịch sử để tránh một lỗi nguồn làm mở khóa quyết định.

```powershell
python -X utf8 scripts\collect_hose.py 2026-07-17 VCB CTD
python -X utf8 scripts\collect_vietcombank.py all
```

Quy trình duyệt một snapshot:

1. Thu thập raw từ nguồn trong `config/sources.json`.
2. Chuẩn hóa theo `data/snapshot.example.json`.
3. Điền nguồn theo từng field và từng sản phẩm; không suy diễn nguồn.
4. Tạo ứng viên bằng `python -X utf8 scripts\candidate_pipeline.py stage data\snapshot-moi.json`.
5. Mở file trong `data/candidates/`, đối chiếu từng số với nguồn rồi ký nhận bằng lệnh `review`.
6. Chỉ sau khi đã rà soát mới chạy lệnh `promote` để đưa snapshot vào lịch sử.
7. Chạy test, decision report và build dashboard.
8. Chỉ ghi scorecard khi quyết định tương ứng thực sự ở trạng thái READY.

Ví dụ đầy đủ:

```powershell
python -X utf8 scripts\candidate_pipeline.py stage data\snapshot-moi.json
python -X utf8 scripts\candidate_pipeline.py review data\candidates\2026-07-18-chieu.candidate.json --reviewer "Duy" --note "Đã đối chiếu nguồn chính thức"
python -X utf8 scripts\candidate_pipeline.py promote data\candidates\2026-07-18-chieu.candidate.json
python -X utf8 scripts\build_dashboard.py
```

Mỗi ứng viên có checksum SHA-256. Nếu dữ liệu bị sửa sau khi tạo, bước rà soát hoặc promote sẽ bị từ chối. Thư mục `data/candidates/` là dữ liệu làm việc local và không được đưa lên GitHub.

## Cổng quyết định bắt buộc

### Chứng khoán

- Cần giá tham chiếu, giá đóng cửa, `%` thay đổi, `volume_million_shares`, VN-Index và `market_date` từ HOSE.
- `%` thay đổi phải khớp giá tham chiếu/đóng cửa.
- Cần lịch sử phiên chiều để xác minh thanh khoản.
- Dữ liệu cơ bản phải có ngày cuối kỳ, tăng trưởng lợi nhuận, ROE, P/E và nguồn IR đúng doanh nghiệp.

### Vàng

- Cần giá mua/bán SJC, XAU/USD, tỷ giá bán VCB, premium và thời điểm quan sát.
- Premium tự khai phải khớp phép quy đổi; giá quá hạn hoặc thời điểm tương lai bị khóa.

### Gửi tiết kiệm

- Mỗi dòng phải gắn đúng nguồn/ngân hàng và có đủ điều kiện sản phẩm.
- Mức quảng cáo thiếu min/max hoặc không áp dụng cho khoản dưới 1 tỷ bị loại.
- Hạn mức bảo hiểm tiền gửi cấu hình là 350 triệu đồng/người/tổ chức tham gia, hiệu lực 13/07/2026; luôn kiểm tra lại chính sách trước khi gửi.

## Cấu trúc chính

| Đường dẫn | Vai trò |
|---|---|
| `dashboard/` | Giao diện web và dữ liệu build |
| `scripts/decision_engine.py` | Cổng an toàn và điểm sàng lọc |
| `scripts/finance_data.py` | Schema, đơn vị và kiểm tra thời gian |
| `scripts/collect_hose.py` | Thu thập EOD VCB/CTD từ HOSE |
| `scripts/collect_vietcombank.py` | Thu thập tỷ giá/lãi suất VCB |
| `scripts/scorecard.py` | Nhật ký và đánh giá kết quả |
| `config/sources.json` | Registry nguồn/field/độ trễ |
| `data/history.jsonl` | Snapshot công khai đã duyệt |
| `data/raw/` | Bản thô private, không commit |
| `docs/nguon-du-lieu.md` | Chính sách nguồn và giấy phép |
| `docs/kiem-tra-du-lieu-legacy.md` | Kết quả rà dữ liệu ban đầu |

## Việc cần làm tiếp

1. Viết bộ thu thập SJC/XAU và báo cáo IR có kiểm soát giấy phép.
2. Kết nối collector vào luồng **candidate → review → promote** hiện có, không tự động promote.
3. Backfill ít nhất 20 phiên để dùng volume ratio; hướng tới 500 phiên trước khi backtest nghiêm túc.
4. Chỉ sau khi pipeline ổn định mới bật lịch tự thu thập; không tự động công khai raw dữ liệu có điều kiện bản quyền.
5. Bổ sung kiểm thử trình duyệt vào CI và giám sát lỗi collector.

> Đây là công cụ hỗ trợ kỷ luật ra quyết định, không phải tư vấn đầu tư cá nhân hay cam kết lợi nhuận.
