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
| Bản tin đầu tư sáng 8h | `0 1 * * *` | ~08:04 | `trig_01FRDsJoxuve2rZqa155NJbL` |
| Bản tin đầu tư chiều 6h | `0 11 * * *` | ~18:07 | `trig_015dnA1uyoL2zMK61MDwFgKD` |

Cả hai routine bắn vào phiên Claude Code gốc (session `session_013t34M5Yh9yPtmNDBRg4UYx`), dùng WebSearch lấy số liệu mới nhất kèm nguồn.

## Kênh xuất bản

- **Chat**: bản tin đầy đủ bằng tiếng Việt trong phiên Claude Code
- **Dashboard**: artifact cập nhật cùng URL mỗi kỳ — https://claude.ai/code/artifact/6f0a817e-7841-4b94-8e92-8c2393d0b551

## Cấu hình theo dõi hiện tại

- Danh mục: toàn thị trường theo nhóm ngành (chưa có danh sách mã cụ thể — thêm mã vào đây nếu muốn theo sát từng cổ phiếu)
- Vàng: cả trong nước + thế giới
- Tiền gửi: khoản dưới 1 tỷ đồng, ưu tiên so sánh online vs tại quầy
