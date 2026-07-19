# Implementation Plan — Finance-duy (nâng cấp lên hệ thống có Decision Engine + Risk Officer)

Tham chiếu: `docs/AUDIT_REPORT.md` (hiện trạng), đặc tả 21 mục do chủ dự án cung cấp 2026-07-19.
Nguyên tắc xuyên suốt: **mỗi phase = 1 commit riêng, chạy test trước khi commit, không xóa chức năng đang chạy, không để AI tự bịa số liệu.**

---

## Phase 1 — Audit & tài liệu ✅ (đang thực hiện, phase này)

- [x] Đọc `docs/HANDOVER.md`, kiểm tra branch/status/log
- [x] Đọc + chạy thử an toàn 8 script hiện có
- [x] Kiểm tra bảo mật (grep secrets — sạch), kiểm tra mạng (xác nhận vẫn bị chặn tới hsx.vn/entrade.com.vn, PyPI thì thông)
- [x] `docs/AUDIT_REPORT.md`, `docs/IMPLEMENTATION_PLAN.md`
- [ ] Dọn `__pycache__` khỏi git + thêm `.gitignore` (việc nhỏ, làm cuối Phase 1)

**Không sửa logic nghiệp vụ trong phase này.**

---

## Phase 2 — Data Contract & Source Health

**Mục tiêu:** mọi số liệu tài chính đi qua repo đều có nguồn, độ mới, độ tin cậy — thay vì số trần trụi.

### File mới
- `datacontract/schema.py` — dataclass/TypedDict `DataPoint`: `name, value, unit, source, source_url, as_of, fetched_at, freshness_seconds, confidence, fallback_used, metadata`
- `datacontract/validators.py` — hàm kiểm tra: `is_stale(dp, max_age_seconds)`, `is_missing`, `is_abnormal(dp)` (âm/=0 bất thường tùy loại tài sản), `compare_sources(dp_a, dp_b, tolerance)` → trả `HEALTHY/DEGRADED/STALE/FAILED/CONFLICTING`
- `datacontract/sources.py` — registry nguồn theo `config/source_priority.yaml`, có `get_with_fallback(fetchers: list[Callable]) -> DataPoint`

### File sửa
- `scripts/trend.py` — `cmd_append` validate từng field quan trọng qua `datacontract.validators` trước khi ghi; snapshot mở rộng thêm field `_meta: {source, confidence}` song song field giá trị cũ (không phá schema cũ — field mới optional)
- Toàn bộ script `scripts/*.py` — thay `print()` bằng `logging` (module `common/logsetup.py` mới, mỗi lần chạy có `run_id` = uuid4, log ra `logs/<run_id>.jsonl`)

### Ràng buộc quan trọng (vì môi trường chặn API tài chính)
Vì `api.hsx.vn`/`services.entrade.com.vn` bị chặn network policy trong môi trường hiện tại (đã xác nhận lại ở Phase 1), **nguồn "chính" thực tế cho VN-Index/VCB/CTD vẫn phải là kết quả WebSearch của AI** cho tới khi network được mở. Data contract phải xử lý được điều này một cách trung thực: gán `source="web_search_summary"`, `confidence` thấp hơn hẳn so với 1 API HEALTHY, và field `fallback_used=True`. Đây **không phải giả** — là mô tả đúng thực tế nguồn, để Risk Officer (Phase 7) biết mà hạ confidence tổng.

### Test (`tests/test_datacontract.py`)
- stale detection đúng ngưỡng thời gian
- missing → không được thay bằng 0
- 2 nguồn lệch > tolerance → CONFLICTING
- 1 nguồn fail → dùng fallback, đánh dấu `fallback_used=True`

---

## Phase 3 — Cấu hình danh mục

### File mới
- `config/portfolio.yaml` — đúng schema chủ dự án cung cấp (gold_ring 6.5 tael, savings 246tr, cash 35tr, stocks: [], watchlist: [VCB, CTD])
- `config/risk_limits.yaml` — gold_warning 0.60, gold_critical 0.70, single_stock_max 0.10, total_stock_max 0.20, minimum_cash_buffer 30tr
- `config/source_priority.yaml` — thứ tự nguồn cho từng loại dữ liệu (vàng, chứng khoán, lãi suất, tin tức), đánh dấu rõ nguồn nào hiện KHÔNG khả dụng (HOSE API — bị chặn) để hệ thống tự biết bỏ qua thay vì thử rồi timeout mỗi lần
- `config/decision_rules.yaml` — khung rule cho Phase 7 (đặt trước, dùng sau)
- `portfolio/loader.py` — đọc 4 file YAML trên, validate bằng `datacontract`

### File sửa
- `scripts/networth.py` — bỏ hard-code `gold_luong/bank_vnd_trieu/cash_vnd_trieu` khỏi `data/assets.json`, đọc từ `config/portfolio.yaml`; đọc ngưỡng cảnh báo từ `config/risk_limits.yaml` thay vì số `60` viết chết trong code
- **Giữ nguyên `data/assets.json` là snapshot lịch sử** (không xóa) nhưng vai trò đổi thành "bản ghi tại 1 thời điểm", nguồn sự thật (source of truth) là `config/portfolio.yaml`

### Test
- Đọc YAML → tính tổng tài sản đúng như `networth.py` hiện tại đã tính (1.109,8 tr) — so khớp để đảm bảo không phá kết quả cũ
- Cảnh báo gold_warning/critical kích hoạt đúng ngưỡng 60%/70%

---

## Phase 4 — Module Vàng

### File mới
- `gold/conversion.py`:
  ```python
  GRAMS_PER_TROY_OUNCE = 31.1034768
  GRAMS_PER_VIETNAMESE_TAEL = 37.5
  def theoretical_vnd_per_tael(xau_usd: float, usd_vnd: float) -> float: ...
  ```
  (sửa đúng sai số đã phát hiện ở Audit — `luong_per_oz` hiện tại 1.205656 → phải là 1.2056530)
- `gold/xuan_trieu_model.py` — refactor `scripts/gold_price.py` vào đây dưới dạng module có thể import + giữ CLI wrapper mỏng ở `scripts/gold_price.py` để không phá lệnh gọi hiện tại
- `data/normalized/xuan_trieu_gold_history.csv` — **file chưa tồn tại, tạo mới**, mỗi lần hiệu chuẩn (khi có ảnh mới) append 1 dòng: `date, xau_usd, usd_vnd, world_per_tael, shop_buy, shop_sell, premium, mae_vs_prediction`
- `gold/indicators.py` — MA20/50/200, RSI14, MACD, Bollinger, ATR, volatility 20 ngày cho **giá vàng** (tách khỏi `scripts/indicators.py` vốn dành cho cổ phiếu, dùng chung hàm lõi qua `analytics/ta_core.py` để không trùng code)
- `analytics/ta_core.py` — gộp các hàm `sma/ema_series/rsi/macd/bollinger` hiện đang nằm trong `scripts/indicators.py`, để cả module vàng và module cổ phiếu dùng chung 1 nguồn implementation (tránh 2 bản RSI khác nhau)

### File sửa
- `scripts/indicators.py` — refactor để gọi `analytics/ta_core.py` thay vì định nghĩa lại (giữ nguyên CLI/behavior, không đổi output)
- `scripts/networth.py` — dùng `gold/xuan_trieu_model.py` thay vì import chay `gold_price` qua sys.path hack

### Test (`tests/test_gold.py`)
- `theoretical_vnd_per_tael(4017, 26460)` ≈ 128.15 tr (khớp số đã tính tay ở Phase trước, sai số < 0.01tr sau khi sửa hằng số)
- Hệ số hiệu chuẩn tại đúng điểm calibration cho ra khớp 100% giá tiệm thật (127.5tr mua / 130.0tr bán)
- Với 1 mẫu MAE không tính được → trả `confidence=LOW, sample_size=1`, không báo số MAE giả

**Đầu ra 2 phần tách bạch theo đúng yêu cầu:**
```python
{"trend": "TÍCH CỰC" | "TIÊU CỰC" | "TRUNG TÍNH",  # từ chỉ báo kỹ thuật thuần túy
 "portfolio_action": None}  # để trống — Decision Engine (Phase 7) mới điền, KHÔNG tính ở đây
```
Lý do tách: đúng ví dụ chủ dự án đưa ("Xu hướng vàng: TÍCH CỰC. Hành động: KHÔNG MUA THÊM. Lý do: tỷ trọng vượt giới hạn") — xu hướng là thuộc tính của THỊ TRƯỜNG, hành động là thuộc tính của DANH MỤC + RISK LIMIT, hai thứ không được trộn trong cùng 1 hàm.

---

## Phase 5 — Module Tiền gửi

### File mới
- `deposits/schema.py` — record: bank, term_months, rate_online, rate_counter, min_deposit, conditions, interest_payment, early_withdrawal_penalty, updated_at, source
- `deposits/ranking.py` — lọc bỏ lãi suất VIP/nhiều tỷ/bảo hiểm/CCTG/ưu đãi mập mờ (theo danh sách loại trừ tường minh, không phải AI tự đoán); xếp hạng theo (lãi suất, thanh khoản, điểm phù hợp)
- `deposits/strategy.py` — chia kỳ hạn (6T/12T/13-18T + quỹ dự phòng + quỹ chờ mua CP), tính ngày đáo hạn, lãi dự kiến, thiệt hại rút trước hạn
- `data/normalized/deposit_rates.jsonl` — lịch sử lãi suất theo ngày (kế thừa cấu trúc `deposit_top` đã có trong `history.jsonl`, tách riêng thành file chuẩn hóa)

### File sửa
- `scripts/trend.py` — phần lãi suất trong `report()` gọi `deposits/ranking.py` thay vì so sánh dict thô như hiện tại

### Test
- Danh sách loại trừ hoạt động đúng (dữ liệu mẫu có 1 dòng "13 tháng 9.2% yêu cầu 500 tỷ" phải bị loại)
- Tính lãi 246tr @ 7.4%/12T = 18.2tr (khớp số đã tính tay trong bản tin trước)

---

## Phase 6 — Module Chứng khoán Việt Nam

**Đây là phase rủi ro cao nhất về dữ liệu** — ghi nhận thẳng trong plan: `api.hsx.vn` bị chặn network. Thiết kế phải coi WebSearch-summary là **nguồn hợp lệ nhưng confidence thấp**, không giả vờ có API.

### File mới
- `equity/market.py` — VN-Index, giá trị GD, thanh khoản, độ rộng, nhóm ngành, khối ngoại/tự doanh/ETF — nhận input dạng `DataPoint` (Phase 2), không tự fetch cứng 1 nguồn
- `equity/fundamentals.py` — khung 12 chỉ tiêu cơ bản (doanh thu, LN, biên LN, dòng tiền KD, nợ vay, ROE, ROA, phải thu, tồn kho...) cho VCB/CTD — nhập tay từ BCTC (đánh dấu rõ `source="BCTC_manual_entry"`) vì chưa có API BCTC
- `equity/valuation.py` — P/E, P/B, so lịch sử/ngành, biên an toàn, 3 kịch bản (thấp/cơ sở/cao) — công thức thuần, input là DataPoint
- `equity/technical.py` — dùng lại `analytics/ta_core.py` (Phase 4) + thêm Relative Volume, Volume z-score, hỗ trợ/kháng cự (đã có logic thô trong `data/alerts.json`, nâng cấp thành phát hiện tự động từ pivot high/low), breakout, trend state
- `equity/governance.py` — enum trạng thái pháp lý chuẩn: `NONE, RUMOR, UNDER_VERIFICATION, SUMMONED_FOR_QUESTIONING, INVESTIGATION_OPENED, INDICTED, CONVICTED` — **cấm cứng** việc gán `INDICTED` (bị khởi tố/bắt) nếu nguồn tin chỉ nói "đang xác minh"/"mời làm việc" (đúng yêu cầu chủ dự án, implement bằng whitelist từ khóa nguồn → enum, không để AI tự diễn giải)
- `analytics/anomaly_detector.py` — refactor `scripts/tick.py` vào đây, đổi tên khỏi ý nghĩa "insider trading", output đúng format:
  ```json
  {"ticker": "CTD", "alert_level": 3, "anomaly_type": "unusual_volume",
   "evidence": [...], "conclusion": "Cần theo dõi, chưa đủ căn cứ kết luận giao dịch nội bộ"}
  ```
  Giữ nguyên heuristic lệnh tròn số đã có (đã test, logic đúng), chỉ đổi format output + cấm từ "nội gián"/"insider" trong toàn bộ output text.

### File sửa
- `scripts/tick.py` — giữ làm CLI wrapper mỏng gọi `analytics/anomaly_detector.py`
- `scripts/indicators.py` — thêm Relative Volume, Volume z-score (hiện chỉ có `vol_vs_bq20`)
- `data/eod/*.csv` — **cần bơm thêm lịch sử** (hiện 1 dòng/mã). Ghi rõ trong plan: đây là **blocker dữ liệu**, không phải blocker code — cần chủ dự án cung cấp CSV lịch sử (từ app chứng khoán) hoặc mở network policy.

### Test
- Governance enum: input "đang bị mời làm việc để xác minh" → PHẢI ra `UNDER_VERIFICATION`, test fail nếu ra `INDICTED`
- Anomaly detector: dữ liệu mô phỏng có lệnh tròn số lặp 5 lần → `alert_level` tăng tương ứng, `conclusion` luôn chứa "chưa đủ căn cứ"

---

## Phase 7 — Risk Officer & Decision Engine

**Đây là phase quan trọng nhất** — giải quyết đúng lỗ hổng lớn nhất tìm thấy ở Audit (L1, L2): hiện tại 100% quyết định là văn xuôi AI, 0% là code.

### File mới
- `decision/risk_officer.py`:
  ```python
  VETO_RULES = ["stale_critical_data", "conflicting_critical_sources",
                "gold_concentration_critical", "governance_red_flag",
                "insufficient_liquidity", "missing_financial_data",
                "abnormal_price_data"]
  def review(proposed_action, portfolio_state, data_quality) -> RiskReview: ...
  ```
  Rule cụ thể đầu tiên cần code đúng ví dụ chủ dự án cho: vàng ≥70% → chặn mọi `BUY` liên quan vàng, ép `final_action = DO_NOT_BUY_MORE` bất kể input là gì.
- `decision/confidence_score.py` — tính điểm 0-100 từ: độ đầy đủ dữ liệu, độ mới, đồng thuận tín hiệu (kỹ thuật/cơ bản/dòng tiền có đồng chiều không), độ chính xác lịch sử (từ `evaluation/decision_review.py`, Phase 9), mức xung đột nguồn, mức rủi ro danh mục. Thuật toán tường minh, không phải "AI cho điểm".
- `decision/policy_engine.py` — kết hợp toàn bộ input (Phase 4/5/6) → 1 trong 9 action chuẩn (`HOLD, TAKE_PARTIAL_PROFIT, DO_NOT_BUY_MORE, DEPOSIT, BUY_SMALL, WATCH, WAIT_FOR_CONFIRMATION, STAND_ASIDE, NO_DECISION`) → gọi `risk_officer.review()` để có veto cuối cùng
- `decision/action_mapper.py` — map 9 action tiếng Anh trên sang 7 nhãn tiếng Việt chủ dự án yêu cầu (GIỮ, CHỐT BỚT, KHÔNG MUA THÊM, GỬI TIẾT KIỆM, MUA THĂM DÒ, ĐỨNG NGOÀI, CHỜ XÁC NHẬN) — 1-1 mapping tường minh, không suy diễn

### Rule đầu tiên implement (rút từ chính case thật của chủ dự án)
```yaml
# config/decision_rules.yaml (điền dần qua các phase, nhưng rule vàng có ngay từ Phase 7)
gold:
  if_allocation_gte: 0.70
    then: DO_NOT_BUY_MORE
    veto: gold_concentration_critical
  if_allocation_gte: 0.60
    then: prefer TAKE_PARTIAL_PROFIT over BUY_SMALL
```

### Test (`tests/test_decision.py`, `tests/test_risk_officer.py`)
- Input tài sản thật của chủ dự án (vàng 74.7%) → `risk_officer.review(BUY_SMALL_GOLD, ...)` PHẢI trả `approved=False, final_action="DO_NOT_BUY_MORE"`
- Dữ liệu giá cũ >X giờ → mọi action tự động thành `NO_DECISION`
- 2 nguồn giá lệch nhau > tolerance → `WAIT_FOR_CONFIRMATION`
- Governance `INDICTED` cho 1 mã trong watchlist → chặn mọi đề xuất mua mã đó

---

## Phase 8 — Bản tin sáng/chiều + Diff report + Dashboard

### File mới
- `scripts/run_morning.py` — orchestrator: load config → fetch/nhập data (đánh dấu confidence theo Phase 2) → gọi Phase 4/5/6 modules → gọi `decision/policy_engine.py` → in báo cáo theo đúng cấu trúc chủ dự án yêu cầu (Tổng quan hành động / Tài sản ròng / Vàng / Tiền gửi / Chứng khoán / Kết luận)
- `scripts/run_evening.py` — tương tự + gọi `reporting/diff_report.py`
- `reporting/diff_report.py` — so bản chiều với bản sáng cùng ngày (đọc 2 snapshot gần nhất trong lịch sử mở rộng từ `trend.py`), bắt buộc ghi lý do nếu quyết định đổi
- `reporting/render_dashboard.py` — **thay thế cách sửa tay HTML hiện tại**: đọc toàn bộ output từ `data/` + `decision/` + `datacontract`, render `dashboard/ban-tin-dau-tu.html` bằng template (giữ nguyên thiết kế/CSS đã có, chỉ thay phần nội dung động từ chỗ "AI gõ tay" sang "script sinh ra") — hiển thị rõ badge DỮ LIỆU ĐÃ CŨ / NGUỒN XUNG ĐỘT / ĐANG DÙNG FALLBACK theo trạng thái `DataPoint`

### File sửa
- `scripts/trend.py` — `report()` output được `run_morning.py`/`run_evening.py` gọi làm 1 phần, không đổi hành vi CLI gốc (vẫn chạy độc lập được như cũ)

**Giữ nguyên khả năng chạy độc lập của toàn bộ script cũ** — `run_morning.py` là lớp orchestrator MỚI bên trên, không xóa lệnh gọi trực tiếp `python3 scripts/trend.py report` v.v.

---

## Phase 9 — Journal nâng cấp + Backtest + Đánh giá quyết định

### File sửa
- `scripts/journal.py` — thêm cấu trúc `run_id` đầy đủ theo schema chủ dự án; sửa string-matching cứng bằng enum action (Phase 7); thêm guard chia 0 (Audit L8)

### File mới
- `evaluation/decision_review.py` — với mỗi quyết định đã lưu trong journal, tính kết quả thực tế sau 1 ngày/5 phiên/20 phiên, so với action đã đề xuất → đúng/sai
- `evaluation/backtest.py` — nâng cấp `scripts/backtest.py`: thêm đánh giá cho GIỮ/CHỐT BỚT/ĐỨNG NGOÀI/MUA THĂM DÒ/CHỜ XÁC NHẬN (không chỉ mua/bán nhị phân như hiện tại), thêm drawdown, win rate, precision cảnh báo, chi phí giao dịch, spread vàng, slippage
- **Giữ nguyên `scripts/backtest.py` hiện tại làm CLI wrapper** gọi `evaluation/backtest.py`

### Nguyên tắc chống look-ahead (đã đúng 1 phần, cần giữ khi mở rộng)
`backtest_ma` hiện tại tính MA từ `closes[i-n:i]` (loại trừ ngày i) — đúng nguyên tắc. Khi thêm chiến lược mới cho các action khác, giữ đúng ràng buộc: dữ liệu ngày T chỉ dùng thông tin có tới hết ngày T-1 khi ra quyết định cho ngày T.

---

## Phase 10 — Automation, Health Check, Test, Bảo mật hoàn thiện

### File mới
- `scripts/health_check.py` — kiểm tra: job cuối cùng chạy khi nào, `data/history.jsonl` có mới không, dashboard có được sinh ra không (Phase 8 xong mới check được), nguồn dữ liệu nào đang FAILED
- `.env.example` — để trống (chưa có secret nào cần), nhưng dựng sẵn khung cho tương lai (VD nếu thêm API key FireAnt/SSI)
- `.gitignore` — `__pycache__/`, `.env`, `*.pyc`, `logs/*.jsonl` (log chi tiết không cần commit, chỉ commit summary)
- `tests/` — đầy đủ theo checklist Phase 16 của đặc tả (quy đổi vàng, tài sản, tỷ trọng, premium, spread, lãi tiết kiệm, RSI/MACD/Bollinger, source fallback, stale, conflicting, risk veto, confidence score, decision engine, morning/evening report, diff report)

### File sửa
- Toàn bộ `scripts/*.py` còn dùng `print()` thuần → hoàn thiện chuyển logging (bắt đầu từ Phase 2, hoàn thiện ở đây)
- README.md — cập nhật hướng dẫn vận hành mới (lệnh `python scripts/run_morning.py`, cách sửa portfolio.yaml, risk_limits.yaml...)
- `CHANGELOG.md` (file mới) — ghi lại từng phase

---

## Rủi ro/blocker cần chủ dự án quyết định trước khi làm Phase 6

1. **Mạng bị chặn tới HOSE/entrade** — cần 1 trong 3: (a) mở network policy, (b) API key FireAnt/SSI, (c) chấp nhận nguồn WebSearch-summary với confidence thấp vĩnh viễn cho dữ liệu VN-Index/VCB/CTD.
2. **Dữ liệu BCTC VCB/CTD** để tính ROE/ROA/nợ vay — cần nhập tay từ báo cáo tài chính công bố (không có API miễn phí đáng tin), sẽ đánh dấu `source="BCTC_manual_entry"`, KHÔNG bịa số.
3. **`data/eod/*.csv` cần lịch sử dài hơn** để `indicators.py`/`backtest.py` có ý nghĩa (hiện 1 phiên/mã, cần ≥20 tối thiểu, ≥200 để có MA200 đầy đủ).

---

## Trình tự commit dự kiến (không đổi thứ tự trừ khi phát sinh phụ thuộc mới)

```
Phase 1: docs(audit): audit report + implementation plan + dọn .gitignore
Phase 2: feat(data): data contract, validators, source health, structured logging
Phase 3: feat(config): portfolio/risk_limits/source_priority YAML + loader
Phase 4: feat(gold): conversion chuẩn, xuan_trieu model, gold indicators, history CSV
Phase 5: feat(deposits): schema, ranking có loại trừ, chiến lược chia kỳ hạn
Phase 6: feat(equity): market/fundamentals/valuation/technical/governance/anomaly_detector
Phase 7: feat(decision): risk_officer, confidence_score, policy_engine, action_mapper
Phase 8: feat(reporting): run_morning, run_evening, diff_report, render_dashboard
Phase 9: feat(journal): nâng cấp journal + evaluation/backtest + decision_review
Phase 10: chore(ops): health_check, .env.example, .gitignore hoàn thiện, tests đầy đủ
```

Mỗi commit: chạy `pytest` (từ Phase 2 trở đi khi đã có test) trước khi commit; không có phase nào xóa file/chức năng đang hoạt động của phase trước.
