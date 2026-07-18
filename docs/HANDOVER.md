# Bàn giao kỹ thuật Finance-duy

## Nguyên tắc không được phá vỡ

1. Không có nguồn đúng field, đơn vị và thời điểm lấy thì phải trả `WAIT_DATA`.
2. Không dùng `date` thay cho `market_date` hoặc `gold.observed_at`.
3. Thanh khoản cổ phiếu chỉ dùng `volume_million_shares`; field `volume` bị từ chối vì mơ hồ.
4. Raw chỉ lưu trong `data/raw/`; không commit và không tự promote.
5. Dashboard công khai không được chứa giá vốn, số lượng hoặc dữ liệu danh mục thật.
6. Không gọi điểm sàng lọc là dự báo, lệnh mua/bán hay xác suất thắng.
7. Accuracy scorecard chỉ hiện khi đủ tối thiểu 20 outcome đã đánh giá.

## Quy trình phát hành snapshot

Snapshot mới bắt buộc đi qua ba trạng thái: `pending_review` → `reviewed` → `promoted`. Dùng `scripts/candidate_pipeline.py`; không append thẳng vào `data/history.jsonl`. Checksum khóa nội dung ứng viên giữa lúc tạo và lúc duyệt.

1. Chạy collector và giữ raw.
2. Đối chiếu schema/API drift, đơn vị và quyền phân phối.
3. Tạo candidate theo `data/snapshot.example.json`.
4. Gắn source ID/URL/retrieved_at/fields; sản phẩm tiết kiệm phải có provenance theo từng dòng.
5. Chạy:

```powershell
python -X utf8 scripts\trend.py append '<JSON>'
python -X utf8 -m unittest discover -s tests -v
python -X utf8 scripts\decision_engine.py report
python -X utf8 scripts\build_dashboard.py
node --check dashboard\app.js
```

6. Nếu còn blocker, xuất dashboard ở trạng thái WAIT_DATA; tuyệt đối không sửa tay để ép READY.
7. Chỉ ghi journal bằng `scripts\scorecard.py record` khi kỳ dữ liệu thực sự dùng để ra quyết định.

## Trạng thái triển khai

- CI: Windows + Ubuntu.
- GitHub Pages: build/deploy dashboard từ nhánh mặc định và chạy lại hằng ngày.
- Lịch hằng ngày hiện chỉ làm mới trạng thái độ tươi, chưa gọi collector.
- Collector hiện có: HOSE EOD và Vietcombank FX/lãi suất.
- Còn thiếu: SJC/XAU hợp lệ để phân phối, dữ liệu cơ bản IR tự động, kết nối collector vào pipeline duyệt và lịch sử đủ dài.

## Kiểm tra trước khi merge

- `git diff --check` sạch.
- Test, compile và JavaScript syntax đều xanh.
- `dashboard/data.json` không chứa `portfolio`, `avg_cost`, `quantity`.
- `data/raw/` và `portfolio.local.json` không xuất hiện trong `git status`.
- Dashboard mở không có console error và mọi asset thiếu dữ liệu vẫn hiển thị WAIT_DATA.

## Tài liệu liên quan

- `README.md`: tổng quan vận hành.
- `docs/nguon-du-lieu.md`: nguồn, độ trễ, giấy phép.
- `docs/phuong-phap-phan-tich.md`: phương pháp phân tích.
- `docs/kiem-tra-du-lieu-legacy.md`: sai lệch dữ liệu legacy và cách xử lý.
