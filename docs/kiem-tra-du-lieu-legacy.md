# Kiểm tra dữ liệu legacy ngày 18/07/2026

## Kết luận

Snapshot sáng 18/07 ban đầu có VCB 57.600 và CTD 73.800 nhưng không có `market_date`, thời điểm lấy hoặc nguồn theo field. Hai con số này không đủ điều kiện dùng cho quyết định.

Đối chiếu endpoint EOD trên tên miền HOSE cho ngày thị trường 17/07/2026:

| Mã | Tham chiếu | Đóng cửa | Thay đổi | Khối lượng |
|---|---:|---:|---:|---:|
| VCB | 59.400 đ | 58.500 đ | -1,52% | 1,9901 triệu cp |
| CTD | 66.200 đ | 63.500 đ | -4,08% | 0,4268 triệu cp |

Nguồn công khai: https://www.hsx.vn/vi/du-lieu-giao-dich/thong-ke/du-lieu-cuoi-ngay. Bản raw kiểm tra được lưu local trong `data/raw/hose/` và bị Git bỏ qua.

## Xử lý đã thực hiện

- Snapshot mới nhất đã thay giá/khối lượng VCB, CTD bằng số HOSE nêu trên và gắn `market_date`, `collected_at`, URL, `retrieved_at`, field cụ thể.
- Các trường VN-Index, vàng, tin vĩ mô và lãi suất legacy chưa đủ provenance vẫn được giữ để bảo toàn lịch sử nhưng không được mở khóa quyết định.
- Dashboard chỉ hiển thị sản phẩm tiết kiệm đã qua kiểm tra theo từng dòng; các mức lãi legacy không còn được trình bày như dữ liệu đã xác minh.

Không tự backfill các trường còn lại nếu chưa có raw/nguồn chính thức tương ứng.
