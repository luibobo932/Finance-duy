# Finance-duy — Bản tin Đầu tư tự động

Hệ thống tổng hợp tin tức đầu tư 2 lần/ngày (8h sáng & 6h chiều giờ Việt Nam) chạy bằng Claude Code Routines, phục vụ ra quyết định đầu tư.

## Nội dung mỗi bản tin

1. **Chứng khoán Việt Nam**
   - Diễn biến VN-Index / VN30 / HNX, thanh khoản, khối ngoại mua/bán ròng
   - Phân tích từng nhóm ngành (ngân hàng, BĐS, thép, chứng khoán, bán lẻ, dầu khí, công nghệ, cảng biển/xuất khẩu…) và **yếu tố đang khiến từng nhóm hưởng lợi hay bất lợi**
   - Bản sáng: tin qua đêm (Mỹ, thế giới) ảnh hưởng phiên hôm nay
   - Bản chiều: kết quả phiên vừa đóng cửa + tin doanh nghiệp trong ngày

2. **Vàng**
   - Giá SJC miếng, vàng nhẫn 9999 (SJC, DOJI, BTMC)
   - Giá vàng thế giới XAU/USD, chênh lệch trong nước – thế giới (quy đổi theo tỷ giá VCB)
   - Yếu tố tác động: Fed, DXY, địa chính trị, chính sách NHNN

3. **Lãi suất tiết kiệm**
   - Ngân hàng có lãi suất cao nhất cho khoản gửi **dưới 1 tỷ đồng**, theo kỳ hạn 6 / 12 / 13+ tháng
   - Loại trừ các mức lãi suất đặc biệt yêu cầu số dư lớn

4. **Gợi ý hành động** — định hướng ngắn gọn cho nhà đầu tư (tham khảo, không phải khuyến nghị đầu tư)

## Lịch chạy (Routines)

| Routine | Cron (UTC) | Giờ VN | Trigger ID |
|---|---|---|---|
| Bản tin đầu tư sáng 8h | `0 1 * * *` | ~08:08 | `trig_01VkDWQ59sqHpXDTyScxmzzV` |
| Bản tin đầu tư chiều 6h | `0 11 * * *` | ~18:08 | `trig_01B8JjRY5Qm71deb3s69XwCb` |

Routine chiều thứ Sáu tự thêm mục **Tổng kết tuần**. Cả hai routine tự chạy `indicators.py`, `alerts.py`, `trend.py`, `watchlist.py` khi có dữ liệu.

## Lịch sử số liệu & xu hướng

- `data/history.jsonl` — mỗi bản tin append 1 dòng JSON snapshot (VN-Index, VCB, CTD, khối ngoại, vàng, tỷ giá, top lãi suất, cờ rủi ro). Xem dòng đầu file làm schema mẫu.
- `data/portfolio.json` — giá vốn + số lượng VCB/CTD để tính lãi/lỗ thực tế (null = chưa cung cấp).
- `scripts/trend.py`:
  - `append '<json>'` — validate và ghi snapshot mới (chặn ghi trùng ngày+kỳ)
  - `report` — so sánh với kỳ trước: biến động VN-Index/VCB/CTD/vàng, chuỗi mua/bán ròng khối ngoại (chỉ tính kỳ chiều để không đếm trùng phiên), **KLGD từng mã vs bình quân 20 phiên (cảnh báo ⚠️ khi ≥1,5× — dấu hiệu cần soi thỏa thuận/giao dịch nội bộ)**, chênh lệch vàng nới/thu hẹp, ngân hàng thay đổi lãi suất, lãi/lỗ danh mục
- Mỗi routine tự commit + push `data/` sau khi ghi để lịch sử bền vững qua các container.

## Công cụ phân tích & quản lý (scripts/)

| Script | Chức năng |
|---|---|
| `trend.py` | Lịch sử snapshot + so sánh xu hướng + lãi/lỗ danh mục |
| `tick.py` | Phát hiện gom hàng qua lệnh lớn tròn số lặp lại (cần dữ liệu khớp lệnh) |
| `indicators.py` | RSI(14), MACD, SMA/EMA 20/50/200, Bollinger từ `data/eod/<MÃ>.csv` |
| `backtest.py` | Backtest quy tắc (MA cross…) trên dữ liệu EOD |
| `alerts.py` + `data/alerts.json` | Cảnh báo ngưỡng giá VCB/CTD/vàng bị chạm |
| `journal.py` + `data/journal.jsonl` | Nhật ký giao dịch cá nhân: win-rate, đối chiếu khuyến nghị |
| `watchlist.py` + `data/watchlist.json` | Theo dõi hiệu suất danh mục giả lập Buffett-list |
| `networth.py` + `data/assets.json` | Tài sản ròng thực tế (vàng/tiết kiệm/mặt/cổ phiếu) + phân bổ + cảnh báo tập trung |
| `gold_price.py` + `data/gold_model.json` | Ước tính giá vàng nhẫn tại tiệm theo XAU/USD real-time (hiệu chuẩn từ 1 ảnh bảng giá); networth tự dùng để định giá vàng động |

Xem `docs/ROADMAP.md` cho trạng thái toàn bộ 12 hạng mục phát triển và việc cần người dùng cung cấp.

## Data contract & kiểm thử (Phase 2)

Dự án đang được nâng cấp theo `docs/IMPLEMENTATION_PLAN.md` (10 phase, xem `docs/AUDIT_REPORT.md` cho hiện trạng đầy đủ).

- `datacontract/` — `DataPoint` chuẩn (value/unit/source/as_of/fetched_at/confidence/status...), validators (`is_stale`, `is_missing`, `is_abnormal`, `compare_sources`, `pick_with_fallback`, `requires_no_decision`), `sources.py` (thứ tự ưu tiên nguồn, đánh dấu domain bị chặn mạng)
- `common/logsetup.py` — logging có cấu trúc (JSON Lines vào `logs/`, KHÔNG thay thế phần in báo cáo ra stdout)
- `scripts/trend.py` giờ **từ chối ghi** snapshot có giá âm/bằng 0 bất thường trước khi vào `data/history.jsonl` (dùng `datacontract`)
- `tests/` — chạy bằng `pytest` (`pip install pytest` nếu chưa có): `python3 -m pytest tests/ -v`

Nguyên tắc: nếu dữ liệu thiếu, hệ thống phải báo rõ "chưa có dữ liệu" — không được vá bằng số 0.

## Cấu hình danh mục & rủi ro (Phase 3)

Số lượng tài sản và hạn mức rủi ro **không còn hard-code trong Python** — sửa ở `config/`:

| File | Nội dung | Sửa khi nào |
|---|---|---|
| `config/portfolio.yaml` | Số lượng vàng, tiết kiệm, tiền mặt, vị thế cổ phiếu, watchlist | Tài sản thay đổi |
| `config/risk_limits.yaml` | Ngưỡng cảnh báo/veto: vàng ≥60% (warning) / ≥70% (critical), tỷ trọng 1 mã tối đa 10%, tổng CP tối đa 20%, quỹ khẩn cấp tối thiểu | Khẩu vị rủi ro thay đổi |
| `config/source_priority.yaml` | Thứ tự ưu tiên nguồn dữ liệu theo loại + danh sách domain bị chặn mạng | Có nguồn mới/network policy đổi |
| `config/decision_rules.yaml` | Khung rule cho Decision Engine (Phase 7) — đã có rule vàng cụ thể | Điền dần qua các phase |

`portfolio/loader.py` nạp 4 file trên; `scripts/networth.py` đọc số lượng từ đây (không còn từ `data/assets.json`, file đó giờ chỉ giữ **metadata định giá vàng** — loại vàng, giá tiệm fallback, nguồn hiệu chuẩn).

⚠️ **Phát hiện quan trọng sau khi wire risk_limits.yaml**: vàng của chủ dự án hiện chiếm 74,7% tài sản — đã vượt cả ngưỡng **CRITICAL (70%)**, không chỉ warning (60%) như cảnh báo cũ từng ghi.

## Module Vàng (Phase 4)

- `gold/conversion.py` — hằng số chính xác `GRAMS_PER_TROY_OUNCE = 31.1034768`, `GRAMS_PER_VIETNAMESE_TAEL = 37.5` (đã sửa sai số ~0,0003tr/lượng của bản xấp xỉ cũ)
- `gold/xuan_trieu_model.py` — ước tính giá tiệm từ XAU/USD real-time, `record_calibration_point()` để tích lũy lịch sử, `mae()` tính sai số dự báo (trả `None` trung thực khi <2 mẫu, không bịa số)
- `gold/indicators.py` — RSI/MACD/MA/Bollinger/volatility cho giá vàng, dùng chung `analytics/ta_core.py` với cổ phiếu; `trend_label()` chỉ trả **xu hướng thị trường thuần túy** (TICH_CUC/TIEU_CUC/TRUNG_TINH) — **hành động danh mục KHÔNG được quyết định ở đây**, đó là việc của Decision Engine (Phase 7)
- `data/normalized/xuan_trieu_gold_history.csv` — lịch sử hiệu chuẩn (hiện 1 điểm, cần tích lũy thêm qua các lần chụp ảnh mới)
- `scripts/gold_price.py` giờ là CLI mỏng gọi `gold/xuan_trieu_model.py`, giữ nguyên contract JSON cũ (tương thích ngược)
- `analytics/ta_core.py` — công thức lõi (sma/ema/rsi/macd/bollinger/atr/volatility) dùng chung cho `scripts/indicators.py` và `gold/indicators.py`, tránh 2 bản cài đặt khác nhau

## Module Tiền gửi (Phase 5)

- `deposits/schema.py` — `DepositRate` (bank/term_months/rate_online/rate_counter/min_deposit/conditions/interest_payment/source)
- `deposits/ranking.py` — loại lãi suất KHÔNG áp dụng cho khoản retail <1 tỷ bằng danh sách từ khóa tường minh (VIP, bancassurance, CCTG, số dư tối thiểu quá lớn), không để AI tự đoán. Đọc `data/normalized/deposit_rates.jsonl` (chỉ lấy bản ghi ngày mới nhất)
- `deposits/strategy.py` — chia vốn theo trọng số kỳ hạn (6T/12T/13+T = 30/40/30%) sau khi trừ quỹ khẩn cấp (`risk_limits.yaml`), tính lãi dự kiến + thiệt hại rút trước hạn; **không tự bịa lãi suất** khi thiếu ngân hàng phù hợp cho 1 kỳ hạn — báo rõ phần chưa phân bổ
- `scripts/deposits_report.py` — CLI demo: `python3 scripts/deposits_report.py`

Đã test với dữ liệu thật: HDBank 7,6%/13T yêu cầu 500 tỷ bị loại đúng, kỳ hạn 13+ tháng "chưa phân bổ" thay vì gán bừa ngân hàng.

## Module Chứng khoán Việt Nam (Phase 6)

- `equity/governance.py` — **enum trạng thái pháp lý chuẩn** (NONE/RUMOR/UNDER_VERIFICATION/SUMMONED_FOR_QUESTIONING/INVESTIGATION_OPENED/INDICTED/CONVICTED) + phân loại theo từ khóa tường minh. Đã fix 1 lỗi tinh vi trước khi commit: `"khởi tố vụ án"` (mở vụ án, chưa chỉ đích danh) và `"khởi tố bị can"` (khởi tố đích danh 1 người) là 2 mức nghiêm trọng khác nhau — không dùng chung từ khóa `"khởi tố"` trần trụi cho mức INDICTED nữa. **Test trực tiếp yêu cầu gốc**: "đang bị mời làm việc để xác minh" → `SUMMONED_FOR_QUESTIONING`, KHÔNG BAO GIỜ `INDICTED`.
- `equity/technical.py` — Relative Volume, Volume z-score, pivot hỗ trợ/kháng cự, breakout, trend state — dùng chung `analytics/ta_core.py`
- `equity/valuation.py` — P/E, P/B, biên an toàn, percentile so lịch sử, 3 kịch bản định giá (thấp/cơ sở/cao)
- `equity/fundamentals.py` — ROE/ROA/biên LN/đòn bẩy/chất lượng dòng tiền — schema sẵn sàng, **chưa có số liệu BCTC thật cho VCB/CTD** (cần nhập tay, đánh dấu `source="BCTC_manual_entry"`, không bịa số)
- `equity/market.py` — độ rộng thị trường, dòng vốn khối ngoại/tự doanh/ETF, chuỗi mua/bán ròng liên tiếp
- `analytics/anomaly_detector.py` — refactor từ `scripts/tick.py`, output chuẩn `{ticker, alert_level, anomaly_type, evidence, conclusion}`, **kết luận luôn là "cần theo dõi, chưa đủ căn cứ"**, không bao giờ khẳng định "giao dịch nội gián"
- `scripts/tick.py` giờ là CLI mỏng gọi `analytics/anomaly_detector.py`, giữ nguyên 2 lệnh `fetch`/`csv`

⚠️ **Rủi ro dữ liệu lớn nhất của Phase 6** (đã ghi từ Audit): `api.hsx.vn`/`services.entrade.com.vn` vẫn bị chặn mạng — `equity/market.py` và `equity/technical.py` nhận input do caller cung cấp (WebSearch hoặc CSV thủ công), không tự fetch được.

## Decision Engine & Risk Officer (Phase 7) — quan trọng nhất

Đây là nơi **DUY NHẤT** trong hệ thống được tạo ra kết luận GIỮ/CHỐT BỚT/... Trước Phase 7, mọi kết luận là AI viết văn xuôi trong bản tin — giờ phải qua rule engine bằng code.

- `decision/action_mapper.py` — 9 action nội bộ (HOLD/TAKE_PARTIAL_PROFIT/DO_NOT_BUY_MORE/DEPOSIT/BUY_SMALL/WATCH/WAIT_FOR_CONFIRMATION/STAND_ASIDE/NO_DECISION) ánh xạ sang 7 nhãn tiếng Việt chuẩn; `NO_DECISION` → đúng nguyên văn `"CHƯA ĐỦ DỮ LIỆU ĐỂ RA QUYẾT ĐỊNH"`
- `decision/risk_officer.py` — **có quyền phủ quyết**. 7 veto rule chuẩn (`stale_critical_data`, `conflicting_critical_sources`, `gold_concentration_critical`, `governance_red_flag`, `insufficient_liquidity`, `missing_financial_data`, `abnormal_price_data`) + downgrade mềm (`gold_concentration_warning` → tự đổi đề xuất mua thành CHỐT BỚT). Nguyên tắc: `approved = (final_action == original_action)`.
- `decision/confidence_score.py` — tính điểm 0-100 bằng công thức có trọng số tường minh (đầy đủ 25% + mới 20% + đồng thuận tín hiệu 25% + lịch sử 15% + không xung đột 10% + rủi ro thấp 5%), không phải AI tự chấm điểm
- `decision/policy_engine.py` — `decide()`: kết hợp xu hướng kỹ thuật + cơ bản + dòng tiền → đề xuất ban đầu → bắt buộc qua Risk Officer → output chuẩn `{asset, action, confidence, reasons, risks, conditions_to_change, data_quality, risk_veto}`. Đã sửa 1 lỗi trước khi commit: confidence phải nhất quán với `data_quality` (không được báo "POOR" mà vẫn cho điểm tin cậy cao)
- `scripts/decide.py` — demo chạy **thật** với dữ liệu tài sản hiện tại: `python3 scripts/decide.py gold TICH_CUC`

**Đã verify bằng chính kịch bản thật của chủ dự án**: vàng 74,7% + xu hướng TÍCH CỰC → hệ thống tự động trả về **"KHÔNG MUA THÊM"** (risk_veto=true), đúng yêu cầu gốc "nếu vàng ≥70% thì không cho phép đề xuất mua thêm vàng".

## Bản tin & Dashboard tự sinh (Phase 8)

- `scripts/run_morning.py` / `scripts/run_evening.py` — orchestrator ghép Tài sản ròng + Vàng (qua Decision Engine) + Tiền gửi + Cảnh báo ngưỡng thành 1 bản tin có cấu trúc. **Không tự fetch dữ liệu thị trường** (network vẫn chặn HOSE/entrade) — giả định `scripts/trend.py append` đã ghi snapshot hôm nay trước đó, đúng quy trình routine hiện tại.
- `reporting/diff_report.py` — mục "THAY ĐỔI SO VỚI BẢN TIN TRƯỚC" bắt buộc trong bản tin chiều; nếu quyết định đổi, **luôn kèm lý do** (không được báo "đã đổi" mà không giải thích)
- `reporting/render_dashboard.py` — sinh `dashboard/auto_dashboard.html` **tự động từ dữ liệu thật**, có badge trạng thái (OK/DÙNG FALLBACK/DỮ LIỆU ĐÃ CŨ/DỮ LIỆU KHÔNG KHẢ DỤNG/NGUỒN XUNG ĐỘT) cho từng số liệu. File `dashboard/ban-tin-dau-tu.html` (thiết kế tay) **không bị ghi đè** — dashboard tự sinh là file riêng, việc chuyển hẳn sang bản tự động là lựa chọn của người vận hành ở bước sau.

⚠️ **1 lỗi thật phát hiện + sửa khi nối dữ liệu**: `data/alerts.json` ghi ngưỡng VCB/CTD theo đơn vị "nghìn đồng" nhưng `data/history.jsonl` lưu giá cổ phiếu theo VND thô — nếu không quy đổi, mọi giá cổ phiếu thật sẽ luôn bị báo "vượt ngưỡng" sai. Đã sửa trong `scripts/run_morning.py`.

Chạy thử: `python3 scripts/trend.py append '<json>' && python3 scripts/run_morning.py` (hoặc `run_evening.py`).

## Khung phân tích

`docs/phuong-phap-phan-tich.md` — khung bắt buộc mọi bản tin phải áp dụng cho VCB/CTD:
- **Phát hiện giao dịch bất thường/nội bộ**: KLGD vs BQ20, giao dịch thỏa thuận, Wyckoff effort-vs-result, và quét công bố giao dịch người nội bộ trên HOSE (kênh hợp pháp — dữ liệu tick từng lệnh không truy cập được qua web)
- **Wyckoff**: 3 quy luật, 4 pha, tín hiệu spring/upthrust/SOS/SOW
- **Nến Nhật**: các mẫu đảo chiều/do dự + nguyên tắc volume xác nhận
- **Buffett**: moat, ROE, định giá có biên an toàn
- **Philip Fisher**: 15 điểm rút gọn + scuttlebutt, quy tắc khi nào bán

Cả hai routine bắn vào phiên Claude Code gốc (session `session_013t34M5Yh9yPtmNDBRg4UYx`), dùng WebSearch lấy số liệu mới nhất kèm nguồn.

## Kênh xuất bản

- **Chat**: bản tin đầy đủ bằng tiếng Việt trong phiên Claude Code
- **Dashboard**: artifact cập nhật cùng URL mỗi kỳ — https://claude.ai/code/artifact/6f0a817e-7841-4b94-8e92-8c2393d0b551

## Cấu hình theo dõi hiện tại

- **Danh mục cá nhân: VCB (Vietcombank) và CTD (Coteccons)** — theo sát giá, tin tức, KQKD, giao dịch khối ngoại từng mã
- Thị trường chung: toàn bộ nhóm ngành + động thái **quỹ đầu tư lớn và khối ngoại** (mua/bán ròng, ETF, dòng vốn trước nâng hạng)
- **Cảnh báo rủi ro doanh nghiệp**: tin lãnh đạo/chủ tịch tập đoàn bị bắt/khởi tố → đánh giá lan tỏa + cách phòng ngừa
- Vàng: trong nước + thế giới, kèm phân tích **địa chính trị/chiến tranh**, **động thái Trump** (đánh giá rủi ro với kinh tế thế giới) và **quyết định/tín hiệu Fed**
- Tiền gửi: khoản dưới 1 tỷ đồng, ưu tiên so sánh online vs tại quầy
- Phân tích: dùng plugin Finance (chuẩn CFA) khi khả dụng trong phiên
