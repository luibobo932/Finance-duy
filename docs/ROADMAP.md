# Roadmap phát triển — trạng thái 12 ý tưởng

Cập nhật 20/07/2026. ✅ = đã xây & test xong · 🟡 = có công cụ, chờ dữ liệu/đầu vào người dùng · ⬜ = chưa làm.

## Nhóm 1 — Dữ liệu chuẩn

| # | Ý tưởng | Trạng thái | Ghi chú |
|---|---|---|---|
| 1 | Nguồn dữ liệu giá duy nhất | ✅ | **Đã xác nhận `services.entrade.com.vn` KHÔNG bị chặn trên laptop local** (2026-07-20) — chỉ bị chặn network policy trong claude.ai sandbox. `scripts/fetch_eod.py` (mới) gọi API `chart-api/v2/ohlcs/stock?...&resolution=1D` thật, gộp vào `data/eod/<MÃ>.csv`. Đã tải 27 phiên thật cho VCB và CTD (17/6–17/7/2026), `scripts/indicators.py` tự tính RSI/MACD/MA20/Bollinger từ dữ liệu thật. Vẫn cần thêm ~173 phiên để đủ MA200. |
| 2 | Tick data thật cho CTD | ✅ | `scripts/tick.py fetch CTD <ngày>` đã chạy được thật trên laptop local (cùng domain entrade, nến 1 phút — **vẫn là proxy gần đúng, không phải từng lệnh khớp thật**, đúng như tài liệu đã ghi). Test 17/7/2026: 171 bản ghi, không phát hiện bất thường. |
| 3 | Backtest quy tắc | ✅ | `scripts/backtest.py` (MA cross, mở rộng được). Chạy khi `data/eod/` đủ dài. |

> **29/08/2026 — dữ liệu EOD đã cũ 19 ngày và không ai chạy `fetch_eod.py`.**
> Hệ quả không phải "thiếu dữ liệu" mà là **lời khuyên sai**: bản tin ra MUA THĂM DÒ
> CTD 80/100 kèm mức cắt lỗ 53.61 tính trên giá của ba tuần trước, trong khi
> `health_check.py` gọi đúng chuỗi đó là hỏng. Đã sửa (xem README, mục 29/08): nay
> Risk Officer chặn nhánh cổ phiếu bằng cùng rule đang chặn vàng. Việc còn lại là của
> vận hành — chạy `python3 scripts/fetch_eod.py` định kỳ, vì hệ thống giờ **im lặng**
> thay vì đoán bừa, và im lặng kéo dài cũng là mất mát.

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
| 8 | Nhật ký giao dịch | ✅ | `scripts/journal.py` + `data/journal.jsonl`. Ghi lệnh, tính win-rate, cảnh báo lệnh đi ngược khuyến nghị. **Bạn dùng**: nhắn mỗi lần mua/bán. **Phase 9 bổ sung**: `scripts/review.py` + `data/decisions.jsonl` — hệ thống tự ghi mọi quyết định của Decision Engine và đối chiếu với giá thực tế sau đó (chống look-ahead), accuracy nạp ngược vào confidence score. |
| 9 | Danh mục giả lập Buffett-list | ✅ | `scripts/watchlist.py` + `data/watchlist.json`. Theo dõi 11 mã so ngày lập. **Hết cần cập nhật tay**: `watchlist.py update` tải giá thật cả 11 mã từ entrade (20/07/2026 đã điền đủ base 17/7, chống look-ahead: base chỉ lấy phiên ≤ ngày lập). |

## Nhóm 4 — Trải nghiệm

| # | Ý tưởng | Trạng thái | Ghi chú |
|---|---|---|---|
| 10 | Trang lưu trữ bản tin | 🟡 | `dashboard/ban-tin-dau-tu.html` giờ **sinh 100% từ `history.jsonl`** (`scripts/build_dashboard.py`) và hiện TOÀN BỘ lịch sử thay vì cửa sổ trượt 9 kỳ — nên bản thân trang đã là trang lưu trữ. Còn thiếu: snapshot từng kỳ ra file riêng trong `dashboard/archive/` để xem lại đúng trang của một ngày cụ thể. |
| 11 | Bản tin tổng kết tuần (thứ Sáu) | 🟡 | Đã thêm mục vào prompt routine chiều thứ Sáu (xem README). |
| 12 | Telegram bot | 🟡 | `notifications/telegram.py` xây xong + test (bot `@Tintucstock_bot`, token đã lưu `.env`). **Bị chặn bởi network policy** (`api.telegram.org` — xác nhận qua log proxy "403 policy denial"). Cần mở domain này trong Network policy của environment trên claude.ai, sau đó chạy `python3 notifications/telegram.py whoami` rồi `send`. |

## Cần người dùng / admin

- [ ] **Giá vốn VCB, CTD** → `data/portfolio.json` (bật lãi/lỗ thật)
- [x] **Mở network policy** cho nguồn giá → ĐÃ XONG trên laptop local (2026-07-20), `scripts/fetch_eod.py` chạy thật (mục 1, 3). Vẫn cần chạy định kỳ để tích lũy đủ 200 phiên cho MA200.
- [x] **File khớp lệnh CTD** hoặc API key → ĐÃ XONG trên laptop local, `scripts/tick.py fetch` dùng cùng nguồn entrade (proxy nến 1 phút, mục 2)
- [ ] **Routine có connector** (tạo từ UI claude.ai) → email/calendar tự động (mục 5, 6)
- [ ] **TELEGRAM_BOT_TOKEN thật** trong `.env` local (không có trong git) → cần chủ dự án cung cấp lại để chạy `notifications/telegram.py whoami`/`send` trên laptop này (mục 12, xem README)
