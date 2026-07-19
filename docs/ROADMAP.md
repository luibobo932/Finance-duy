# Roadmap phát triển — trạng thái 12 ý tưởng

Cập nhật 18/07/2026. ✅ = đã xây & test xong · 🟡 = có công cụ, chờ dữ liệu/đầu vào người dùng · ⬜ = chưa làm.

## Nhóm 1 — Dữ liệu chuẩn

| # | Ý tưởng | Trạng thái | Ghi chú |
|---|---|---|---|
| 1 | Nguồn dữ liệu giá duy nhất | 🟡 | `scripts/indicators.py` + `data/eod/<MÃ>.csv` đã sẵn sàng. **Cần**: mở network policy cho `api.hsx.vn`/`services.entrade.com.vn`, hoặc Codex bơm CSV EOD 20+ phiên. Khi có dữ liệu, RSI/MACD/MA/Bollinger tự tính. |
| 2 | Tick data thật cho CTD | 🟡 | `scripts/tick.py` đã có (đếm lệnh tròn số lặp). **Cần**: API FireAnt/SSI hoặc file khớp lệnh CSV. |
| 3 | Backtest quy tắc | ✅ | `scripts/backtest.py` (MA cross, mở rộng được). Chạy khi `data/eod/` đủ dài. |

## Nhóm 2 — Cảnh báo & lịch

| # | Ý tưởng | Trạng thái | Ghi chú |
|---|---|---|---|
| 4 | Cảnh báo ngưỡng giá | ✅ | `scripts/alerts.py` + `data/alerts.json`. Đã cấu hình 6 ngưỡng VCB/CTD/vàng. Routine giữa phiên có thể quét & push. |
| 5 | Lịch sự kiện đầu tư | ⬜ | Cần bật Google Calendar connector cho routine. Mốc: họp Fed 28–29/7, KQKD Q2, review FTSE tháng 9. |
| 6 | Gửi bản tin qua email | ⬜ | Gmail connector có trong phiên tương tác nhưng KHÔNG truyền được vào routine tự động (routine chạy không connector). Cần tạo routine từ UI claude.ai có gắn Gmail, hoặc Codex gửi qua SMTP. |

## Nhóm 3 — Phân tích sâu & kỷ luật

| # | Ý tưởng | Trạng thái | Ghi chú |
|---|---|---|---|
| 7 | Định giá theo quý | 🟡 | Khung trong `docs/phuong-phap-phan-tich.md`. Kích hoạt khi KQKD Q2 ra (cuối tháng 7). |
| 8 | Nhật ký giao dịch | ✅ | `scripts/journal.py` + `data/journal.jsonl`. Ghi lệnh, tính win-rate, cảnh báo lệnh đi ngược khuyến nghị. **Bạn dùng**: nhắn mỗi lần mua/bán. |
| 9 | Danh mục giả lập Buffett-list | ✅ | `scripts/watchlist.py` + `data/watchlist.json`. Theo dõi 11 mã so ngày lập. Cần cập nhật giá định kỳ. |

## Nhóm 4 — Trải nghiệm

| # | Ý tưởng | Trạng thái | Ghi chú |
|---|---|---|---|
| 10 | Trang lưu trữ bản tin | ⬜ | Dự kiến: mỗi bản tin snapshot vào `dashboard/archive/`. |
| 11 | Bản tin tổng kết tuần (thứ Sáu) | 🟡 | Đã thêm mục vào prompt routine chiều thứ Sáu (xem README). |
| 12 | Telegram bot | 🟡 | `notifications/telegram.py` xây xong + test (bot `@Tintucstock_bot`, token đã lưu `.env`). **Bị chặn bởi network policy** (`api.telegram.org` — xác nhận qua log proxy "403 policy denial"). Cần mở domain này trong Network policy của environment trên claude.ai, sau đó chạy `python3 notifications/telegram.py whoami` rồi `send`. |

## Cần người dùng / admin

- [ ] **Giá vốn VCB, CTD** → `data/portfolio.json` (bật lãi/lỗ thật)
- [ ] **Mở network policy** cho nguồn giá → bật chỉ báo kỹ thuật tự động (mục 1, 3)
- [ ] **File khớp lệnh CTD** hoặc API key → soi lệnh nội bộ (mục 2)
- [ ] **Routine có connector** (tạo từ UI claude.ai) → email/calendar tự động (mục 5, 6)
- [ ] **Mở network policy cho `api.telegram.org`** → bật gửi bản tin qua Telegram bot `@Tintucstock_bot` (mục 12, code đã sẵn sàng)
