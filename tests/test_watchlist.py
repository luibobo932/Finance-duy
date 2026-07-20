"""Test cho scripts/watchlist.py — logic áp giá thật vào watchlist (thuần túy,
không gọi mạng; phần fetch dùng chung fetch_eod đã test riêng)."""
from watchlist import apply_prices


def _data() -> dict:
    return {
        "base_date": "2026-07-18",
        "stocks": [
            {"ticker": "FPT", "group": "A", "base_price": None, "last_price": None, "moat": "x"},
            {"ticker": "VCB", "group": "A", "base_price": 58.5, "last_price": 58.5, "moat": "x"},
        ],
    }


def test_apply_prices_fills_null_base_with_last_close_on_or_before_base_date():
    closes = {"FPT": [("2026-07-16", 90.0), ("2026-07-17", 92.0), ("2026-07-20", 95.0)]}
    data, notes = apply_prices(_data(), closes)
    fpt = data["stocks"][0]
    # base_date 18/7 là thứ Bảy — phiên gần nhất TRƯỚC đó là 17/7, không được
    # lấy 20/7 (sau ngày lập danh sách = look-ahead)
    assert fpt["base_price"] == 92.0
    assert fpt["last_price"] == 95.0


def test_apply_prices_never_overwrites_existing_base():
    closes = {"VCB": [("2026-07-17", 58.5), ("2026-07-20", 60.0)]}
    data, notes = apply_prices(_data(), closes)
    vcb = data["stocks"][1]
    assert vcb["base_price"] == 58.5  # giữ nguyên giá tham chiếu gốc
    assert vcb["last_price"] == 60.0


def test_apply_prices_missing_ticker_left_untouched_with_note():
    data, notes = apply_prices(_data(), {"VCB": [("2026-07-20", 60.0)]})
    fpt = data["stocks"][0]
    assert fpt["base_price"] is None
    assert fpt["last_price"] is None
    assert any("FPT" in n for n in notes)


def test_apply_prices_no_close_before_base_date_leaves_base_null():
    # Chỉ có dữ liệu SAU ngày lập → không được bịa base bằng giá tương lai
    closes = {"FPT": [("2026-07-20", 95.0)]}
    data, notes = apply_prices(_data(), closes)
    fpt = data["stocks"][0]
    assert fpt["base_price"] is None
    assert fpt["last_price"] == 95.0
    assert any("FPT" in n and "base" in n.lower() for n in notes)
