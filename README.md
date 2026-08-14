# Finance-duy — Bản tin Đầu tư tự động

Hệ thống tổng hợp tin tức đầu tư, phục vụ ra quyết định đầu tư.

⚠️ **Thay đổi kiến trúc quan trọng (2026-07-27)**: 2 Claude Code Routine trên
claude.ai (sáng/chiều, dùng WebSearch) đã bị chủ dự án NGỪNG SỬ DỤNG — chúng
từng độc lập ghi vào `data/watchlist.json`/`data/history.jsonl` trên CÙNG
nhánh git với automation local bên dưới, gây xung đột git khiến automation
bị KẸT ÂM THẦM 7 ngày (20–26/7) mà không ai biết. Giờ **chỉ còn 1 nguồn tự
động duy nhất: task Windows local `daily_evening.bat`** (mục kế tiếp). Nếu
2 routine cloud đó vẫn còn tồn tại trên claude.ai (trigger ID cũ:
`trig_01VkDWQ59sqHpXDTyScxmzzV` sáng, `trig_01B8JjRY5Qm71deb3s69XwCb` chiều),
cần xóa hẳn ở giao diện Routines của claude.ai để tránh xung đột tái diễn.

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

## Lịch chạy (automation local — thay thế Routines cloud)

Windows Task Scheduler task `FinanceDuy-BanTinChieu` chạy `scripts/daily_evening.bat` mỗi ngày **18:41 giờ VN**:

1. `git fetch` + `reset --hard origin/<nhánh>` — luôn đồng bộ sạch trước khi làm gì (xem cảnh báo kiến trúc ở trên)
2. `fetch_eod.py VCB CTD` — giá EOD thật từ entrade
3. `fetch_market_snapshot.py chieu` — **XAU/USD thật** (api.gold-api.com) + **tỷ giá USD/VND thật** (portal VCB) + đóng cửa VCB/CTD, ghi vào `data/history.jsonl`
4. `watchlist.py update` — giá thật 11 mã Buffett-list
5. `run_evening.py` — tổng hợp bản tin, chạy Decision Engine, **tự gửi Telegram**
6. `health_check.py --alert` — kiểm tra freshness + an ninh, FAIL thì báo Telegram; `.bat` kiểm exit code ngay sau bước này
7. commit + push `data/` (không rebase — nếu push thất bại chỉ log cảnh báo, KHÔNG tự động merge/rebase để tránh lặp lại sự cố kẹt ở trên)

**Vẫn CHƯA có nguồn tự động** (trung thực để trống trong bản tin, không bịa số) cho: VN-Index, khối ngoại mua/bán ròng, giá SJC/vàng nhẫn tại tiệm trong nước, lãi suất tiết kiệm, tin tức pháp lý/quản trị doanh nghiệp. Những phần này cần nhắn trực tiếp trong phiên chat (WebSearch) khi cần, hoặc `scripts/trend.py append` nhập tay.

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
| `fetch_eod.py` | Tải EOD thật từ `services.entrade.com.vn` (bị chặn network policy trong sandbox claude.ai, đã xác nhận mở được trên laptop local), gộp vào `data/eod/<MÃ>.csv` |
| `fetch_market_snapshot.py` | Tải XAU/USD thật (gold-api.com) + tỷ giá USD/VND thật (VCB portal) + VCB/CTD EOD, ghi vào `data/history.jsonl` qua validate của `trend.py` — lấp khoảng trống sau khi ngừng routine cloud |
| `indicators.py` | RSI(14), MACD, SMA/EMA 20/50/200, Bollinger từ `data/eod/<MÃ>.csv` |
| `backtest.py` | Backtest quy tắc (MA cross…) trên dữ liệu EOD |
| `alerts.py` + `data/alerts.json` | Cảnh báo ngưỡng giá VCB/CTD/vàng bị chạm |
| `journal.py` + `data/journal.jsonl` | Nhật ký giao dịch cá nhân: win-rate, đối chiếu khuyến nghị |
| `review.py` + `data/decisions.jsonl` | Decision review (Phase 9): đối chiếu quyết định Decision Engine với giá thực tế sau đó, chống look-ahead |
| `watchlist.py` + `data/watchlist.json` | Theo dõi hiệu suất danh mục giả lập Buffett-list |
| `networth.py` + `data/assets.json` | Tài sản ròng thực tế (vàng/tiết kiệm/mặt/cổ phiếu) + phân bổ + cảnh báo tập trung |
| `gold_price.py` + `data/gold_model.json` | Ước tính giá vàng nhẫn tại tiệm theo XAU/USD real-time (hiệu chuẩn từ 1 ảnh bảng giá); networth tự dùng để định giá vàng động |
| `health_check.py` | Health check (Phase 10): freshness dữ liệu + vệ sinh an ninh (.env, quét secret); dữ liệu tự động cũ quá 3× ngưỡng thì leo thang WARN → FAIL; exit 1 khi FAIL; `--alert` gửi Telegram (chống spam qua `data/health_state.json`) |

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

## Health check & an ninh (Phase 10)

`python3 scripts/health_check.py` (hoặc `--json`) kiểm tra một lượt:

- **Freshness dữ liệu**: history.jsonl (≤2 ngày), EOD VCB/CTD (≤4 ngày — nới cho cuối tuần), lãi suất chuẩn hóa (≤7 ngày), hiệu chuẩn vàng tiệm (≤30 ngày). Cũ quá ngưỡng → WARN, thiếu hẳn → FAIL.
- **An ninh**: `.env` không bị git track + có trong `.gitignore`; quét pattern token Telegram trong toàn bộ file được track.
- Exit code 1 khi có FAIL → gắn được vào automation/routine như một guard.

Security review 20/07/2026: `.env` sạch (không track, đã ignore), 100 file được track không chứa secret, log chỉ ghi message_id (không ghi token).

### Cảnh báo phải LEO THANG và phải ĐẾN NƠI (14/08/2026)

Health check đúng nhưng vô hiệu: ngày 13/8 nó báo WARN vì `data/eod/VCB.csv` đã cũ **7 ngày** — automation EOD đứng suốt một tuần mà không ai biết. Hai lỗ hổng cộng lại:

1. WARN **không bao giờ leo thang** — cũ 3 ngày hay 30 ngày đều cùng một chữ WARN, nên "cũ quá lâu" không phân biệt được với "cuối tuần nên chưa có".
2. `scripts/daily_evening.bat` gọi health check nhưng `if errorlevel 1` lại nằm sau `git push` — **exit code của health check không bao giờ được đọc**. Guard có mà không ai kiểm.

Nay:

- **Leo thang**: cũ quá `STALE_ESCALATE_FACTOR = 3` lần ngưỡng → **FAIL** (exit 1), không còn WARN vĩnh viễn.
- **Chỉ leo thang nguồn TỰ ĐỘNG**: mỗi mục có cờ `automated`. Lãi suất và hiệu chuẩn vàng tiệm là **nhập tay** — bắt chúng FAIL hằng ngày chỉ tái tạo đúng cái bệnh alert fatigue đã sửa ở mục cảnh báo ngưỡng. Nguồn tay ở lại WARN.
- **`--alert`** gửi Telegram khi FAIL, chống spam bằng `data/health_state.json`: chỉ gửi khi **đổi trạng thái**, hoặc khi vẫn FAIL sau `REALERT_AFTER_DAYS = 3` ngày. Cảnh báo im lặng thì bằng không có; cảnh báo mỗi ngày thì bị bỏ qua.
- `.bat` kiểm errorlevel **ngay sau** health check, ghi rõ vào `logs/daily_task.log`.

## Decision review & backtest nâng cấp (Phase 9)

Hệ thống giờ TỰ THEO DÕI thành tích khuyến nghị của chính nó:

- `decision/decision_log.py` — mỗi lần `run_morning.py`/`run_evening.py` gọi Decision Engine, quyết định được ghi **bất biến** vào `data/decisions.jsonl` kèm giá tham chiếu tại đúng thời điểm đó (chặn ghi trùng ngày+kỳ+tài sản, không bao giờ ghi đè lịch sử)
- `analytics/decision_review.py` — đối chiếu quyết định cũ với giá thực tế SAU đó. **Chống look-ahead-bias là ràng buộc cứng**: chỉ dùng snapshot có kỳ lớn hơn hẳn (sáng < chiều), chỉ so cùng trường giá đã ghi lúc quyết định. Chỉ chấm đúng/sai cho hành động có định hướng giá (MUA THĂM DÒ kỳ vọng tăng, CHỐT BỚT kỳ vọng giảm); GIỮ/KHÔNG MUA THÊM là quản trị rủi ro — trung thực ghi "không chấm điểm" thay vì bịa tiêu chí
- Accuracy lịch sử (khi đủ ≥5 quyết định đã chấm) tự nạp ngược vào trọng số "lịch sử 15%" của confidence score — hệ thống tự biết nó đoán đúng bao nhiêu
- `scripts/review.py` — CLI xem bảng review + tổng kết (`--json` để nhúng bản tin)
- `scripts/backtest.py` nâng cấp: thêm quy tắc RSI (`--rule rsi`, ngưỡng `--buy-th`/`--sell-th`), phí giao dịch (`--fee 0.15` %/chiều), dùng chung `analytics/ta_core.py`; tín hiệu tại phiên i chỉ tính từ dữ liệu tới phiên i
- `scripts/fetch_eod.py` có guard nến chưa đóng cửa: trước 15h giờ VN không ghi bar của ngày hôm nay (nến dở dang làm chỉ báo sai lệch)

## Bản tin & Dashboard tự sinh (Phase 8)

- `scripts/run_morning.py` / `scripts/run_evening.py` — orchestrator ghép Tài sản ròng + Vàng (qua Decision Engine) + Tiền gửi + Cảnh báo ngưỡng thành 1 bản tin có cấu trúc. **Không tự fetch dữ liệu thị trường** (network vẫn chặn HOSE/entrade) — giả định `scripts/trend.py append` đã ghi snapshot hôm nay trước đó, đúng quy trình routine hiện tại.
- `reporting/diff_report.py` — mục "THAY ĐỔI SO VỚI BẢN TIN TRƯỚC" bắt buộc trong bản tin chiều; nếu quyết định đổi, **luôn kèm lý do** (không được báo "đã đổi" mà không giải thích)
- `reporting/render_dashboard.py` — sinh `dashboard/auto_dashboard.html`: bảng **chẩn đoán**, mỗi số liệu kèm badge trạng thái (OK/DÙNG FALLBACK/DỮ LIỆU ĐÃ CŨ/DỮ LIỆU KHÔNG KHẢ DỤNG/NGUỒN XUNG ĐỘT).

⚠️ **1 lỗi thật phát hiện + sửa khi nối dữ liệu**: `data/alerts.json` ghi ngưỡng VCB/CTD theo đơn vị "nghìn đồng" nhưng `data/history.jsonl` lưu giá cổ phiếu theo VND thô — nếu không quy đổi, mọi giá cổ phiếu thật sẽ luôn bị báo "vượt ngưỡng" sai. Đã sửa trong `scripts/run_morning.py`.

## Dashboard bản tin tự sinh (nâng cấp 12/08/2026)

`dashboard/ban-tin-dau-tu.html` trước đây **sửa tay mỗi kỳ**: ~71 cặp toạ độ SVG cộng mọi con số trong thẻ/bảng/chân trang. Một con số sai sẽ vẽ ra đường sai mà không gì báo lỗi, và vì thêm điểm là phải tính lại tay nên biểu đồ bị giới hạn ở "cửa sổ trượt 9 kỳ" — lịch sử cũ bị đẩy khỏi hình dù vẫn còn trong `history.jsonl`.

Nay file này **sinh 100% từ dữ liệu**:

```
python3 scripts/build_dashboard.py           # ghi dashboard/ban-tin-dau-tu.html
python3 scripts/build_dashboard.py --check   # chỉ kiểm tra, không ghi file
```

- `reporting/chart.py` — sinh SVG từ dữ liệu: trục tự chia bước tròn (1–2–5×10^n), `None` = **NGẮT đường** (không nội suy qua chỗ thiếu = không bịa số), nhãn cuối tự tách khi chồng nhau, cột luôn mọc từ gốc 0, màu qua CSS var nên theme sáng/tối tự đổi
- `reporting/dashboard_builder.py` — dựng cả trang; định giá lịch sử dùng **chính mô hình của `networth.py`** (có test chống lệch 2 nguồn). Hiện **toàn bộ** lịch sử, thêm 3 biểu đồ trước đây không có: tổng tài sản theo thời gian, tỷ trọng vàng vs ngưỡng critical, VN-Index
- `analytics/advice_tracker.py` — đếm số kỳ liên tiếp vượt ngưỡng và tỷ trọng đã đi hướng nào; đẩy cảnh báo lên đầu mục rủi ro. Ra đời vì 6 bản tin liên tiếp đều khuyên CHỐT BỚT mà tỷ trọng vàng vẫn bò 74,6% → 75,1% và **không gì trong hệ thống thấy điều đó**

## Kế hoạch giảm tỷ trọng — "bán bao nhiêu là đủ" (13/08/2026)

Khuyến nghị **CHỐT BỚT** treo 14 kỳ trong khi tỷ trọng vàng leo 74,6% → 76,0%. Một phần lý do rất người: lời khuyên trả lời "làm gì" nhưng bỏ trống "**bao nhiêu**", nên không hành động được.

```
python3 scripts/rebalance_plan.py             # 3 mốc mục tiêu để so sánh
python3 scripts/rebalance_plan.py --target 72 # 1 mốc cụ thể
python3 scripts/rebalance_plan.py --json      # để nhúng
```

`decision/rebalance.py` tính đúng 3 ràng buộc thực tế thay vì làm tròn cho tiện:

1. **Bán theo CHỈ** (1 lượng = 10 chỉ) — không bán được 0,516 lượng; số bán làm tròn **LÊN** vì làm tròn xuống thì không chạm mục tiêu
2. **Giá bán = giá tiệm MUA vào**, không phải giá niêm yết bán ra — đây là tiền thật nhận được
3. **Chi phí spread mua–bán** nếu sau này mua lại, nêu rõ nhưng không trừ vào tổng (chưa mua lại)

Không mô hình thuế giao dịch vàng: cá nhân bán vàng vật chất ở VN không có thuế giao dịch riêng, chi phí thật là spread — không bịa thêm khoản phí.

Kế hoạch đưa **3 mốc** thay vì áp 1 con số, vì "về mức nào" là khẩu vị của chủ danh mục chứ không phải kết luận kỹ thuật. Mục này tự ẩn khi tỷ trọng đã dưới critical, và xuất hiện trong cả dashboard lẫn bản tin (Telegram).

## Sai số mô hình định giá vàng — đo được, không im lặng (13/08/2026)

Toàn bộ con số "vàng chiếm 76% tài sản" (thứ kích hoạt khuyến nghị CHỐT BỚT) dựa trên hệ số quy đổi lấy từ **đúng một tấm ảnh** bảng giá tiệm ngày 18/7. Một con số trông rất chắc chắn mà không ai biết nó sai bao nhiêu.

`gold/calibration.py` đo sai số từ **11 quan sát thật** trong `history.jsonl`:

| Đo được | Giá trị |
|---|---|
| k = nhẫn trong nước / thế giới quy đổi | n=11, mean 1,1368, stdev 0,0081 |
| Lệch tối đa khỏi trung bình | 1,48% |
| **Tương quan Pearson(XAU, k)** | **−0,753** → giá trong nước **TRỄ** so với thế giới |
| MAE trung bình phẳng → hồi quy theo XAU | 0,55% → 0,37% (tốt hơn 32%) |

**Nguyên tắc quan trọng nhất: không ngoại suy hồi quy ra ngoài vùng dữ liệu.** Khoảng đã hiệu chuẩn là XAU 3.984–4.134$; XAU hiện tại 4.340$ nằm ngoài. Ngoại suy sẽ lệch k tới −3,3% (≈29tr trên danh mục này) — sai một cách rất tự tin. Nên: trong khoảng dùng hồi quy, ngoài khoảng dùng trung bình + nới biên theo mức trôi mà độ dốc đã đo hàm ý.

**Biên bất đối xứng** vì đã biết hướng sai: tương quan âm nghĩa là khi thế giới tăng nhanh, ước tính thường CAO hơn giá tiệm thật → biên dưới rộng hơn biên trên (hiện −3,7% / +1,5%). Biên đối xứng ở đây là nói dối một cách lịch sự.

Phân biệt rành mạch hai thứ có số mẫu khác nhau: **MỨC giá vẫn 1 mẫu** (chỉ ảnh bảng giá mới sửa được), **BIÊN từ 11 quan sát**. `networth.py` và dashboard giờ hiện khoảng thay vì một con số.

Kiểm chứng có ý nghĩa: dù giá vàng ở đáy khoảng, tỷ trọng vẫn 75,3% > ngưỡng 70% — **khuyến nghị CHỐT BỚT không phải sản phẩm của sai số mô hình** (có test khẳng định điều này).

## Cảnh báo ngưỡng tự làm mới (13/08/2026)

`data/alerts.json` đặt ngưỡng theo giá 18/7 rồi không cập nhật. Đo ngày 13/8: **3 trong 6 ngưỡng kích hoạt vĩnh viễn**. Rõ nhất là `gold-res` "vượt 4.060$" khi XAU đã 4.340$ — báo động ở mọi lần chạy suốt nhiều tuần, không mang thông tin nào, và làm loãng những cảnh báo thật. Cùng họ lỗi với vụ khuyến nghị lặp 14 kỳ: trạng thái cần làm mới mà không có gì làm mới nó.

```
python3 scripts/alerts.py '{"VCB":60.3,"CTD":62.4,"XAUUSD":4340}'   # quét
python3 scripts/alerts.py --list                                     # kèm số kỳ đã chạm
python3 scripts/alerts.py --reanchor '{...}'                         # đặt lại theo biến động thật
```

`analytics/alert_health.py`:

- **Đếm số KỲ liên tiếp** chạm ngưỡng (`data/alert_state.json`). Lần đầu là TIN; quá 3 kỳ liên tiếp thì báo "ngưỡng lỗi thời, cần đặt lại" thay vì báo như tin mới. Bộ đếm tính theo **kỳ** (ngày + sáng/chiều) nên chạy lại CLI trong cùng buổi không tự đẩy ngưỡng thành lỗi thời — nó đo diễn biến thị trường, không đo số lần gõ lệnh.
- Giá **thoát ngưỡng rồi chạm lại** là diễn biến mới → báo lại như tin. Thiếu giá thì **bỏ qua, không reset** bộ đếm (thiếu giá không phải bằng chứng đã thoát ngưỡng).
- **`--reanchor`** đặt ngưỡng cách giá hiện tại 1,5×biến động thật của chính tài sản đó (ATR(14) từ `data/eod/` cho cổ phiếu, độ lệch chuẩn ngày từ `history.jsonl` cho vàng). Ngưỡng tôn trọng biến động của tài sản thì mới không kêu vì nhiễu. Thiếu giá hoặc thiếu dữ liệu biến động → **giữ nguyên ngưỡng cũ** và nói rõ vì sao, không đặt bằng số bịa.
- Reanchor cũng **viết lại ghi chú**: nếu không, ghi chú tay theo mức cũ sẽ nói ngược với mức mới (đã gặp thật: ngưỡng thành 4.410$ mà ghi chú vẫn ghi "Vượt 4.060$"). Nhận định tay gốc được giữ ở `note_manual`.
- Mục cảnh báo trong bản tin dùng **chung** module này — trước đây nó có bản sao logic riêng nên không thấy được ngưỡng lỗi thời (nguồn sự thật thứ ba cho cùng phép so sánh).

## Phí cơ hội của khuyến nghị phòng thủ (14/08/2026)

Decision review chấm đúng/sai cho quyết định **có định hướng giá**, còn GIỮ/CHỐT BỚT/KHÔNG MUA THÊM ghi "quản trị rủi ro — không chấm". Đúng nguyên tắc, nhưng hệ quả đo được: **11/13 quyết định thật không bao giờ được đánh giá**, accuracy vĩnh viễn `None`, thành phần "lịch sử" (15% trọng số) của confidence score mãi dùng giá trị trung tính — hệ thống không học được gì mà vẫn hiện điểm tin cậy cao.

`analytics/opportunity_cost.py` đo thứ đo được, và đóng khung đúng bản chất: **phí bảo hiểm**, không phải "lời khuyên sai". Bảo hiểm không sai khi nhà không cháy — nhưng người mua có quyền biết đã trả bao nhiêu.

```
python3 scripts/review.py     # decision review + mục PHÍ CƠ HỘI ở cuối
```

Kết quả thật trên `data/decisions.jsonl` (14/08): 3 khuyến nghị CHỐT BỚT, trung bình **+3,49%** bỏ lỡ, xấu nhất +5,48%.

Hai vấn đề đo lường phải xử lý cho tử tế:

- **Trường giá gốc ngừng thu thập.** Quyết định 22/7 neo vào `ring_sell`, mà giá vàng trong nước dừng từ 27/7 → so trường gốc ra +0,00%, đúng kỹ thuật mà vô dụng. Nay có `FALLBACK_FIELDS`, và chọn phép đo có **nhiều thời gian trôi qua nhất** thay vì "ưu tiên trường gốc" — nhưng luôn neo giá ở **cả hai đầu bằng cùng một trường** (không bao giờ so `ring_sell` 147,5 với `xauusd` 4.340). Kết quả xấp xỉ được **đánh dấu `[xấp xỉ]` kèm mức sai số đã đo** (~2,3%/6 ngày, từ `gold/calibration.py`).
- **Phải nêu cả hai vế.** `premium_in_vnd()` trừ lãi tiền gửi thu được vào phần tăng giá bỏ lỡ: chốt bớt mất phần tăng NHƯNG tiền về ngân hàng sinh lãi. Nêu vế mất mà giấu vế được là dẫn dắt chứ không phải tư vấn — nên cảnh báo "khuyến nghị treo" trên dashboard giờ hiện **cùng lúc** cả rủi ro tập trung lẫn cái giá đã trả.

Chống look-ahead dùng **đúng** `later_snapshots()` của decision_review — không mở đường tắt thứ hai.

## Quy trình mỗi kỳ bản tin (đã gộp còn 2 lệnh)

```
python3 scripts/trend.py append '<json snapshot>'   # 1 lệnh, 3 việc
python3 scripts/run_morning.py                      # hoặc run_evening.py
```

`trend.py append` giờ làm cả 3 việc, cố ý gộp vì từng bỏ sót thật:

1. Ghi snapshot — chặn giá âm/bằng 0 **và giá bất khả thi so với kỳ trước**
2. Đồng bộ lãi suất sang `data/normalized/deposit_rates.jsonl` (`deposits/sync.py`)
3. Chạy Decision Engine và ghi vào `data/decisions.jsonl`

Vì sao gộp: 6 bản tin 20–22/7 đều ra khuyến nghị nhưng `decisions.jsonl` chỉ có **2** bản ghi — orchestrator bị bỏ qua nên decision review + confidence score (Phase 9) chạy trên dữ liệu rỗng. `append` là bước LUÔN được gọi nên gắn vào đây thì không còn đường bỏ sót.

### Chặn giá bất khả thi (`analytics/price_sanity.py`)

4/6 bản tin phải viết tay cảnh báo Simplize trả giá CTD 73.800đ khi giá đã xác minh là 59.100đ. Việc phát hiện phụ thuộc vào người soạn **nhớ** rằng nguồn đó không đáng tin.

Nay dùng ràng buộc cứng của sàn thay cho danh sách đen — **HOSE ±7%/phiên, HNX ±10%, UPCoM ±15%**: giá lệch quá biên độ tích lũy trong số phiên đã trôi qua là *bất khả thi*, sàn không cho khớp ở mức đó. Nhờ vậy bắt được **mọi** nguồn sai, kể cả nguồn chưa từng gặp. Tham chiếu cách > 10 phiên thì trả "không đủ căn cứ" thay vì gật đầu vô nghĩa.

Sự kiện doanh nghiệp thật (chia tách, thưởng cổ phiếu) hợp lệ vượt biên độ → `append ... --force`, và lý do được ghi thẳng vào `risk_flags.note_forced_append` để việc bỏ qua kiểm tra không bao giờ âm thầm.

## Gửi bản tin qua Telegram

Bot `@Tintucstock_bot` đã tạo, token lưu trong `.env` (KHÔNG commit — xem `.env.example` để biết cấu trúc).

```
python3 notifications/telegram.py whoami   # lấy chat_id sau khi bấm /start với bot, lưu vào .env
python3 notifications/telegram.py send "nội dung bản tin"
```

⚠️ **Đang bị chặn bởi network policy của environment** (`api.telegram.org` — xác nhận qua `curl $HTTPS_PROXY/__agentproxy/status`: "gateway answered 403... host: api.telegram.org:443"). Cần vào cấu hình Network policy của environment trên claude.ai và thêm domain này vào danh sách cho phép trước khi 2 lệnh trên chạy được. `common/env.py` nạp `.env` bằng parser tối giản (không dependency ngoài).

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
