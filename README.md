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
6. `send_report.py plan` — **thứ Hai hằng tuần**: gửi báo cáo kế hoạch (sức mua sau lạm phát + mục tiêu 10 tỷ). Không gửi hằng ngày vì nội dung chỉ đổi khi giá tài sản đổi — gửi mỗi ngày sẽ thành nhiễu và bị bỏ qua, đúng bệnh "cảnh báo lặp mãi" đã sửa ở `alert_health.py`
7. `health_check.py --alert` — kiểm tra freshness + an ninh, FAIL thì báo Telegram; `.bat` kiểm exit code ngay sau bước này
8. commit + push `data/` (không rebase — nếu push thất bại chỉ log cảnh báo, KHÔNG tự động merge/rebase để tránh lặp lại sự cố kẹt ở trên)

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
| `plan.py` + `config/plan.yaml` | **Tầng kế hoạch**: lợi suất THỰC sau lạm phát, bào mòn sức mua, bảng độ nhạy 10 năm, đối chiếu mục tiêu tài chính |
| `send_report.py` | Gửi báo cáo qua Telegram (`plan`/`morning`/`evening`), `--preview` để xem trước mà không gửi |
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

## Điểm tin cậy phải ĐO được (14/08/2026)

Cả **13/13 quyết định** trong `data/decisions.jsonl` từ 20/7 đến 10/8 đều ghi đúng một con số: `confidence: 92`, `data_quality: GOOD`. Không kỳ nào khác kỳ nào — kể cả những kỳ mà giá vàng nhẫn trong nước đã ngừng thu thập 23 ngày, `history.jsonl` cũ 4 ngày, và mô hình định giá vàng đang ngoại suy ngoài vùng hiệu chuẩn.

Mổ ra thì 92 là phép cộng, không phải bằng chứng — **3 trong 6 thành phần là hằng số**:

| Thành phần | Trọng số | Thực tế trước khi sửa |
|---|---|---|
| Độ đầy đủ dữ liệu | 25% | mặc định **100**, không caller nào truyền giá trị khác |
| Độ mới dữ liệu | 20% | mặc định **100**, như trên |
| Đồng thuận tín hiệu | 25% | chỉ nối được `trend_label`; công thức tính 1/1 = **100% đồng thuận** |
| Lịch sử chính xác | 15% | 50 trung tính (đã xử lý ở mục phí cơ hội) |
| Xung đột nguồn | 10% | 100 |
| Rủi ro | 5% | 100 |

Hệ quả kép: nhánh hạ cấp `data_quality = "FAIR"` (khi hai chỉ số dữ liệu < 80) **không bao giờ chạy được**, và `RiskContext.data_stale` tồn tại nhưng chưa caller nào set.

Ba thay đổi:

- **`analytics/data_quality.py`** đo thật độ đầy đủ + độ mới từ các nguồn mà quyết định *thực sự* dựa vào. Ngưỡng tuổi **dùng lại đúng ngưỡng của health check** (`STALE_ESCALATE_FACTOR` giờ định nghĩa ở đây, health check import về) — một hệ thống không được có hai định nghĩa "quá cũ". Điểm lấy **MIN trên nguồn trọng yếu**, không lấy trung bình (trung bình cho một nguồn tươi che một nguồn mục); nguồn **đối chiếu** cũ thì ghi chú rõ nhưng không kéo điểm. **Thiếu hẳn ≠ cũ**: thiếu tính vào completeness, cũ tính vào freshness — không phạt chồng một sự việc.
- **Mặc định đổi từ `100.0` sang `None` = "chưa đo"**, quy về trung tính 50 kèm dòng lý do. Quên đo phải làm giảm điểm, không được thưởng điểm tuyệt đối — "chưa kiểm tra" không bao giờ được đọc thành "đã kiểm tra và hoàn hảo".
- **Một tín hiệu không phải là đồng thuận.** `signal_agreement_from_labels` giờ cần ≥2 tín hiệu mới chấm; dưới ngưỡng trả 50 trung tính, giống hệt cách xử lý khi không có tín hiệu nào.

Kết quả trên dữ liệu thật hôm nay: **92/GOOD → 70/FAIR**, kèm lý do nêu thẳng nguồn ghìm điểm ("XAU/USD cũ 4 ngày, ngưỡng 2") và ("chỉ có 1 nhóm tín hiệu"). **Hành động không đổi** — vẫn CHỐT BỚT do Risk Officer veto; đây là sửa mức tin cậy, không phải đổi lời khuyên.

Một phát hiện đi kèm, đáng sợ hơn con số: `gold/indicators.py` đọc `data/normalized/xuan_trieu_gold_history.csv`, file này có **đúng 1 dòng, ngày 18/7** — xử lý ở mục kế tiếp. Chất lượng dữ liệu nền giờ hiện thành một thẻ riêng trên dashboard, ngay trong mục rủi ro chứ không giấu ở chân trang.

## Xu hướng đo trên dữ liệu thật + bất biến "rủi ro tệ hơn thì lời khuyên không được nhẹ đi" (14/08/2026)

Ba lỗi nối nhau, cùng một gốc: **hệ thống tự tin hơn dữ liệu của nó**.

### 1. Đo xu hướng trên file 1 dòng, trong khi có 19 quan sát thật

`gold/indicators.py` mặc định đọc `data/normalized/xuan_trieu_gold_history.csv` — file có **đúng 1 dòng, ngày 18/7**. Mọi RSI/MACD/SMA trả `None` suốt gần một tháng. Cùng lúc đó `data/history.jsonl` có **19 quan sát XAU/USD thật** không ai dùng.

Đo trên chuỗi đó ra ngay **RSI(14) = 78,3** — vùng quá mua rõ rệt, một tín hiệu hệ thống chưa từng nhìn thấy lần nào. Nay `analyze()` mặc định dùng chuỗi thế giới; chuỗi giá tiệm vẫn đo được khi cần đối chiếu.

Không "lấp" file hiệu chuẩn bằng dữ liệu suy ra: `ring_sell` (giá niêm yết) và `shop_buy_trieu` (giá tiệm MUA vào) là hai đại lượng khác nhau — quy đổi qua lại sẽ là bịa số liệu hiệu chuẩn.

### 2. "Chưa đo được" bị trả về thành "đi ngang"

`trend_label()` trả `TRUNG_TINH` cho **cả hai** trường hợp: thiếu dữ liệu, và thị trường thật sự trung tính. Một đằng là chưa có kết luận, một đằng là kết luận — gộp lại thì bản tin in "Xu hướng kỹ thuật: TRUNG_TINH" như một phát hiện, và bộ đếm đồng thuận tính nó là 1 tín hiệu có mặt. Nay thiếu dữ liệu trả **`None`**.

Kèm theo: cũ đòi có **đủ cả** RSI lẫn MACD mới chấm. MACD cần ≥26 điểm, nên với 19 điểm hiện có, RSI 78,3 vẫn bị vứt đi và báo "trung tính". Nay chấm trên chỉ báo **đang có**, và `trend_evidence()` nói rõ đã dùng cái nào — nhãn không kèm căn cứ thì không phản biện được.

### 3. Rủi ro tệ hơn mà lời khuyên nhẹ đi

Sửa (1) làm lộ ra một mâu thuẫn có sẵn. Đo cùng một danh mục vàng:

| Tỷ trọng vàng | Tín hiệu | Khuyến nghị (trước khi sửa) |
|---|---|---|
| 65% (warning) | TICH_CUC | CHỐT BỚT |
| **76% (critical)** | TICH_CUC | **KHÔNG MUA THÊM** ← nhẹ hơn |
| 76% (critical) | TRUNG_TINH | CHỐT BỚT |

Tập trung **tệ hơn** mà khuyến nghị **dịu đi**, và kết quả còn lật theo việc tín hiệu thị trường tình cờ là gì — trong khi vàng tăng giá chính là thứ làm tỷ trọng tệ thêm. Đây không phải lựa chọn khẩu vị, đây là lỗi.

`decision/risk_officer.py` nay có thang `EXPOSURE_SEVERITY` và hàm `stricter()`, giữ một **bất biến có test**: tỷ trọng càng vượt ngưỡng, khuyến nghị không bao giờ nhẹ đi (`test_bat_bien_dung_o_MOI_muc_ty_trong` quét 8 mức từ 30% đến 90%). Cấu hình đặt nấc critical nhẹ hơn nấc warning sẽ được **nâng lên và nói rõ**, không âm thầm.

**Yêu cầu gốc "vàng ≥70% thì KHÔNG cho phép đề xuất mua thêm" không mất**: đề xuất mua vẫn bị veto (`gold_concentration_critical`), câu "KHÔNG MUA THÊM vàng" vẫn được ghi thẳng vào cảnh báo, và CHỐT BỚT về logic đã bao hàm việc không mua thêm. Muốn quay lại hành vi cũ thì đổi `above_critical_action` trong `config/decision_rules.yaml`.

Test cũng đổi theo tinh thần đó: thay vì neo cứng `final_action == "DO_NOT_BUY_MORE"` (chính cách viết đó đã khoá một cấu hình mâu thuẫn suốt), giờ kiểm **điều thực sự được yêu cầu** — đề xuất mua bị chặn, câu "KHÔNG MUA THÊM" được nói ra, và hành động cuối không nhẹ hơn mức đó.

## Rủi ro tập trung quy ra TIỀN (14/08/2026)

Khuyến nghị **CHỐT BỚT** đã treo **19 kỳ** và không được thực hiện. Đọc lại nội dung nó nói thì dễ hiểu vì sao: *"vàng 76%, vượt ngưỡng critical 70%"* — một tỷ lệ phần trăm so với một tỷ lệ phần trăm khác. Không kỳ nào nói rủi ro đó **bằng bao nhiêu tiền**.

`decision/rebalance.py` đã trả lời "bán bao nhiêu". `analytics/downside.py` trả lời vế còn lại: **"bán để tránh cái gì"**.

| Kịch bản | XAU/USD | Tổng tài sản | Thay đổi | % vàng sau |
|---|---|---|---|---|
| −20% | 3.472 $ | 994 tr | **−178 tr** | 71,7% |
| −15% | 3.689 $ | 1.039 tr | **−134 tr** | 73,0% |
| −10% | 3.906 $ | 1.084 tr | −89 tr | 74,1% |
| +10% | 4.774 $ | 1.262 tr | +89 tr | 77,7% |
| +20% | 5.208 $ | 1.351 tr | +178 tr | 79,2% |

Điểm phản trực giác đáng chú ý: **kịch bản xấu làm cảnh báo tập trung tự tắt** — vàng −20% thì tỷ trọng tự về 71,7%. Nhưng về bằng cách **mất tiền**, không phải bằng cách cân lại danh mục. Câu đó giờ in thẳng trong bản tin.

Kế hoạch bán cũng được nối với kịch bản: *"bán 10 chỉ → nếu vàng giảm 15%, phần đã bán tránh được 20,6 tr sụt giá"* (không cộng lãi tiền gửi vào đây — lãi đã nằm ở dòng trên, cộng lần nữa là đếm trùng).

Đây là chỗ dễ trượt thành hù dọa nhất trong cả dự án, nên ba ràng buộc được đóng thành test:

- **Kịch bản không phải dự báo** — số học "nếu…thì", không xác suất nào gắn kèm.
- **Đối xứng** — chạy cả hai chiều cùng biên độ. Chỉ bày kịch bản giảm là dẫn dắt bằng cách chọn dữ liệu, đúng lỗi mà `opportunity_cost.py` đã tránh ở phía ngược lại.
- **Nói rõ mẫu KHÔNG nói được gì** — đo được lệch chuẩn 1,33%/kỳ và sụt sâu nhất 2,50% trên 19 quan sát, nhưng mẫu 3 tuần của một thị trường đang tăng không cho biết vàng có thể giảm sâu tới đâu. Trình bày mức sụt trong mẫu như kịch bản xấu nhất là hiểu sai dữ liệu một cách nguy hiểm.

Thiên lệch đã biết cũng nêu thẳng: mô hình giả định tỷ lệ giá trong nước/thế giới không đổi, trong khi tương quan đo được là −0,75 — nên các mức lỗ trên **nghiêng về phía thận trọng**.

### Biểu đồ có dấu (`reporting/chart.py`)

`bar_chart` kẹp chiều cao ở 0 nên mọi cột âm biến mất. Thêm `diverging_bar_chart()`: cột mọc hai chiều từ đường 0, trục **đối xứng** quanh 0 (lệch trục sẽ phóng đại một phía — với dữ liệu lãi/lỗ đó là bóp méo câu chuyện, không chỉ là thẩm mỹ).

Màu **không** dùng cặp đỏ–xanh lá quen thuộc: chạy `validate_palette.js` trên cặp đó ra **ΔE deutan = 5,9**, dưới cả ngưỡng sàn 6 — người mù màu đỏ–lục không tách được hai cực. Cặp **cam–xanh dương** đạt ΔE 24,7 (sáng) và 26,8 (tối). Dấu +/− vẫn ghi thẳng trên từng cột nên nghĩa không bao giờ phụ thuộc riêng vào màu.

Biểu đồ nhiều cột giờ cũng **tự cuộn ngang** như bảng: ở 390px, SVG 620px co lại 55% làm chữ 11px còn ~6px — đúng thì có đúng nhưng không ai đọc được.

## Khoản tiết kiệm — 21% tài sản mà hệ thống chưa biết gì (14/08/2026)

`config/portfolio.yaml` khai báo khoản tiết kiệm bằng **đúng một dòng**:

```yaml
savings:
  principal_vnd: 246000000
```

Không lãi suất, không ngân hàng, không kỳ hạn, không ngày gửi. Ba hệ quả, không cái nào nhỏ:

1. **Hệ thống tối ưu tiền SẮP có mà không nhìn tiền ĐANG có.** `decision/rebalance.py` tính "bán vàng thu 137tr, gửi 8,0%/năm → lãi thêm 11,0 tr/năm" và nhắc 19 kỳ liền. Nhưng 246tr đang nằm sẵn thì hưởng mức nào? Không ai biết — và khoảng chưa biết đó đáng **1,2–8,6 tr/năm**, đầu trên còn lớn hơn phần lãi thêm của cả kế hoạch bán vàng về 69% (7,7 tr/năm).
2. **Định giá lịch sử coi tiết kiệm là tài sản không sinh lãi**, nên đường "tổng tài sản theo thời gian" gán toàn bộ biến động cho vàng.
3. **Không có ngày đáo hạn thì không cảnh báo được tái tục.** Sổ đến hạn không tất toán thường tự quay vòng theo lãi suất **niêm yết tại quầy** — thường thấp hơn hẳn mức online đã ký. Đây là khoản rò rỉ tiền phổ biến và im lặng.

`deposits/holding.py` xử lý cả hai trạng thái, và **không bịa số ở trạng thái nào**:

**Khi chưa khai báo** — bảng lượng hóa chính khoảng chưa biết, để việc xin số liệu là đề nghị có căn cứ chứ không phải lời nhắc chung chung (loại đã bị bỏ qua 19 kỳ ở chỗ khác):

| Nếu đang ở | Mức tốt nhất đo được | Chênh | Trên 246 tr |
|---|---|---|---|
| 4,5%/năm | 8,00%/năm | 3,50% | **8,6 tr/năm** |
| 5,5%/năm | 8,00%/năm | 2,50% | **6,2 tr/năm** |
| 6,5%/năm | 8,00%/năm | 1,50% | 3,7 tr/năm |
| 7,5%/năm | 8,00%/năm | 0,50% | 1,2 tr/năm |

Mỗi dòng là một **giả định** để đo khoảng chưa biết — không phải phán đoán về mức thật. Chưa khai báo thì tài sản tính theo phần gốc: thấp hơn thực tế, và đó là hướng sai **an toàn**.

**Khi đã khai báo** (điền `bank / rate_pct / term_months / start_date`) — lãi tích lũy, so sánh với mức tốt nhất đang đo được, và cảnh báo trước 14 ngày:

```
Khoản đang gửi: 246 tr @ 6,50%/năm · VIB · kỳ hạn 12 tháng
- Lãi tích lũy tới nay: 15,6 tr
- ⚠️ Thấp hơn mức tốt nhất đang đo được (8,00%/năm) — chênh 3,7 tr/năm
- ⚠️ Còn 5 ngày tới hạn (20/08/2026). Để tự quay vòng thường rơi vào lãi
     suất tại quầy, thấp hơn mức online.
```

Thiếu dữ liệu trả `None`, **không trả 0** — 0 sẽ bị đọc thành "chưa sinh lãi đồng nào", khác hẳn "chưa biết".

## Trụ cột cổ phiếu: xây xong nhưng chưa cắm điện (14/08/2026)

Ba bằng chứng, không phải cảm tính:

- `run_morning.py::section_tong_quan()` in nguyên văn *"Cổ phiếu watchlist: **xem mục Chứng khoán bên dưới**"* — trong khi **không có mục nào như vậy**. Bản tin trỏ tới một phần không tồn tại, ở mọi kỳ, suốt từ đầu.
- `equity/technical.py::technical_snapshot()` đã có đủ RSI, MACD, MA, relative volume, z-score, hỗ trợ/kháng cự, breakout, trend state — và chạy được ngay trên **43 phiên EOD thật** của VCB/CTD. Không caller nào gọi.
- `decision/policy_engine.py` có sẵn nhánh `asset_class == "equity"`, `risk_officer` có rule quản trị doanh nghiệp + rule tập trung cổ phiếu. **Chưa dòng code nào chạy Decision Engine cho một mã cổ phiếu.**

Nối lại qua `equity/signals.py` (phần nối, không phải phần tính — công thức vẫn ở `equity/technical.py`). Kết quả thật:

```
- VCB 60,30 (EOD 2026-08-10) → ĐỨNG NGOÀI (tin cậy 80/100)
  - đo trên 43 phiên EOD: RSI(14)=59,1, MACD hist=+0,66, giá trên SMA20 (57,33)
  - hỗ trợ 60,20 · kháng cự 61,00
- CTD 62,40 (EOD 2026-08-10) → ĐỨNG NGOÀI (tin cậy 80/100)
  - đo trên 43 phiên EOD: RSI(14)=47,3, MACD hist=+0,91, giá trên SMA20 (60,77)
  - hỗ trợ 54,70 · kháng cự 65,00
```

### Lỗi ngữ nghĩa lộ ra ngay khi nhánh equity được dùng thật

Chủ danh mục **đã bán hết cổ phiếu** (19/7), nên VCB/CTD chỉ là danh sách theo dõi. Nhánh cũ trả `HOLD` khi xu hướng tích cực — nhưng **không thể "GIỮ" thứ mình không nắm giữ**; đó là lời khuyên không thực hiện được. `DecisionInput` nay có `has_position` (mặc định `False`, khớp thực tế danh mục này), và không có vị thế thì xu hướng tích cực ra **ĐỨNG NGOÀI**.

Loại lỗi này chỉ lộ ra khi code được đem dùng thật — đúng lý do không nên để một nhánh "xây xong" nằm im.

### Một định nghĩa "xu hướng" cho cả vàng lẫn cổ phiếu

Logic chấm nhãn xu hướng chuyển vào `analytics/ta_core.py` (`indicator_votes`, `trend_from_indicators`); `gold/indicators.py` uỷ quyền sang đó. Chép nó vào `equity/` sẽ tạo nguồn sự thật thứ hai cho cùng một câu hỏi — đúng cái bẫy mà chính `ta_core.py` ra đời để tránh (từng có 2 bản cài đặt RSI). Có test khẳng định hai bên luôn cho cùng kết quả.

Cảnh báo **KLGD ≥ 1,5× bình quân** dùng lại đúng ngưỡng của `scripts/trend.py report` — một hệ thống, một ngưỡng — và dẫn thẳng sang phần soi giao dịch thỏa thuận / công bố giao dịch người nội bộ trong `docs/phuong-phap-phan-tich.md`.

## Rà soát watchlist 11 mã (15/08/2026)

`data/fundamentals.jsonl` — số liệu cơ bản THẬT cho 11 mã watchlist + 1 bản ghi bối cảnh thị trường (`_MARKET`), thu thập bằng WebSearch, **mỗi dòng kèm nguồn và ngày thu thập**. Trước đây `equity/fundamentals.py` chỉ có schema và công thức, không có số liệu nào — đúng chủ ý (không bịa), nhưng cũng có nghĩa mọi chỉ tiêu cơ bản đều trống.

Báo cáo đầy đủ: **[Sổ tay 11 mã](https://claude.ai/code/artifact/ea8c7eb4-4121-4635-b916-d2ed103d92a2)**.

Bốn phát hiện đáng ghi lại:

- **HPG** — LNST quý II **6.424 tỷ (+51%)**, HRC 1,9 triệu tấn (+64%, kỷ lục), khối ngoại gom, nằm trong danh sách dự báo vào rổ FTSE — mà giá **thủng đáy 1 năm**. Kết quả và giá đi ngược chiều nhau.
- **PNJ** — quý II **lỗ 283 tỷ** (cùng kỳ lãi 437 tỷ) do trích lập dự phòng **865,5 tỷ** cho nghĩa vụ mua lại kim cương; giá giảm 48,5% trong tháng 7, đáy 6 năm. Nghĩa vụ còn đang phát sinh (giá trị mua lại vượt tiền + đầu tư tài chính hơn 3.000 tỷ) nên **rủi ro chưa định lượng được** — đó mới là lý do tránh, không phải vì giá đã giảm sâu.
- **VCB** — LNTT quý II +58%, nợ xấu 0,61% vẫn thấp nhất hệ thống, nhưng **nợ nhóm 4 (nghi ngờ) tăng 451%** lên 1.227 tỷ. Tuyệt đối còn nhỏ, nhưng nhóm 4 là bậc ngay trước nợ có khả năng mất vốn.
- **CTD** — backlog **51.600 tỷ** cao nhất lịch sử, nhưng biên LNST chỉ **~2,3%** (788/34.340). Backlog là doanh thu tương lai, chưa phải lợi nhuận tương lai.

Giới hạn đã nêu thẳng trong báo cáo: chỉ VCB/CTD có chuỗi EOD nên chỉ 2 mã đó có chỉ báo kỹ thuật thật; các bội số P/E là **của công ty chứng khoán**, trích lại kèm nguồn chứ không tự tính (chưa nhập EPS/giá trị sổ sách); số cơ bản lấy từ tin BCTC công bố, **chưa đối chiếu BCTC gốc**.

## Tầng kế hoạch: sức mua, không phải số dư (15/08/2026)

Đây là tầng biến dự án từ **theo dõi giá** thành **quản lý tài sản**, và nó bắt đầu từ một dữ kiện mà hệ thống chưa từng nhắc tới lần nào trong toàn bộ lịch sử bản tin: **lạm phát**.

Mọi con số đã nói với chủ danh mục cho tới nay đều là **danh nghĩa** — "tiền gửi 8,0%/năm", "lãi thêm 11 tr/năm", "danh mục 1.173 tr". Với **CPI bình quân 7 tháng 2026 là +4,39%** (Tổng cục Thống kê), khoảng cách giữa hai cách nói là khoảng cách giữa hai kết luận trái ngược:

| Khoản | Danh nghĩa | **THỰC** | Nhận định |
|---|---|---|---|
| Tiền mặt 35 tr | 0,00% | **−4,21%/năm** | đang **mất 1,47 tr/năm** sức mua |
| Tiết kiệm nếu ở 4,5% | +4,50% | **+0,11%/năm** | gần như đứng yên |
| Tiết kiệm ở mức tốt nhất 8,0% | +8,00% | **+3,46%/năm** | gấp đôi sức mua sau ~20 năm |

Nói "gửi 4,5%/năm" nghe như đang sinh lời. Nói "thực +0,11%/năm" mới là sự thật.

### Con số đắt nhất trong cả dự án

```
Để yên 1.173 tr không sinh lời → sau 10 năm còn 763 tr theo sức mua hôm nay.
                                  Mất 410 tr, không cần thị trường sập lần nào.
```

Để so sánh: kịch bản vàng **giảm 20%** làm mất 178 tr. Việc **không làm gì trong 10 năm** tốn gấp hơn hai lần thế — và im lặng.

### Ba quy tắc kỹ thuật

- **Fisher chính xác, không phải phép trừ.** Lợi suất thực là `(1+n)/(1+i)−1`, không phải `n−i`. Ở 8,00% và 4,39%, phép trừ cho 3,61% còn công thức đúng cho 3,46% — và sai số 0,15 điểm % **luôn lệch về phía lạc quan**.
- **Hệ thống KHÔNG dự báo lợi suất.** Lạm phát là số liệu công bố (có nguồn); lãi suất tiền gửi là số đo được. Lợi suất kỳ vọng của vàng/cổ phiếu là **giả định của chủ danh mục**, khai trong `config/plan.yaml`. Chưa khai thì chạy **bảng độ nhạy** chứ không chọn hộ một con số rồi trình bày nó như sự thật.
- **Chưa khai báo ≠ bằng 0.** Hiện 97% danh mục (vàng 892 tr + tiết kiệm 246 tr) chưa có giả định lợi suất; phần đó được tách riêng và báo rõ tỷ trọng, không bị gán 0% rồi kéo tụt kết quả một cách bịa đặt.

### Mục tiêu: "vàng ≥70%" là 70% so với cái gì?

Mọi ngưỡng trong hệ thống cho tới nay đều **rời rạc**. Không có mục tiêu thì ngưỡng nào cũng cảm giác tuỳ tiện, và khuyến nghị cảm giác tuỳ tiện thì bị bỏ qua — đúng như đã xảy ra suốt 19 kỳ.

`config/plan.yaml` nhận mục tiêu theo **sức mua hôm nay** ("3 tỷ năm 2041" là câu vô nghĩa nếu không nói 3 tỷ đó mua được gì — sau 15 năm lạm phát 4,39% nó chỉ còn mua được lượng hàng của ~1,57 tỷ). Hệ thống tự quy lên danh nghĩa rồi tính lợi suất cần thiết ở **cả hai thang**.

Quỹ khẩn cấp cũng được sửa cùng logic: `risk_limits.yaml` đang đặt mức tối thiểu **30 tr** — một con số tuyệt đối không neo vào chi tiêu thật. 30 tr là 6 tháng với người tiêu 5 tr/tháng và là 1 tháng với người tiêu 30 tr/tháng. `emergency_fund_months()` quy về **số tháng**, và trả `None` khi chưa khai chi tiêu thay vì đoán.

```
python3 scripts/plan.py           # bảng đầy đủ
python3 scripts/plan.py --json    # để nhúng
```

## Mục tiêu 10 tỷ: cần GÌ để khả thi (15/08/2026)

Chủ danh mục đặt mục tiêu **nâng tổng tài sản lên 10 tỷ**. Hiện có 1.173 tr → cần gấp **8,53 lần**. Nhưng thiếu một biến quyết định tất cả: **thời hạn**. Không chốt thời hạn thì "10 tỷ" là hai bài toán hoàn toàn khác nhau, nên `planning/feasibility.py` không đoán hộ mà giải cho cả dải:

| Thời hạn | Lợi suất cần<br>*nếu không gửi thêm* | Hoặc gửi thêm<br>*chỉ với lãi tiền gửi 8%* | Phân loại |
|---|---|---|---|
| 5 năm | 53,52%/năm | 112,6 tr/tháng | **không phải mục tiêu đầu tư** |
| 10 năm | 23,90%/năm | 40,8 tr/tháng | **không phải mục tiêu đầu tư** |
| 15 năm | 15,36%/năm | 18,1 tr/tháng | đòi hỏi rất cao |
| **20 năm** | 11,31%/năm | **7,7 tr/tháng** | khả thi, cần có cổ phiếu |
| 25 năm | 8,95%/năm | 2,1 tr/tháng | khả thi |
| 30 năm | 7,41%/năm | **không cần gửi thêm** | đạt được bằng **tiền gửi** |

### Kết luận có sức nặng hơn mọi khuyến nghị cổ phiếu

**Gấp đôi thời hạn — từ 10 lên 20 năm — làm mức tiết kiệm cần thiết giảm 5,3 lần** (40,8 → 7,7 tr/tháng). Không cách chọn cổ phiếu nào tạo ra được độ chênh đó. Đòn bẩy mạnh nhất là **thời hạn** và **tỷ lệ tích luỹ**, không phải chọn mã.

Ở mốc 20 năm, riêng 1.173 tr hiện có đã tự lên **5.466 tr** chỉ với lãi tiền gửi — hơn nửa quãng đường, không cần làm gì thêm.

### Danh nghĩa hay sức mua — hai mục tiêu khác nhau

"10 tỷ" gần như luôn được hiểu là con số **nhìn thấy trong tài khoản**. Nhưng sau 20 năm lạm phát 4,39%, 10 tỷ đó chỉ mua được lượng hàng hoá của **~4,2 tỷ hôm nay**. Muốn 10 tỷ **theo sức mua hôm nay** thì con số danh nghĩa phải là **23,6 tỷ**. `config/plan.yaml` có trường `basis: nominal | today` để phân biệt, và hệ thống luôn trả cả hai.

### Mốc phân loại: cái nào là số đo, cái nào là nhận định

Mốc thấp nhất neo vào **lãi suất tiền gửi tốt nhất đang đo được** — số thật. Hai mốc 12% và 20% là **nhận định** về mức bền vững, không phải số đo; `BAND_NOTE` nói rõ điều đó để không ai đọc nhầm thành dự báo.

Hàm `required_years()` trả `None` khi kế hoạch **không bao giờ** tới đích — trả một con số khổng lồ ở đó sẽ bị đọc thành "rồi cũng tới", trong khi sự thật là kế hoạch không hoạt động.

## Gửi báo cáo qua Telegram — và lỗi cắt cụt đã âm thầm chạy bấy lâu (15/08/2026)

```
python3 scripts/send_report.py --preview plan   # xem trước, chạy được mọi nơi
python3 scripts/send_report.py plan             # gửi thật (cần mạng tới api.telegram.org)
```

### Lỗi thật phát hiện khi làm phần này

`send_message()` **cắt cụt ở 4.000 ký tự** rồi ghi *"…(cắt bớt, xem đầy đủ trong bản tin gốc)"*. Bản tin hiện dài **7.438 ký tự** — nghĩa là **mọi bản tin automation đã gửi đều mất gần một nửa**. Tệ hơn, câu "xem đầy đủ trong bản tin gốc" là lời khuyên không thực hiện được: người đọc đang cầm điện thoại, không có bản gốc nào để mở.

Nay `split_for_telegram()` cắt thành **nhiều tin**, luôn ở **ranh giới dòng** — cắt giữa dòng sẽ xé đôi cặp `<b>…</b>` và Telegram từ chối **cả tin** vì HTML không hợp lệ. Mỗi phần được đánh số `(phần k/n)`. Có test khẳng định mọi phần đều dưới giới hạn cứng 4.096 và mọi thẻ đều cân bằng.

### Bảng canh cột phải giữ được cột

Telegram hiển thị tin nhắn bằng font **tỷ lệ**, nên mọi bảng canh cột bằng dấu cách (bảng thời hạn, bảng độ nhạy — phần đáng đọc nhất của báo cáo) sẽ vỡ hàng trên điện thoại. `wrap_aligned_blocks()` tự phát hiện khối bảng và bọc vào `<pre>`; thẻ `<b>` bị gỡ bên trong vì Telegram xử lý định dạng lồng trong khối mã không nhất quán, và một thẻ hỏng làm hỏng cả tin.

Nhãn phân loại trong bảng rút thành ký hiệu ngắn (✅/⚠️/❌) kèm chú giải đầy đủ bên dưới — bảng nhãn dài rộng ~118 ký tự, trong `<pre>` phải cuộn ngang trên điện thoại.

## Khuyến nghị MUA cổ phiếu: từ "không thể" thành "có điều kiện" (15/08/2026)

### Lỗi cấu trúc: hệ thống KHÔNG THỂ khuyến nghị mua

`derive_initial_action` cho equity chỉ ra `BUY_SMALL` khi `margin_of_safety_pct > 20`. Nhưng grep toàn repo cho thấy **không caller production nào truyền trường đó** — nó luôn `None`. Nghĩa là nhánh cổ phiếu, dù đã nối vào bản tin và dashboard, **về mặt cấu trúc không thể nói "mua"**: mọi mã vĩnh viễn dừng ở ĐỨNG NGOÀI. Một hệ thống theo dõi cổ phiếu không bao giờ nói được "mua" thì chỉ là cái đồng hồ báo giá.

### Biên an toàn từ giá mục tiêu — và ba ràng buộc chống lạc quan

`data/valuations.jsonl` chứa 13 giá mục tiêu từ 11 công ty chứng khoán, mỗi dòng kèm nguồn và ngày. `equity/target_prices.py` áp ba ràng buộc:

- **Dùng mục tiêu THẤP NHẤT.** Với VCB dải mục tiêu là 61,9–80,7: biên an toàn tính theo mức thấp nhất là **2,6%**, theo mức cao nhất là **25,3%**. Cùng một mã, hai kết luận trái ngược. Chọn mức thấp nhất là chọn kết luận khó chịu hơn khi không có cơ sở để tin bên nào.
- **Báo cáo độ phân tán.** Các CTCK lệch nhau 30% thì bản thân sự lệch đó là thông tin: không ai thực sự biết. Độ phân tán cao còn **hạ điểm tin cậy** của quyết định.
- **Loại mục tiêu quá cũ** (>180 ngày) và nói rõ đã loại gì; mục tiêu không rõ ngày vẫn dùng nhưng được cảnh báo riêng.

Mỗi lần nêu, hệ thống nhắc: đây là **phán đoán đi mượn** từ CTCK, không phải giá trị đo được — dự án không đo được thành tích dự báo của họ.

### Mua bao nhiêu, giá nào, sai thì thoát ở đâu

`decision/rebalance.py` trả lời "bán bao nhiêu" cho vàng, và chính con số đó biến CHỐT BỚT thành việc làm được. Phía cổ phiếu chưa có gì tương đương — `decision/position_size.py` bổ sung, với **bốn chốt chặn**:

| Chốt chặn | Nguồn |
|---|---|
| Hạn mức 1 mã ≤10%, tổng ≤20% | `config/risk_limits.yaml` |
| **Rào lợi suất**: phải thắng tiền gửi 8,0%/năm KHÔNG rủi ro, **so sau thuế phí** | `deposit_rates.jsonl` + `equity/costs.py` |
| **Lợi nhuận/rủi ro ≥ 2:1**, cắt lỗ dưới hỗ trợ thật | `equity/technical.py` |
| Cỡ lệnh sao cho một lần sai ≤1% tài sản ròng | mức mất tính cả phí và thuế bán |

Kết quả thật trên hai mã đang theo dõi:

```
VCB 60,30 → ĐỨNG NGOÀI
   CHƯA MUA — tổng lợi nhuận 2,9% (tăng giá 2,7% gộp → 2,1% sau thuế phí
   cộng cổ tức 0,71% sau thuế) không vượt được tiền gửi 8,00%/năm KHÔNG rủi
   ro; lợi nhuận/rủi ro 0,8:1 dưới mức tối thiểu 2:1 — doanh nghiệp có thể
   tốt nhưng ĐIỂM VÀO xấu

CTD 62,40 → MUA THĂM DÒ
   Mua tối đa 81 tr · cắt lỗ dưới 53,61 (mất 14,6% đã gồm thuế phí) · mục
   tiêu 93,00 (+49,0% gộp, +48,4% sau thuế phí) · cổ tức 1,52%/năm sau thuế
   · lợi nhuận/rủi ro 3,3:1
```

**VCB bị chặn bởi hai lý do độc lập** dù kết quả kinh doanh rất tốt — đó chính là điều một bộ chặn phải làm được: phân biệt "doanh nghiệp tốt" với "điểm vào tốt".

Và một ràng buộc về nguồn tiền: chủ danh mục có 35 tr tiền mặt với quỹ khẩn cấp tối thiểu 30 tr, nên chỉ 5 tr dùng được. Hệ thống nói thẳng **tiền mua phải đến từ giảm tỷ trọng vàng, không phải từ rút quỹ khẩn cấp** — thay vì đưa một con số không có nguồn tiền.

Rule quản trị doanh nghiệp vẫn **thắng cả biên an toàn**: có test khẳng định cờ đỏ quản trị đè được mọi mức chiết khấu, đúng tình huống PNJ (giá rơi 48,5% nên "rẻ", nhưng nghĩa vụ mua lại chưa định lượng được).

## Vòng đời vị thế: từ khuyến nghị MUA đến vị thế được quản lý (15/08/2026)

Mở được nút MUA làm lộ ra bốn lỗ hổng phía sau nó. Cả bốn đều chưa từng nổ **chỉ vì chưa có quyết định cổ phiếu nào được ghi**.

### 1. Tài sản ròng tự phồng lên 83 triệu

Làm đúng theo khuyến nghị "mua CTD 83 tr" rồi khai vị thế vào config:

```
Tổng trước khi mua               1.172,7 tr
Sau khi thêm vị thế 83 tr CTD    1.255,7 tr   ← TĂNG 83 tr
```

Tiền mua phải lấy từ đâu đó — bán vàng hoặc rút tiền mặt — nhưng `config/portfolio.yaml` chỉ mô tả *đang nắm gì*, không mô tả *đã đổi gì lấy gì*. Mọi con số phía sau (tỷ trọng vàng, tiến độ tới 10 tỷ) đều lệch theo.

`portfolio/transactions.py` + `data/transactions.jsonl`: mỗi giao dịch MUA **bắt buộc khai `funded_from`** — một giao dịch mua không có nguồn tiền là giao dịch chưa xảy ra. Đây cũng là chỗ trả lời câu **giá vốn** đã hỏi mà chưa có: giá vốn không phải con số cần nhớ, nó là kết quả cộng dồn của các giao dịch. Bán làm giảm giá vốn theo **tỷ lệ**, không theo giá bán — dùng giá bán sẽ khiến giá vốn phần còn lại nhảy theo thị trường.

Module **không tự sửa config**, chỉ báo lệch — sửa danh mục phải là hành động có ý thức, cùng lý do mà `--force` của `trend.py append` buộc ghi lại dấu vết.

### 2. Giá tham chiếu cổ phiếu ghi cứng vào VCB

`REF_PRICE_FIELDS["equity"]` là `[("vcb", "close")]`. Một quyết định về **CTD** sẽ được ghi kèm **giá của VCB** — sai lệch âm thầm làm hỏng vĩnh viễn mọi phép chấm điểm sau này. Nay `extract_ref_price` nhận `ticker`, và **thiếu ticker thì trả `None`** thay vì lấy bừa một mã: ghi sai giá tham chiếu còn tệ hơn không ghi.

### 3. Quyết định cổ phiếu không được ghi

`decisions.jsonl` có 13/13 bản ghi là vàng. Nay quyết định cổ phiếu cũng được ghi — và đây mới là loại **có hướng giá**, chấm đúng/sai được, thứ mà HOLD/CHỐT BỚT của vàng không làm được. Sau vài kỳ nữa, thành phần "lịch sử" (15% trọng số) của điểm tin cậy cuối cùng sẽ có nội dung thật.

### 4. Mức cắt lỗ chỉ là một dòng chữ

Hệ thống tính "cắt lỗ dưới 53,61" rồi in ra. Không gì theo dõi mức đó. Một vị thế có mức thoát chỉ tồn tại trong một dòng chữ đã trôi qua thì không phải vị thế được quản lý — đó là vị thế có kèm một lời hứa.

`decision/stop_registry.py` đăng ký mức cắt lỗ thành **cảnh báo thật** trong `data/alerts.json` để `scripts/alerts.py` quét mỗi kỳ. Không đè ngưỡng đặt tay (cờ `auto: true` riêng), và **vị thế đóng thì gỡ cảnh báo** — ngưỡng mồ côi sẽ kêu mãi mà không mang thông tin nào, đúng bệnh alert fatigue đã sửa ở `alert_health.py`.

### Lỗi thứ năm, lộ ra khi thử vị thế thật

Đang nắm 83 tr CTD, hệ thống vẫn bảo **"mua tối đa 89 tr"** — cộng lại 13,7% tài sản ròng, **vượt trần 10% cho một mã** mà không báo gì. Cả hai trần (1 mã và tổng cổ phiếu) đều không trừ phần đang nắm. Sau khi sửa: còn được mua thêm **43 tr**, đúng bằng 125,6 − 83.

## Thuế, phí và cổ tức: hai sai lệch ngược chiều nhau (16/08/2026)

Rào lợi suất dựng ở phần trên so **tiềm năng GỘP** của cổ phiếu với lãi tiền gửi. Phép so đó thiên vị cổ phiếu: gửi tiết kiệm không mất phí giao dịch nào. Nhưng sửa mỗi chiều đó lại thành thiên vị ngược, vì hệ thống chưa từng biết tới cổ tức. Hai sai lệch đi **ngược chiều nhau**, nên bỏ cả hai không tự triệt tiêu:

| Bỏ qua | Hướng lệch |
|---|---|
| Thuế và phí giao dịch | chấm cổ phiếu **CAO** hơn thực tế |
| Cổ tức tiền mặt | chấm cổ phiếu **THẤP** hơn thực tế |

### `equity/costs.py` — quy định hiện hành, không phải ước lượng

```
Thuế TNCN khi BÁN      0,1% trên GIÁ TRỊ BÁN — phải nộp KỂ CẢ KHI LỖ
Phí giao dịch          ~0,15–0,35% mỗi chiều (config: brokerage_fee_pct)
Thuế cổ tức tiền mặt   5%
```

Một vòng mua–bán tốn **0,4–0,8%** trước khi giá nhúc nhích. Ba chỗ đã sửa theo:

- **Rào lợi suất** so số ròng: một mã tiềm năng gộp đúng 8% thì sau thuế phí là **thua** tiền gửi 8%.
- **Mức mất khi cắt lỗ** cộng cả phí hai chiều và thuế bán — khoản thuế vẫn phải nộp khi lệnh đang lỗ.
- **Cỡ lệnh** tính trên mức mất thật, nên nhỏ đi (CTD: 83 → 81 tr).

Có test giữ **bất biến**: thêm chi phí không bao giờ được làm một mã **dễ** mua hơn.

*Không* mô hình thuế cho vàng: cá nhân bán vàng vật chất tại VN không có thuế giao dịch riêng — chi phí thật là chênh lệch mua–bán, `decision/rebalance.py` đã tính đúng. Bịa thêm một khoản thuế vàng là bịa số liệu.

### `equity/dividends.py` — và hai cái bẫy trong cổ tức

**Bẫy 1: "tỷ lệ %" của cổ tức tính trên MỆNH GIÁ 10.000đ, không phải giá thị trường.** VCB công bố "cổ tức tiền mặt **4,5%**" — nghe ngang tiền gửi. Thực tế 450đ/cp; trên giá 60.300đ, tỷ suất thật là **0,75%** trước thuế, **0,71%** sau thuế. Chênh hơn **6 lần**, và luôn theo hướng làm cổ phiếu trông hấp dẫn hơn. Hệ thống luôn quy về tỷ suất trên giá đang mua.

**Bẫy 2: cổ tức bằng CỔ PHIẾU không phải lợi nhuận.** "Cổ tức 49,5% bằng cổ phiếu" của VCB không làm tài sản tăng 49,5%: doanh nghiệp không chi ra đồng nào, giá tham chiếu bị điều chỉnh giảm tương ứng trong ngày giao dịch không hưởng quyền. Cầm nhiều cổ phiếu hơn với giá mỗi cổ phiếu thấp hơn thì giá trị nắm giữ không đổi. Cổ phiếu **thưởng** (CTD 20:1) và cổ tức cổ phiếu của REE (15%) bản chất pha loãng y hệt. Hệ thống tính tỷ suất của chúng bằng **0** và nói rõ vì sao, thay vì im lặng bỏ qua.

`data/dividends.jsonl` — 5 bản ghi có nguồn và ngày cho VCB/CTD/REE. Thiếu dữ liệu trả `None` ("tổng lợi nhuận đang bị tính THIẾU"), **không** trả 0 ("doanh nghiệp không trả cổ tức") — hai câu khác hẳn nhau.

Chỉ cổ tức **tiền mặt sau thuế** được cộng vào tổng lợi nhuận khi so với tiền gửi. Cổ tức bằng cổ phiếu bị đánh thuế khi BÁN chứ không khi nhận; phần đó hệ thống ghi rõ là **chưa mô hình được**, chứ không coi như bằng 0.

### Một giả định được nói thẳng ra

Rào lợi suất so **tổng mức tăng tới giá mục tiêu** với lãi tiền gửi **một năm**. Điều đó chỉ đúng nếu giá mục tiêu được kỳ vọng đạt trong khoảng 12 tháng; xa hơn thì rào đang dễ dãi với cổ phiếu. Mỗi kế hoạch vào lệnh nay in kèm câu cảnh báo đó thay vì để giả định nằm im trong code.

## Dữ liệu cũ phải chặn được khuyến nghị cổ phiếu, đúng như nó đang chặn vàng (29/08/2026)

Cùng một lần chạy, ngày 29/08, hai nửa hệ thống nói hai điều trái ngược về **cùng một file**:

```
scripts/health_check.py  → ❌ EOD CTD: mới nhất 2026-08-10 — đã 19 ngày,
                             gấp >3× ngưỡng 4 ngày. Automation đã ngừng chạy.
scripts/run_morning.py   → CTD 62.40 (EOD 2026-08-10) → MUA THĂM DÒ (80/100)
                             Mua tối đa 81 tr · cắt lỗ dưới 53.61 · mục tiêu 93.00
```

Một nửa gọi dữ liệu là hỏng, nửa kia dựng trên nó một lệnh mua kèm mức cắt lỗ. Trong khi **đúng kỳ đó**, vàng — đọc từ snapshot cũ y hệt — bị Risk Officer chặn thành CHƯA ĐỦ DỮ LIỆU (30/100).

### Cơ chế chặn không thiếu, nhánh cổ phiếu chỉ không đi qua nó

`equity/signals.py::decide_for` ghi cứng `data_freshness_score=100.0` và dựng một `RiskContext` không có `data_stale`. Rule `stale_critical_data` chạy đúng cho vàng, nhưng về cấu trúc **không thể chạm tới cổ phiếu** — không caller nào truyền dữ liệu vào để nó xét.

Đây là lần thứ ba đúng lớp lỗi này: `margin_of_safety_pct` từng không được truyền nên nhánh cổ phiếu không thể khuyến nghị MUA; `data_completeness_pct` từng mặc định 100 nên 13/13 quyết định vàng cùng một điểm 92. Trường có tồn tại, kiểu đúng, mặc định trông vô hại — và không ai truyền. Lý lẽ "chuỗi EOD là nguồn tự động thật" cũng sai ở đúng chỗ đó: **"tự động" nói về cách lấy, không nói gì về việc nó có còn chạy hay không.**

### Chỗ nguy hiểm nhất không phải nhãn hành động, mà là mức cắt lỗ

`53.61` — chính xác tới hai chữ số thập phân — được suy ra từ vùng hỗ trợ của gần ba tuần trước. Sau ngần ấy phiên không quan sát, giá có thể đã ở bất kỳ đâu. Bốn ràng buộc sẵn có của `decision/position_size.py` đều nói về **tương quan** giữa các con số (giá vs hỗ trợ, lợi nhuận vs rào tiền gửi, cỡ lệnh vs hạn mức) nên vẫn cho ra kết quả đẹp khi mọi con số cùng cũ 19 ngày. Nay có ràng buộc thứ năm: `price_stale_note` chặn hẳn kế hoạch vào lệnh, và đứng **đầu** danh sách lý do — các blocker khác bàn về chất lượng của lệnh, cái này bàn về việc có được phép bàn hay không.

### Một ngưỡng, một câu giải thích, hai nơi hiển thị

- `analytics/data_quality.py::EOD_MAX_AGE_DAYS = 4` là **định nghĩa duy nhất** của "EOD quá cũ" — `scripts/health_check.py` import nó thay vì giữ riêng số 4. Bốn ngày lịch chứ không phải một: giá đóng cửa thứ Sáu đọc sáng thứ Hai đã 3 ngày tuổi mà vẫn là phiên gần nhất, ngưỡng phải nuốt được một cuối tuần bình thường. Không có lịch nghỉ lễ, nên Tết dài sẽ làm dữ liệu trông cũ hơn thực tế — sai theo hướng khuyên ít đi, không theo hướng nguy hiểm.
- `equity/signals.py::stale_price_note()` là **câu giải thích duy nhất**. Cần vậy vì có hai nơi hiển thị: bản tin văn bản và `dashboard/ban-tin-dau-tu.html`. Trang HTML — thứ chủ danh mục thật sự đọc — đã in "CHƯA ĐỦ DỮ LIỆU ĐỂ RA QUYẾT ĐỊNH" ở cột Khuyến nghị và "Mua tối đa 81 tr · cắt lỗ dưới 53.61" ở cột ngay bên cạnh, **trên cùng một hàng**.
- Độ mới đo trên `TickerSignal.last_date` — chuỗi đã nạp — chứ không đọc lại đĩa, để nhãn hành động và nhãn chất lượng không thể nói về hai bộ dữ liệu khác nhau.

### Test tự hỏng theo lịch cũng là một lỗi

Ba test cũ chạy trên EOD thật mà không ghim mốc thời gian, nên rule chặn dữ liệu cũ làm chúng đỏ — chúng xanh khi vừa viết và đỏ ba tuần sau mà không dòng code nào thay đổi. Nay `decide_for(..., today=...)` tiêm được, và mọi test **không** nói về độ mới đều lấy "hôm nay" là ngày của nến EOD cuối. Phần độ mới nằm riêng ở `tests/test_equity_freshness.py` (17 test).

Kết quả sau khi sửa: cùng chuỗi EOD đó, đọc **trong ngày** vẫn ra MUA THĂM DÒ 80/100 như trước — hành vi đường chạy bình thường không đổi; đọc **hôm nay** ra CHƯA ĐỦ DỮ LIỆU 30/100, không kèm cỡ lệnh hay mức cắt lỗ nào.

## Bốn lỗi tìm được khi rà soát toàn hệ thống (29/08/2026)

Rà soát bằng cách CHẠY mọi script rồi soi kết quả, chứ không chỉ đọc code. Ba trong bốn lỗi chỉ lộ ra khi chạy thật.

### 1. `fetch_market_snapshot.py` ghi snapshot RỖNG và báo thành công

Chạy script khi mạng bị chặn: thoát mã 0 như bình thường, và ghi vào `data/history.jsonl`:

```json
{"date": "2026-08-29", "ky": "chieu", "vnindex": {}, "gold": {},
 "vcb": {"close": 60300, "change_pct": 1.01}, "ctd": {"close": 62400, "change_pct": 0.48}}
```

Hai chuyện sai cùng lúc, và chúng khuếch đại nhau:

- **Không có giá vàng** — mà vàng là ~76% tài sản. Hậu quả đo được ngay: `value_at()` trả `total_trieu=None` cho kỳ mới nhất, đường tài sản ròng **thủng đúng ở đầu bên phải**; Decision Engine ghi tiếp 4 quyết định dựa trên kỳ rỗng đó.
- **Giá VCB/CTD là nến ngày 10/08 mang nhãn ngày 29/08** — rửa dữ liệu cũ thành dữ liệu mới. `analytics/price_sanity.py` không bắt được, vì nó so với snapshot liền trước, mà chép nguyên giá cũ thì lệch 0% — qua mọi kiểm tra một cách hoàn hảo.

`validate_snapshot()` bắt giá **sai** (âm, bằng 0, bất khả thi) nhưng không bắt giá **thiếu**, vì thiếu không phải một giá trị bất thường. Nay `refuse_reasons()` từ chối ghi khi không có giá vàng hoặc tỷ giá, và `latest_eod_close_pct()` mang theo `as_of` để nến cũ hơn `EOD_MAX_AGE_DAYS` bị loại thay vì đóng dấu ngày hôm nay. **Thà không ghi gì còn hơn ghi một kỳ rỗng rồi để cả hệ thống coi đó là hiện trạng mới nhất.**

### 2. Dashboard nói "mua tối đa 81 tr", bản tin nói 34 tr — cùng một câu hỏi

Với 83 tr CTD đang nắm, trần 10% cho một mã chỉ còn 34,3 tr. Bản tin tính đúng; `reporting/dashboard_builder.py` gọi thẳng `plan_position()` mà **bỏ bốn tham số ràng buộc** (vị thế đang nắm cho cả hai trần, tiền mặt khả dụng, quỹ khẩn cấp) nên in ra 81 tr — gấp 2,4 lần, đẩy vị thế lên 14% tài sản.

Trần chỉ trừ được phần đang nắm khi caller **truyền** phần đang nắm vào; không truyền thì trần im lặng nới ra. Đúng lỗi này đã sửa một lần rồi — commit "Vòng đời vị thế" ghi nguyên văn *"đang nắm 83 tr CTD, hệ thống vẫn bảo mua tối đa 89 tr"* — nhưng chỉ sửa ở `run_morning.py`. Dashboard mới là trang chủ danh mục thật sự đọc.

Nay có `equity/signals.py::plan_for()` là **chỗ dựng duy nhất**, cả hai bề mặt gọi lại. Test `test_chi_MOT_noi_duoc_goi_thang_plan_position` chặn tái phát: thêm bề mặt mới mà gọi thẳng `plan_position()` là test đỏ.

### 3. Bộ đếm kỷ luật giao dịch vừa bỏ sót vừa buộc tội oan

`docs/AUDIT_REPORT.md` mục L7 xếp logic string-matching cũ là "dễ vỡ". Đo lại trên đúng 9 nhãn mà `action_mapper.py` sinh ra thì nó không dễ vỡ — **nó đã vỡ sẵn**:

| Khuyến nghị lúc đó | Lệnh | Logic cũ | Đúng ra |
|---|---|---|---|
| KHÔNG MUA THÊM | SELL | ⚠️ "đi ngược" | thuận — bán không mâu thuẫn với "đừng mua thêm" |
| ĐỨNG NGOÀI | BUY | không gắn cờ | **đi ngược** |
| CHỜ XÁC NHẬN | BUY | không gắn cờ | **đi ngược** |
| GIỮ | SELL | không gắn cờ | **đi ngược** |

Nhánh BUY dò chuỗi `"CHƯA MUA"` — chuỗi này chỉ có trong `PositionPlan.summary()`, **không nằm trong bất kỳ nhãn quyết định nào**. Nên trên cả 9 nhãn, cột BUY luôn `False`: mọi lệnh mua sai đều lọt. Mà mua sai mới là phía mất tiền. Ngược lại "KHÔNG MUA THÊM" chứa chuỗi con "MUA" nên lệnh bán đúng bị đếm là sai.

Nay `decision/discipline.py` đối chiếu bằng **enum**, bảng 9 hành động tường minh, và tách **ba** trạng thái chứ không hai: `CHƯA ĐỦ DỮ LIỆU` không phải một khuyến nghị để mà đi ngược — nó là lời thú nhận hệ thống không biết; trộn vào cột "đi ngược" sẽ làm loãng đúng thứ cần nhìn.

### 4. Mức cắt lỗ ghi xuống đĩa từ dữ liệu cũ (`L8` cũng chưa từng được sửa)

`_sync_stop_alerts()` là bề mặt **thứ ba** của lỗi dữ liệu cũ đã sửa lượt trước — và là bề mặt duy nhất **ghi xuống đĩa**: mức cắt lỗ suy từ vùng hỗ trợ của 19 ngày trước nằm lại trong `data/alerts.json` và được `alerts.py` quét mỗi kỳ như một mức rủi ro đang sống.

Chỗ dễ làm sai là vế thứ hai: bỏ mã ra khỏi `positions` "cho an toàn" sẽ khiến `sync_stops` coi là vị thế đã đóng và **xoá** cảnh báo — dữ liệu cũ làm một vị thế thật mất mức canh cắt lỗ. Nay có tham số `freeze`: **không tính lại, và cũng không gỡ**. Dữ liệu cũ phải làm hệ thống im lặng, không được làm nó tháo bỏ một thứ đang bảo vệ tiền thật.

Cùng lượt, sửa nốt `L8` (chia cho 0 trong `journal.py`, đã ghi trong audit đầu tiên và chưa từng được thêm guard): `journal.py add BUY VCB 58.5 0` rồi `report` → `ZeroDivisionError`, mất toàn bộ báo cáo. Chặn ở **hai** tầng — cửa vào (giá/khối lượng phải > 0) và chỗ đọc (cho những dòng đã lỡ ghi trước đây).

**747 test** (trước đó 697).

## Backtest tự chấm điểm mình cao hơn thực tế (30/08/2026)

`scripts/backtest.py` tính lợi nhuận sau chi phí bằng **công thức riêng**, không dùng `equity/costs.py` như phần còn lại của hệ thống:

```python
(sell - buy) / buy * 100 - 2 * fee_pct
```

Sai hai chỗ, và cả hai đều lệch về phía **lạc quan**:

1. **Bỏ hẳn thuế bán 0,1%** — khoản bắt buộc, phải nộp *kể cả khi lỗ*. Mọi lệnh trong mọi backtest đều được cộng không 0,1 điểm %.
2. **Trừ phí như điểm phần trăm phẳng.** Phí mua tính trên tiền vào, phí bán tính trên tiền **ra**. Trừ `2 × fee_pct` là coi cả hai như tính trên tiền vào — sai càng nhiều khi lãi càng lớn, tức sai đúng ở chỗ quan trọng.

Đo trên chính dữ liệu CTD, phí 0,2%/chiều:

| mua | bán | gộp | công thức cũ | đúng | lệch |
|---|---|---|---|---|---|
| 62,4 | 63,0 | +0,96% | +0,562% | +0,459% | 0,10 |
| 62,4 | 93,0 | +49,04% | +48,638% | +48,391% | 0,25 |
| 100 | 200 | +100% | +99,600% | +99,200% | 0,40 |

0,1–0,4 điểm % nghe nhỏ, nhưng sai số này **luôn cùng một chiều** và cộng dồn theo số lệnh. Backtest tồn tại để trả lời "quy tắc này có đáng theo không", mà thước đo là tiền gửi ~8%/năm KHÔNG rủi ro — một sai số luôn nghiêng về phía làm quy tắc trông tốt hơn thực tế là loại sai số dẫn thẳng tới quyết định sai.

### Hai thay đổi kèm theo

- **Mặc định không còn là "miễn phí".** `--fee` mặc định lấy phí thật trong `config/decision_rules.yaml` thay vì 0. Giao dịch miễn phí chưa bao giờ là sự thật, và một backtest mặc định bỏ chi phí là backtest mặc định trả lời sai câu hỏi nó sinh ra để trả lời. Thuế bán thì bị trừ **luôn**, kể cả khi khai `--fee 0`.
- **Rào lợi suất, đúng nguyên tắc đã áp cho khuyến nghị mua.** Backtest nay so kết quả với lãi tiền gửi trên **đúng số ngày vốn thực sự nằm trong thị trường** — không quy ra %/năm, vì 3 lệnh trong 43 phiên quy ra năm là phóng đại một mẫu quá nhỏ thành tuyên bố về tương lai:

```
Số lệnh: 3 | Thắng: 0/3 (0%) | Tổng lợi nhuận cộng dồn: -5.8%
Vốn nằm trong thị trường 6 ngày. Cùng 6 ngày đó, gửi tiết kiệm ở mức tốt nhất
đo được (8.00%/năm) cho +0.13% KHÔNG rủi ro.
→ Quy tắc THUA tiền gửi 5.92 điểm %, trong khi vẫn phải chịu rủi ro giá.
⚠️ Chỉ 3 lệnh — quá ít để nói quy tắc tốt hay xấu.
```

**751 test** (trước đó 747). Test cũ từng **mã hoá chính cái sai**: nó assert chênh lệch đúng bằng `2 × 0,15 = 0,3` — con số chỉ đúng với công thức phẳng.

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
