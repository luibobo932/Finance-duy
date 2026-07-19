"""Test cho validate_snapshot() trong scripts/trend.py (Phase 2).

Chỉ test hàm thuần (không I/O) — KHÔNG gọi cmd_append/cmd_report vì chúng
đọc/ghi trực tiếp vào data/history.jsonl thật (dữ liệu sản xuất), không an
toàn để test tự động cho tới khi trend.py được refactor để inject đường dẫn
(việc này ghi trong docs/IMPLEMENTATION_PLAN.md, Phase 9).
"""
import trend


def test_validate_snapshot_rejects_negative_vnindex():
    snap = {"date": "2099-01-01", "ky": "sang", "vnindex": {"close": -5}, "gold": {"xauusd": 4000}}
    errors = trend.validate_snapshot(snap)
    assert any("vnindex.close" in e for e in errors)


def test_validate_snapshot_rejects_zero_gold_price():
    snap = {"date": "2099-01-01", "ky": "sang", "vnindex": {"close": 1800}, "gold": {"xauusd": 0}}
    errors = trend.validate_snapshot(snap)
    assert any("gold.xauusd" in e for e in errors)


def test_validate_snapshot_allows_zero_foreign_net_ty():
    snap = {
        "date": "2099-01-01",
        "ky": "chieu",
        "vnindex": {"close": 1800},
        "gold": {"xauusd": 4000},
        "foreign_net_ty": 0,
    }
    assert trend.validate_snapshot(snap) == []


def test_validate_snapshot_allows_negative_foreign_net_ty():
    # bán ròng là số âm hợp lệ, không được coi là bất thường
    snap = {
        "date": "2099-01-01",
        "ky": "chieu",
        "vnindex": {"close": 1800},
        "gold": {"xauusd": 4000},
        "foreign_net_ty": -690,
    }
    assert trend.validate_snapshot(snap) == []


def test_validate_snapshot_passes_realistic_valid_data():
    snap = {
        "date": "2099-01-01",
        "ky": "sang",
        "vnindex": {"close": 1787.45},
        "vcb": {"close": 58500},
        "ctd": {"close": 63500},
        "gold": {"xauusd": 4017, "sjc_sell": 147.5, "sjc_buy": 144.5, "ring_sell": 146.5},
        "fx_vcb_sell": 26460,
    }
    assert trend.validate_snapshot(snap) == []


def test_validate_snapshot_ignores_missing_optional_price_fields():
    # CTD chưa có giá kỳ này (None/absent) -> không được flag là bất thường,
    # khác hẳn với "có mặt nhưng = 0"
    snap = {"date": "2099-01-01", "ky": "sang", "vnindex": {"close": 1800}, "gold": {"xauusd": 4017}}
    assert trend.validate_snapshot(snap) == []


def test_validate_snapshot_multiple_errors_all_reported():
    snap = {
        "date": "2099-01-01",
        "ky": "sang",
        "vnindex": {"close": -1},
        "vcb": {"close": 0},
        "gold": {"xauusd": 4017},
    }
    errors = trend.validate_snapshot(snap)
    assert len(errors) == 2
