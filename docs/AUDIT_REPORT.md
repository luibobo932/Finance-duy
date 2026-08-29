# Audit Report — Finance-duy

**Ngày audit:** 2026-07-19
**Branch:** `claude/investment-news-aggregator-w81l70` (sạch, không có thay đổi chưa commit)
**Người audit:** Claude (kiến trúc sư phần mềm tài chính, tiếp quản dự án)
**Phạm vi:** Toàn bộ repo tại commit `f6bc2b1`

---

## 1. Tóm tắt điều hành

Dự án hiện tại là một **hệ thống tạo bản tin đầu tư vận hành bằng AI-in-the-loop**: mỗi lần chạy, một phiên Claude Code đọc tài liệu hướng dẫn, tự tìm kiếm số liệu qua WebSearch, gõ tay một JSON snapshot, chạy vài script Python nhỏ để tính toán, rồi **tự viết văn xuôi kết luận** (GIỮ/CHỐT BỚT/...) dựa trên phán đoán ngữ cảnh — không có một dòng code nào quyết định hành động cuối cùng.

Đây là điểm khác biệt cốt lõi so với đặc tả mới: đặc tả mới yêu cầu **Decision Engine + Risk Officer bằng code**, dữ liệu có **data contract** với nguồn/độ tin cậy/độ mới, và **không có con số nào được AI bịa ra**. Hệ thống hiện tại chưa có lớp này — mọi "trí tuệ" nằm trong prompt và trong đầu người vận hành phiên, không nằm trong repo.

**Kết luận:** Nền tảng tính toán thuần túy (vàng, tài sản ròng, chỉ báo kỹ thuật, backtest) viết đúng, đã test bằng tay, không có lỗi crash. Nhưng **toàn bộ tầng dữ liệu là thủ công/không có nguồn máy có thể kiểm chứng**, và **toàn bộ tầng quyết định là văn xuôi của AI**, không phải rule engine. Đây là ưu tiên số 1 cần vá theo đặc tả mới.

---

## 2. Chức năng đang có (hoạt động, đã test)

| Script | Chức năng | Đã test lại hôm nay | Kết quả |
|---|---|---|---|
| `scripts/trend.py` | Lưu snapshot lịch sử (chặn ghi trùng ngày+kỳ); so sánh kỳ hiện tại vs kỳ trước; phát hiện KLGD đột biến ≥1.5× BQ20; chuỗi mua/bán ròng khối ngoại; lãi/lỗ danh mục | ✅ `append`, `report` | Chạy đúng, không crash |
| `scripts/networth.py` | Tính tài sản ròng (vàng+tiết kiệm+mặt+CP), tỷ trọng, cảnh báo tập trung ≥60% | ✅ | Ra đúng: vàng 74.7%, tổng 1.109,8 tr |
| `scripts/gold_price.py` | Quy đổi XAU/USD + tỷ giá → giá vàng nhẫn tiệm, hiệu chuẩn 1 điểm từ ảnh bảng giá | ✅ (test cả XAU=4017 và XAU giả định 4100) | Công thức tuyến tính đúng, phản ứng đúng theo giá thế giới |
| `scripts/indicators.py` | RSI(14) Wilder, MACD(12,26,9), SMA20/50/200, Bollinger(20,2) | ✅ (test với chuỗi tổng hợp 60 phiên ở phiên trước; hôm nay test CTD 1 phiên) | Công thức đúng; nhưng **dữ liệu thật hiện chỉ có 1 phiên/mã** nên luôn trả `None` |
| `scripts/alerts.py` | So giá hiện tại với ngưỡng trong `data/alerts.json`, báo kích hoạt | ✅ `--list` | Đúng |
| `scripts/journal.py` | Ghi lệnh mua/bán, khớp FIFO, tính lãi/lỗ đã chốt, win-rate, đối chiếu khuyến nghị | ✅ (rỗng, đã test có dữ liệu ở phiên trước) | Đúng logic FIFO |
| `scripts/watchlist.py` | Theo dõi % thay đổi giá 11 mã Buffett-list so ngày lập | ✅ `report` | Đúng |
| `scripts/backtest.py` | Backtest chiến lược MA-cross đơn giản trên EOD | ✅ (báo thiếu dữ liệu đúng như kỳ vọng) | Logic không look-ahead nghiêm trọng (dùng closes[i-n:i] loại trừ ngày hiện tại) |
| `scripts/tick.py` | Phát hiện lệnh lớn tròn số lặp ≥3 lần (heuristic gom hàng) | Không chạy lại (cần dữ liệu ngoài) | Trước đó test với dữ liệu mô phỏng — logic đúng |

Tất cả script: Python 3 chuẩn, không dependency ngoài, không crash khi thiếu dữ liệu (trả `None`/thông báo rõ thay vì lỗi).

---

## 3. Chức năng đang lỗi / thiếu (theo đặc tả mới)

| # | Vấn đề | Mức độ | Chi tiết |
|---|---|---|---|
| L1 | **Không có Decision Engine bằng code** | 🔴 Nghiêm trọng | Mọi kết luận GIỮ/CHỐT BỚT/MUA THĂM DÒ hiện do AI viết tay trong bản tin, không qua rule engine, không có confidence score tính toán. |
| L2 | **Không có Risk Officer / veto rule** | 🔴 Nghiêm trọng | Không gì ngăn AI đề xuất "MUA THÊM VÀNG" ngay cả khi vàng đã 75% — hiện chỉ là cảnh báo văn bản trong `networth.py`, không phải veto chặn hành động. |
| L3 | **Không có data contract / nguồn dữ liệu máy** | 🔴 Nghiêm trọng | `history.jsonl`, `assets.json`, `eod/*.csv` đều được AI **gõ tay** từ kết quả WebSearch mỗi phiên — không có API fetch, không có `source_url`, không có `as_of`/`fetched_at`/`confidence` per số liệu. Không thể phân biệt HEALTHY/STALE/CONFLICTING theo yêu cầu vì không có trường nào lưu trạng thái nguồn. |
| L4 | **Dashboard là HTML tĩnh sửa tay** | 🟠 Cao | `dashboard/ban-tin-dau-tu.html` (398 dòng) không được sinh ra từ script/template nào — mỗi kỳ AI dùng Edit tool sửa trực tiếp các con số trong HTML. Rủi ro: số liệu trong dashboard có thể lệch với `data/*.json` vì không cùng một nguồn build. |
| L5 | **`data/eod/*.csv` chỉ có 1 phiên/mã** | 🟠 Cao | `indicators.py` và `backtest.py` cần ≥15–200 phiên; hiện tại luôn trả `None`/"không đủ dữ liệu". Chỉ báo kỹ thuật trong mọi bản tin trước giờ **chưa từng thực sự chạy được** — số RSI/MACD nếu xuất hiện trong bản tin trước đây là do AI tự ước lượng bằng lời, không phải từ `indicators.py`. |
| L6 | **Mạng bị chặn tới nguồn dữ liệu tài chính** | 🟠 Cao | Xác nhận lại hôm nay: `api.hsx.vn` và `services.entrade.com.vn` đều trả `CONNECT tunnel failed, response 403` qua proxy môi trường. PyPI (`pip install`) thì **hoạt động bình thường** → môi trường chặn theo domain, không chặn toàn bộ mạng. |
| L7 | ✅ **ĐÃ SỬA 29/08/2026** — `decision/discipline.py`, đối chiếu bằng enum. Đo lại thì L7 không chỉ "dễ vỡ": nhánh BUY không bắt được lệnh mua sai nào trên cả 9 nhãn, và lệnh BÁN sau "KHÔNG MUA THÊM" bị buộc tội oan. | 🟡 Trung bình | `"CHƯA MUA" in r["rec"].upper()` — dễ vỡ nếu đổi cách viết action. Cần map sang enum hành động chuẩn (HOLD/BUY_SMALL/...). |
| L8 | ✅ **ĐÃ SỬA 29/08/2026** — chặn ở cửa vào (`cmd_add`) và guard ở chỗ đọc (`cmd_report`). Tái hiện được bằng `journal.py add BUY VCB 58.5 0` rồi `report`. | 🟡 Trung bình | `journal.py` dòng tính `(price - cost) / cost` — nếu `avg_cost == 0` sẽ crash. Chưa xảy ra trong thực tế nhưng cần guard. |
| L9 | **Lịch chạy (cron) nằm ngoài repo hoàn toàn** | 🟡 Trung bình | 2 Claude Code Routines được tạo qua MCP tool, không phải code trong repo. Không có `scripts/run_morning.py`/`run_evening.py` độc lập — prompt đầy đủ chỉ tồn tại trong lịch sử hội thoại, đã tóm tắt lại trong `HANDOVER.md` nhưng không phải code chạy được trực tiếp. |
| L10 | **`__pycache__` bị commit vào git** | 🟢 Thấp | `scripts/__pycache__/gold_price.cpython-311.pyc` nằm trong `git ls-files`. Không có `.gitignore`. |
| L11 | **Không có test tự động** | 🟠 Cao | 0 file test, chưa cài `pytest` trước audit này (đã cài được, PyPI truy cập được). Mọi "kiểm chứng" trước giờ là chạy tay 1 lần trong hội thoại rồi không giữ lại. |
| L12 | **Không có structured logging, dùng `print()` khắp nơi** | 🟢 Thấp | Đúng như nhận xét trong yêu cầu — tất cả script dùng `print()` trực tiếp, không có `run_id`, không log ra file. |

---

## 4. Dữ liệu hard-code (cần chuyển vào config)

| Vị trí | Giá trị hard-code | Nên chuyển tới |
|---|---|---|
| `data/assets.json` | `gold_luong: 6.5`, `bank_vnd_trieu: 246`, `cash_vnd_trieu: 35` | `config/portfolio.yaml` (đúng như đặc tả — giữ nguyên số, đổi format/vị trí) |
| `data/watchlist.json` + `docs/nghien-cuu-nganh-va-buffett-list.md` | Danh sách 11 mã Buffett-list, watchlist VCB/CTD | `config/portfolio.yaml` → `watchlist` |
| `data/alerts.json` | 6 ngưỡng giá VCB/CTD/vàng (58.0, 59.3, 63.0, 64.5, 3960, 4060) | Giữ dạng JSON hiện tại nhưng nên có `unit` rõ ràng; đây là *tham số theo dõi*, không phải bí mật, có thể giữ trong `data/` hoặc chuyển `config/` |
| `scripts/networth.py` dòng 88 | Ngưỡng cảnh báo tập trung `gold_pct >= 60` | `config/risk_limits.yaml` → `allocation_limits.gold_warning` (đặc tả đã cho sẵn 0.60/0.70) |
| `scripts/journal.py` dòng 78-79 | Chuỗi `"CHƯA MUA"`, `"MUA"` để đối chiếu khuyến nghị | `config/decision_rules.yaml` hoặc enum Python dùng chung |
| `scripts/gold_price.py` dòng ~ (docstring) | Hằng số `37,5/31,1035` viết tắt trong docstring | Cần đổi sang hằng số chính xác `GRAMS_PER_TROY_OUNCE = 31.1034768` như đặc tả (xem mục 6) |
| `data/gold_model.json` | `luong_per_oz: 1.205656` | Sai số ~0.00025% so với hằng số chuẩn 37.5/31.1034768 = 1.2056530 — nhỏ nhưng nên sửa đúng theo đặc tả |
| Mọi routine prompt (ngoài repo) | Toàn bộ nội dung bản tin, danh sách nguồn tin ưu tiên | Cần đưa logic thu thập dữ liệu vào code thay vì prompt tự do |

**Không tìm thấy** API key, token, mật khẩu, cookie nào bị commit (đã grep toàn repo).

---

## 5. Nguồn dữ liệu đang dùng

| Loại dữ liệu | Nguồn thực tế hiện nay | Có phải nguồn máy-đọc-được? |
|---|---|---|
| VN-Index, VCB, CTD giá/khối lượng | AI đọc báo (CafeF, Vietstock, Nhân Dân, DNSE...) qua WebSearch, gõ tay vào JSON | ❌ Không — là tóm tắt tin tức, không phải API |
| XAU/USD | AI đọc báo giá vàng quốc tế (RoboForex, TradingEconomics...) qua WebSearch | ❌ Không |
| Tỷ giá USD/VND | AI đọc báo tỷ giá Vietcombank qua WebSearch | ❌ Không |
| Giá vàng SJC/nhẫn trong nước | AI đọc báo (CafeF, Vietstock) qua WebSearch | ❌ Không |
| **Giá vàng tiệm Xuân Triệu** | **1 ảnh chụp màn hình do người dùng gửi tay**, hiệu chuẩn 1 lần vào `gold_model.json` | ❌ Không — đây là điểm hiệu chuẩn thủ công duy nhất có độ tin cậy cao (ảnh thật) |
| Lãi suất tiết kiệm | AI đọc báo (TOPI, Webgia...) qua WebSearch | ❌ Không |
| Tin lãnh đạo bị bắt/khởi tố, địa chính trị, Trump, Fed | AI đọc báo qua WebSearch, tự tóm tắt | ❌ Không |
| `data/eod/*.csv` | 2 dòng duy nhất, gõ tay từ số liệu HOSE đọc được qua báo | ❌ Không, và **quá ít** để tính chỉ báo |

→ **Không có bất kỳ API tài chính nào được gọi trực tiếp bằng code** trong repo hiện tại. Mọi con số đi qua "mắt và tay" của AI trong phiên tương tác. Đây chính là rủi ro sai số lớn nhất — đã xảy ra thật: bản tin sáng 18/7 từng ghi CTD ≈73.800đ (SAI, nguồn Simplize lỗi) rồi phải đính chính bằng 63.500đ (đúng, theo ảnh chụp báo cáo HOSE của người dùng) — xem `history.jsonl` dòng 2, trường `note`.

---

## 6. Rủi ro sai số

1. **Đã xảy ra thật (lịch sử)**: CTD bị ghi sai giá 73.800đ thay vì 63.500đ do dựa vào 1 nguồn báo chí lỗi, không có cơ chế đối chiếu 2 nguồn. Đây chính là kiểu lỗi mà "data contract + so sánh nhiều nguồn + CONFLICTING state" trong đặc tả mới được thiết kế để chặn.
2. **Không có kiểm tra dữ liệu cũ (stale)**: nếu một routine chạy fail giữa chừng và không cập nhật `history.jsonl`, bản tin kỳ sau vẫn "so với kỳ trước" dựa trên dữ liệu vài ngày tuổi mà không cảnh báo.
3. **Không phát hiện dữ liệu âm/bằng 0 bất thường**: `trend.py` không có validation nào chặn giá trị âm hoặc =0 được ghi vào lịch sử.
4. **Hệ số quy đổi vàng (`luong_per_oz`) sai số nhỏ (~0.0003tr/lượng)**: không đáng kể về tiền nhưng vi phạm đúng-theo-đặc-tả.
5. **Chỉ 1 điểm hiệu chuẩn giá tiệm Xuân Triệu**: mô hình tuyến tính dựa trên đúng 1 mẫu — MAE/độ tin cậy không thể tính được (đặc tả yêu cầu MAE 7 ngày/30 ngày, hiện chưa có đủ lịch sử `xuan_trieu_gold_history.csv` nào tồn tại — file này **chưa được tạo**).
6. **Backtest chưa tính chi phí giao dịch, trượt giá, spread vàng** — đã ghi chú trong output nhưng chưa trừ vào số liệu.
7. **`journal.py` đối chiếu khuyến nghị bằng khớp chuỗi tiếng Việt** — rủi ro false negative (không phát hiện lệnh đi ngược khuyến nghị) nếu cách diễn đạt đổi.

---

## 7. Rủi ro bảo mật

- **Không phát hiện secret nào bị commit** (đã grep `api[_-]?key|secret|token|password|Authorization` toàn repo, chỉ khớp 1 dòng vô hại nói về "Telegram bot token" trong roadmap dạng ghi chú kế hoạch).
- **Không có `.env`/`.env.example`** — chưa cần vì chưa có script nào gọi API cần xác thực.
- **Không có `.gitignore`** → rủi ro tương lai: nếu sau này thêm file `.env` thật hoặc cache có dữ liệu nhạy cảm, dễ bị commit nhầm.
- **`__pycache__` đã bị commit** — không nhạy cảm nhưng là dấu hiệu thiếu `.gitignore`, cần dọn ngay.
- **Dữ liệu tài sản cá nhân** (`data/assets.json`, `data/journal.jsonl`) **nằm trực tiếp trong git, không mã hóa** — repo là private nhưng đây vẫn là dữ liệu tài chính cá nhân nhạy cảm (số dư ngân hàng, tiền mặt, số lượng vàng). Cần lưu ý khi repo được chia sẻ/mở public sau này.

---

## 8. File cần giữ (đã đúng, không refactor lớn)

- `scripts/indicators.py`, `scripts/backtest.py`, `scripts/tick.py` — logic tính toán đúng, thuần Python, đã test. Chỉ cần: (a) thêm docstring/type hint theo chuẩn mới, (b) không viết lại thuật toán.
- `data/gold_model.json` cấu trúc hiệu chuẩn hợp lý — giữ nguyên concept, chỉ sửa hằng số + bổ sung field mô tả trong data contract.
- `docs/phuong-phap-phan-tich.md`, `docs/nghien-cuu-nganh-va-buffett-list.md` — nội dung phương pháp luận (Wyckoff/Buffett/Fisher) vẫn giá trị, dùng làm **input rule cho Decision Engine** thay vì chỉ để AI đọc rồi viết văn xuôi.

## 9. File cần refactor

| File | Vấn đề | Hướng refactor |
|---|---|---|
| `scripts/networth.py` | Hard-code ngưỡng 60%, import `gold_price` qua sys.path hack | Đọc ngưỡng từ `config/risk_limits.yaml`; sửa import bằng package chuẩn |
| `scripts/trend.py` | Không có validation dữ liệu (âm, thiếu, cũ), không gắn `source`/`confidence` | Thêm bước validate trước khi `append`; mở rộng schema theo data contract |
| `scripts/gold_price.py` | Hằng số thiếu chính xác; chưa lưu lịch sử hiệu chuẩn để tính MAE | Sửa hằng số; thêm `data/normalized/xuan_trieu_gold_history.csv` |
| `scripts/journal.py` | String-matching tiếng Việt cứng để đối chiếu khuyến nghị; thiếu guard chia 0 | Dùng enum hành động chuẩn; thêm guard |
| `dashboard/ban-tin-dau-tu.html` | Không có script sinh ra — sửa tay mỗi kỳ | Xây `reporting/render_dashboard.py` đọc từ `data/` + `decision/` output, sinh HTML tự động (Phase 8) |
| Toàn bộ `scripts/*.py` | Dùng `print()` trực tiếp | Chuyển sang `logging` module chuẩn có `run_id` (Phase 17 nhưng nên làm sớm ở Phase 2 vì mọi module sau đều cần) |

## 10. Thứ tự triển khai đề xuất

Theo đúng 10 phase trong đặc tả, đã đối chiếu với hiện trạng repo — xem chi tiết đầy đủ trong `docs/IMPLEMENTATION_PLAN.md`. Tóm tắt độ ưu tiên:

1. **Phase 2 (Data contract)** là khóa cho tất cả các phase sau — vì hiện tại **0%** dữ liệu có nguồn/độ tin cậy máy-đọc-được, mọi module sau (vàng, tiền gửi, chứng khoán, Risk Officer, Decision Engine) đều phụ thuộc vào nó.
2. **Phase 3 (Portfolio/Risk config)** dễ làm ngay vì số liệu đã có sẵn đúng trong `assets.json` — chỉ cần chuyển format sang YAML + thêm risk limits.
3. **Phase 4 (Vàng)** có nền tảng tốt nhất hiện tại (`gold_price.py`, `networth.py` đã chạy đúng) — refactor nhanh hơn xây mới.
4. **Phase 6 (Chứng khoán VN)** là phần rủi ro nhất về dữ liệu vì mạng bị chặn tới HOSE/entrade — cần thiết kế fallback rõ ràng (web-search-as-source với cảnh báo confidence thấp) thay vì giả định API luôn sẵn có.
5. **Phase 7 (Risk Officer + Decision Engine)** là phần **giá trị nhất** để giải quyết đúng vấn đề cốt lõi (L1, L2) — nên làm sớm ngay sau khi data contract xong, trước khi xây báo cáo/dashboard.
6. **Phase 8 (Bản tin + Dashboard)** nên là bước áp dụng cuối, sau khi Decision Engine đã có, để bản tin gọi engine thay vì AI tự viết kết luận.

---

*Báo cáo này không sửa bất kỳ file hoạt động nào. Toàn bộ nhận định dựa trên chạy thử trực tiếp trong môi trường ngày 2026-07-19.*
