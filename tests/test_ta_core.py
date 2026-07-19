"""Test cho analytics/ta_core.py — hàm mới atr/volatility (Phase 4).

sma/rsi/macd/bollinger đã được bảo vệ gián tiếp qua regression test
scripts/indicators.py (xem docs/AUDIT_REPORT.md) — không lặp lại ở đây.
"""
from analytics.ta_core import atr, volatility_annualized_pct


def test_atr_positive_with_enough_data():
    highs = [10, 11, 12, 11, 13, 14, 13, 15, 16, 15] * 2
    lows = [9, 10, 11, 10, 12, 13, 12, 14, 15, 14] * 2
    closes = [9.5, 10.5, 11.5, 10.5, 12.5, 13.5, 12.5, 14.5, 15.5, 14.5] * 2
    a = atr(highs, lows, closes, n=14)
    assert a is not None
    assert a > 0


def test_atr_insufficient_data_returns_none():
    assert atr([1, 2], [1, 2], [1, 2], n=14) is None


def test_atr_mismatched_lengths_returns_none():
    assert atr([1, 2, 3], [1, 2], [1, 2, 3], n=1) is None


def test_volatility_positive_for_varying_prices():
    closes = [100, 101, 99, 102, 98, 103, 97, 104, 96, 105, 95, 106, 94, 107, 93, 108, 92, 109, 91, 110, 90]
    v = volatility_annualized_pct(closes, n=20)
    assert v is not None
    assert v > 0


def test_volatility_zero_for_constant_prices():
    closes = [100.0] * 25
    v = volatility_annualized_pct(closes, n=20)
    assert v == 0


def test_volatility_insufficient_data_returns_none():
    assert volatility_annualized_pct([100, 101], n=20) is None
