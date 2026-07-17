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
| Bản tin đầu tư sáng 8h | `0 1 * * *` | ~08:08 | `trig_01WXaoTuCY38ZTunJqR2JDMe` |
| Bản tin đầu tư chiều 6h | `0 11 * * *` | ~18:00 | `trig_01Nfm3YyDJ87cKK5yiC6yCWv` |

## Lịch sử số liệu & xu hướng

- `data/history.jsonl` — mỗi bản tin append 1 dòng JSON snapshot (VN-Index, VCB, CTD, khối ngoại, vàng, tỷ giá, top lãi suất, cờ rủi ro). Xem dòng đầu file làm schema mẫu.
- `data/portfolio.json` — giá vốn + số lượng VCB/CTD để tính lãi/lỗ thực tế (null = chưa cung cấp).
- `scripts/trend.py`:
  - `append '<json>'` — validate và ghi snapshot mới (chặn ghi trùng ngày+kỳ)
  - `report` — so sánh với kỳ trước: biến động VN-Index/VCB/CTD/vàng, chuỗi mua/bán ròng khối ngoại (chỉ tính kỳ chiều để không đếm trùng phiên), **KLGD từng mã vs bình quân 20 phiên (cảnh báo ⚠️ khi ≥1,5× — dấu hiệu cần soi thỏa thuận/giao dịch nội bộ)**, chênh lệch vàng nới/thu hẹp, ngân hàng thay đổi lãi suất, lãi/lỗ danh mục
- Mỗi routine tự commit + push `data/` sau khi ghi để lịch sử bền vững qua các container.

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
