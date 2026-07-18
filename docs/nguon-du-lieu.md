# Nguồn dữ liệu chính thức và nguyên tắc sử dụng

Danh sách máy đọc nằm ở `config/sources.json`. Tài liệu này giải thích cách dùng để tránh trộn dữ liệu hoặc vi phạm quyền phân phối.

## Chứng khoán Việt Nam

- [HOSE — dữ liệu cuối ngày](https://www.hsx.vn/vi/du-lieu-giao-dich/thong-ke/du-lieu-cuoi-ngay): nguồn chính cho VN-Index, VCB, CTD, OHLCV.
- Giá cổ phiếu lưu bằng VND; khối lượng chỉ lưu bằng `volume_million_shares`. Không dùng field `volume` chung chung.
- [HOSE — công bố thông tin](https://www.hsx.vn/vi/quy-dinh-hose/cong-bo-thong-tin), [Vietcombank IR](https://www.vietcombank.com.vn/vi-VN/Nha-dau-tu), [Coteccons IR](https://www.coteccons.vn/investor-relations-vn/): báo cáo và sự kiện doanh nghiệp.
- Endpoint JSON nội bộ HOSE không có SLA và có thể thay đổi. Phải lưu raw, hash và fallback sang báo cáo/PDF chính thức. Không mặc định được phép phân phối lại dữ liệu thị trường.

## Vàng và tỷ giá

- [SJC — giá vàng trực tuyến](https://www.sjc.com.vn/gia-vang-online): lưu riêng brand, product, region, giá mua, giá bán và đơn vị.
- [LBMA Gold Price](https://www.lbma.org.uk/prices-and-data/lbma-gold-price): benchmark có điều kiện giấy phép; không scrape rồi phân phối lại. Nếu dùng CME GC phải ghi rõ là proxy, không gọi là XAU/USD.
- [Vietcombank](https://www.vietcombank.com.vn/): API tỷ giá chính thức được collector `collect_vietcombank.py` sử dụng để quy đổi.

## Gửi tiết kiệm

- API lãi suất chính thức Vietcombank là nguồn đầu tiên; bổ sung trang/PDF chính thức từng ngân hàng, không lấy bảng tổng hợp báo chí làm nguồn duy nhất.
- Mỗi mức lãi phải có: kênh gửi, kỳ hạn, số tiền min/max, khách hàng áp dụng, cách trả lãi, ngày hiệu lực và URL.
- Mỗi dòng sản phẩm phải có `source_id`, `source_url`, `retrieved_at`; ngân hàng trong dòng phải khớp publisher được registry cho phép. Một URL Vietcombank không thể xác minh lãi suất của ngân hàng khác.
- “Dưới 1 tỷ” phải lọc thật theo điều kiện sản phẩm; đúng 1 tỷ không thuộc phạm vi.
- Theo [Bảo hiểm Tiền gửi Việt Nam](https://div.gov.vn/tu-ngay-13-7-2026-han-muc-chi-tra-tien-bao-hiem-cua-bao-hiem-tien-gui-viet-nam-la-350-trieu-dong), từ 13/07/2026 hạn mức chi trả tối đa là 350 triệu đồng gồm gốc và lãi cho một người tại một tổ chức tham gia.

## Quy tắc bắt buộc

1. Không có URL + thời điểm lấy + đơn vị → không được mở khóa quyết định.
2. `market_date` là ngày giá có hiệu lực; `date` là ngày bản tin. Không dùng hai trường thay nhau.
3. Dữ liệu cũ hơn stale limit → dashboard phải chuyển về `CHỜ DỮ LIỆU` ngay lúc người dùng mở trang.
4. Raw chỉ nằm trong `data/raw/` và không commit; snapshot đã duyệt mới được đưa vào lịch sử.
5. Nguồn không liên quan tới field không được cộng confidence.
6. `market_date`, `gold.observed_at` và `retrieved_at` không được nằm sau `collected_at`; field quá hạn bị khóa dù snapshot vừa được nhập lại.
