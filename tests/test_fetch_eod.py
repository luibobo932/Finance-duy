"""Test cho scripts/fetch_eod.py — chỉ phần logic thuần túy (parse/merge/csv),
không gọi mạng thật (services.entrade.com.vn có thể bị chặn network policy
tùy môi trường — xem docs/ROADMAP.md mục 1)."""
from fetch_eod import load_existing, merge_rows, parse_ohlc_response, write_csv


def test_parse_ohlc_response_converts_epoch_to_date():
    data = {
        "t": [1752717600], "o": [61.35], "h": [62.25],
        "l": [61.35], "c": [61.75], "v": [9992700],
    }
    rows = parse_ohlc_response(data)
    assert len(rows) == 1
    assert rows[0]["close"] == 61.75
    assert rows[0]["volume"] == 9992700
    assert rows[0]["date"]  # ngày đã được format YYYY-MM-DD


def test_parse_ohlc_response_skips_null_entries():
    data = {"t": [None], "o": [None], "h": [None], "l": [None], "c": [None], "v": [None]}
    assert parse_ohlc_response(data) == []


def test_parse_ohlc_response_empty_input_returns_empty():
    assert parse_ohlc_response({}) == []


def test_merge_rows_new_date_appended():
    existing = [{"date": "2026-07-17", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]
    new = [{"date": "2026-07-20", "open": 2, "high": 2, "low": 2, "close": 2, "volume": 2}]
    merged = merge_rows(existing, new)
    assert [r["date"] for r in merged] == ["2026-07-17", "2026-07-20"]


def test_merge_rows_same_date_new_overwrites_old():
    existing = [{"date": "2026-07-17", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]
    new = [{"date": "2026-07-17", "open": 9, "high": 9, "low": 9, "close": 9, "volume": 9}]
    merged = merge_rows(existing, new)
    assert len(merged) == 1
    assert merged[0]["close"] == 9


def test_merge_rows_sorted_ascending_regardless_of_input_order():
    existing = [{"date": "2026-07-20", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]
    new = [{"date": "2026-07-17", "open": 2, "high": 2, "low": 2, "close": 2, "volume": 2}]
    merged = merge_rows(existing, new)
    assert [r["date"] for r in merged] == ["2026-07-17", "2026-07-20"]


def test_write_csv_then_load_existing_roundtrip(tmp_path):
    path = tmp_path / "VCB.csv"
    rows = [
        {"date": "2026-07-17", "open": 59.3, "high": 59.3, "low": 58.5, "close": 58.5, "volume": 1990100},
    ]
    write_csv(path, rows)
    loaded = load_existing(path)
    assert loaded == rows


def test_load_existing_missing_file_returns_empty(tmp_path):
    assert load_existing(tmp_path / "nope.csv") == []
