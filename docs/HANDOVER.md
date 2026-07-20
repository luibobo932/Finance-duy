# Tài liệu bàn giao dự án — Bản tin Đầu tư tự động

> ⚠️ **CŨ — chỉ còn giá trị lịch sử.** File này viết trước đợt tái cấu trúc lớn
> (Phase 1-8: Data Contract, `config/*.yaml`, module `gold/`, `deposits/`,
> `equity/`, `decision/` + Risk Officer, `reporting/`, Telegram). **Đọc
> `README.md` (mục lục đầy đủ, cập nhật) và `docs/ROADMAP.md` (trạng thái 12
> hạng mục) trước — chỉ quay lại đây nếu cần bối cảnh quy trình thủ công ban đầu.**

Tài liệu này đủ để một agent/dev khác (Codex, v.v.) tiếp quản và tái dựng toàn bộ hệ thống.

## Hệ thống làm gì

Bản tin đầu tư 2 lần/ngày (8h sáng & 6h chiều giờ VN, GMT+7) phục vụ ra quyết định:
1. **Danh mục cá nhân VCB + CTD**: giá, khối lượng, tin tức, khối ngoại từng mã
2. **Chứng khoán VN**: VN-Index, nhóm ngành hưởng lợi/bất lợi, động thái quỹ lớn + khối ngoại
3. **Cảnh báo rủi ro**: lãnh đạo tập đoàn bị bắt/khởi tố → đánh giá lan tỏa + cách phòng ngừa
4. **Vàng**: SJC/nhẫn/XAU-USD, chênh lệch VN–TG, địa chính trị/chiến tranh, động thái Trump, Fed
5. **Lãi suất tiết kiệm**: cao nhất cho khoản DƯỚI 1 tỷ đồng (loại lãi suất đặc biệt cần số dư lớn)
6. **Xu hướng**: so sánh với kỳ trước từ lịch sử tích lũy + lãi/lỗ danh mục

## Cấu trúc repo

| Đường dẫn | Vai trò |
|---|---|
| `README.md` | Tổng quan + cấu hình theo dõi hiện tại |
| `docs/phuong-phap-phan-tich.md` | **Khung phân tích bắt buộc**: phát hiện giao dịch nội bộ (KLGD vs BQ20, thỏa thuận, effort-vs-result Wyckoff, công bố nội bộ HOSE, lệnh tròn số lặp lại), Wyckoff, nến Nhật, Buffett, Fisher |
| `data/history.jsonl` | Lịch sử snapshot mỗi kỳ bản tin (schema: xem dòng mẫu) |
| `data/portfolio.json` | Giá vốn + số lượng VCB/CTD (**đang null — chờ chủ dự án cung cấp**) |
| `scripts/trend.py` | `append '<json>'` ghi snapshot (chặn trùng ngày+kỳ); `report` so sánh kỳ trước: delta giá/vàng, chuỗi mua-bán ròng khối ngoại (chỉ tính kỳ "chieu"), KLGD vs BQ20 (cảnh báo ≥1,5×), thay đổi lãi suất, P&L danh mục |
| `scripts/tick.py` | Phát hiện gom hàng nội bộ: `fetch <MÃ> <YYYY-MM-DD>` (nến 1 phút API DNSE entrade) hoặc `csv <file>` (khớp lệnh từng dòng, 3 cột time,price,volume); đếm lệnh lớn TRÒN SỐ lặp ≥3 lần |
| `dashboard/ban-tin-dau-tu.html` | Dashboard tự chứa (inline CSS, hỗ trợ dark/light) — cập nhật số liệu mỗi kỳ rồi deploy lại |

Scripts chỉ dùng Python 3 chuẩn, không dependency ngoài.

## Quy trình mỗi kỳ bản tin (thứ tự bắt buộc)

1. `git pull` nhánh làm việc
2. Đọc `docs/phuong-phap-phan-tich.md`
3. Thu thập số liệu mới nhất (web search / API): phiên gần nhất, VCB, CTD, vàng, tỷ giá, lãi suất, tin nội bộ/rủi ro, tin Trump/Fed/địa chính trị
4. `python3 scripts/trend.py append '<json snapshot>'` (ky = "sang" hoặc "chieu"; kỳ sáng để `foreign_net_ty` null nếu phiên đó đã ghi ở kỳ chiều trước — tránh đếm trùng chuỗi khối ngoại)
5. `python3 scripts/trend.py report` → đưa nguyên văn vào bản tin
6. Cập nhật `dashboard/ban-tin-dau-tu.html` + deploy
7. `git add data/ dashboard/ && git commit && git push`
8. Soạn bản tin tiếng Việt đầy đủ, kết phần VCB/CTD bằng 3 dòng: Kỹ thuật / Cơ bản / Khối lượng-nội bộ; cuối bản tin là "Gợi ý hành động"; luôn kèm nguồn

## Những thứ KHÔNG nằm trong repo (phải dựng lại khi đổi nền tảng)

1. **Lịch chạy**: hiện là 2 Claude Code Routines (cron UTC `0 1 * * *` và `0 11 * * *` ≈ 8h/18h VN) bắn prompt vào phiên Claude. Chuyển nền tảng khác → thay bằng GitHub Actions `schedule` hoặc cron server, gọi agent với prompt mô tả ở mục "Quy trình" trên. Nội dung prompt đầy đủ nằm trong lịch sử hội thoại phiên Claude gốc; quy trình 8 bước trên là bản đặc tả đủ dùng.
2. **Dashboard hosting**: hiện deploy làm Claude Artifact (URL riêng tư của chủ dự án). Chuyển nền tảng → dùng GitHub Pages (bật Pages cho thư mục `dashboard/`) hoặc bất kỳ static host nào; file HTML tự chứa 100%.
3. **Kênh trả bản tin**: hiện trả vào chat phiên Claude. Chuyển nền tảng → email/Telegram/Slack tùy chọn.

## Việc đang dở / cần chủ dự án

- [ ] **Giá vốn + số lượng VCB, CTD** → điền vào `data/portfolio.json` để bật tính lãi/lỗ (`avg_cost` đơn vị đồng, `quantity` cổ phiếu)
- [ ] **Nguồn dữ liệu khớp lệnh chi tiết**: môi trường hiện tại bị chặn API (CafeF 403, entrade/VNDirect bị proxy chặn). Cần một trong: mở network policy cho `services.entrade.com.vn`, hoặc API key FireAnt/SSI, hoặc chủ dự án xuất CSV khớp lệnh từ app chứng khoán → `scripts/tick.py csv`
- [ ] Yêu cầu đặc biệt của chủ dự án: **soi lệnh khối lượng lớn TRÒN SỐ lặp lại liên tục của CTD** (dấu hiệu tổ chức/nội bộ gom) để chọn điểm vào giá — logic đã có sẵn trong `tick.py`, chỉ thiếu dữ liệu đầu vào
- [ ] Lịch sử mới có 2 snapshot (17/7 chiều, 18/7 sáng) — KLGD vs BQ20 cần ~20 phiên tích lũy mới có ý nghĩa

## Bối cảnh số liệu gần nhất (18/07/2026)

VN-Index 1.787,45 (−0,93% phiên 17/7); VCB ≈57.600 (−1,52%); CTD ≈73.800 (mạnh hơn thị trường, +3,9% từ 8/7); khối ngoại bán ròng 690 tỷ; vàng SJC 143,6–146,6 tr, XAU 4.017 $ (chênh ~18,4 tr); lãi suất cao nhất <1 tỷ: Cake by VPBank 7,4%/12T online. Rủi ro vĩ mô đang theo dõi: bán tháo chip toàn cầu, Mỹ–Iran leo thang, Trump dọa phá đình chiến thuế quan Mỹ–Trung, Fed họp cuối tháng 7.
