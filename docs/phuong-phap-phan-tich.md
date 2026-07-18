# Phương pháp phân tích — khung chuẩn cho mọi bản tin

Bản tin PHẢI áp dụng khung này khi phân tích VCB, CTD và thị trường chung.

## 1. Phát hiện giao dịch bất thường / dấu hiệu nội bộ

Dữ liệu tick từng lệnh không có qua web — dùng 4 kênh proxy sau (đều công khai):

1. **Khối lượng vs bình quân 20 phiên**: KLGD ngày ≥ 1,5× BQ20 = đột biến, cần giải thích được bằng tin tức. Đột biến KHÔNG có tin = nghi vấn dòng tiền biết trước.
2. **Giao dịch thỏa thuận (put-through)**: deal thỏa thuận lớn bất thường (đặc biệt giá trần/sàn hoặc lệch xa giá khớp) thường là sang tay của cổ đông lớn/nội bộ.
3. **Wyckoff — Effort vs Result**: khối lượng rất lớn nhưng giá không đi tương ứng:
   - Volume lớn + giá không tăng nổi ở vùng đỉnh → nghi **phân phối** (tay to xả)
   - Volume lớn + giá không giảm thêm ở vùng đáy → nghi **tích lũy** (tay to gom)
4. **Công bố giao dịch người nội bộ (HOSE/Vietstock/CafeF)**: lãnh đạo, cổ đông lớn, người liên quan phải đăng ký trước khi mua/bán. Quét tin "đăng ký mua/bán", "báo cáo kết quả giao dịch" của VCB, CTD — lãnh đạo bán mạnh trước KQKD là cờ đỏ; đăng ký mua là tín hiệu tự tin.
5. **Lệnh tròn số lặp lại (heuristic của chủ danh mục — ưu tiên áp dụng cho CTD)**: trong bảng khớp lệnh, các lệnh khối lượng LỚN + TRÒN SỐ (10.000, 20.000, 50.000, 100.000 cp...) xuất hiện LIÊN TỤC/ĐỀU ĐẶN là một tín hiệu bất thường cần điều tra. Nó có thể đến từ thuật toán chia lệnh, tạo lập, quỹ hoặc nhiều người giao dịch trùng cỡ lệnh; **không đủ để kết luận giao dịch nội bộ hay đang gom hàng**. Khi có dữ liệu khớp lệnh chi tiết, chạy `scripts/tick.py` để đếm tự động, rồi bắt buộc đối chiếu chiều mua/bán chủ động, vùng giá, giao dịch thỏa thuận và công bố chính thức. Chỉ xem là bằng chứng hỗ trợ cho giả thuyết tích lũy khi nhiều tín hiệu độc lập cùng xác nhận.

## 2. Wyckoff — đọc cấu trúc thị trường

- **3 quy luật**: Cung–Cầu (giá tăng khi cầu > cung); Nguyên nhân–Kết quả (tích lũy càng lâu, sóng càng lớn); Nỗ lực–Kết quả (volume phải xác nhận giá).
- **4 pha**: Tích lũy → Tăng giá (markup) → Phân phối → Giảm giá (markdown). Xác định VCB/CTD đang ở pha nào.
- **Tín hiệu then chốt**: Spring (rũ xuống dưới hỗ trợ rồi bật lại = tín hiệu mua), Upthrust (vượt kháng cự giả rồi rơi = tín hiệu bán), SOS (Sign of Strength: tăng mạnh volume lớn), SOW (Sign of Weakness).

## 3. Nến Nhật — mẫu hình cần nhận diện mỗi phiên

- **Đảo chiều tăng**: Hammer (rút chân ở đáy), Bullish Engulfing (nhấn chìm tăng), Morning Star, Piercing Line — chỉ có giá trị ở vùng hỗ trợ + volume xác nhận.
- **Đảo chiều giảm**: Shooting Star, Bearish Engulfing, Evening Star, Dark Cloud Cover — giá trị ở vùng kháng cự.
- **Do dự**: Doji, Spinning Top — tại đỉnh/đáy sau xu hướng dài là cảnh báo sớm.
- Luôn ghi rõ: mẫu nến phiên gần nhất của VCB, CTD + vị trí (hỗ trợ/kháng cự) + volume có xác nhận không.

## 4. Buffett — phân tích cơ bản (áp dụng khi có KQKD, định giá)

- **Lợi thế cạnh tranh bền vững (moat)**: VCB = thương hiệu + chi phí vốn rẻ nhất hệ thống; CTD = năng lực tổng thầu + backlog. Moat còn nguyên hay đang bị xói mòn?
- **Chỉ số cốt lõi**: ROE ổn định ≥ 15% (ngân hàng ≥ 18% là tốt), biên lợi nhuận, nợ vay hợp lý.
- **Định giá có biên an toàn**: so P/B của VCB với trung bình ngành + lịch sử chính nó; P/E của CTD với tốc độ tăng trưởng lợi nhuận. Giá tốt cho doanh nghiệp tuyệt vời > giá tuyệt vời cho doanh nghiệp tầm thường.
- **Tâm lý**: "Tham lam khi người khác sợ hãi" — thị trường hoảng loạn không do nội tại doanh nghiệp = cơ hội.

## 5. Philip Fisher — 15 điểm (rút gọn các điểm soi được từ tin tức)

- Sản phẩm/dịch vụ còn dư địa tăng trưởng dài hạn không? (VCB: tín dụng, phí; CTD: backlog, đầu tư công, FDI)
- Ban lãnh đạo có chính trực và giỏi không? — mọi tin về quản trị, kiện tụng, thay lãnh đạo đều phải đánh giá
- Biên lợi nhuận có đang cải thiện không?
- **Scuttlebutt**: tin từ đối thủ, khách hàng, nhà cung cấp (VD: chủ đầu tư nói gì về Coteccons, khách hàng doanh nghiệp chọn ngân hàng nào)
- Khi nào bán theo Fisher: chỉ khi doanh nghiệp xấu đi về nội tại hoặc luận điểm ban đầu sai — KHÔNG bán chỉ vì giá đã tăng.

## 6. Quy tắc kết luận trong bản tin

Mỗi bản tin, phần phân tích VCB/CTD kết thúc bằng 3 dòng:
- **Kỹ thuật (Wyckoff + nến)**: pha hiện tại, tín hiệu, vùng mua/bán đáng chú ý
- **Cơ bản (Buffett + Fisher)**: luận điểm còn nguyên vẹn không, có cờ đỏ quản trị không
- **Khối lượng/nội bộ**: có bất thường không, người nội bộ đang đăng ký mua hay bán
