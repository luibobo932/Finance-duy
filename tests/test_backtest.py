"""Test cho scripts/backtest.py (Phase 9) — MA cross + RSI rule + phí giao dịch.

Kiểm chứng chống look-ahead: tín hiệu tại phiên i chỉ được tính từ dữ liệu
tới phiên i, không nhìn thấy phiên i+1.
"""
from backtest import backtest_ma, backtest_rsi


def _series(closes: list[float]) -> list[tuple[str, float]]:
    return [(f"2026-01-{i+1:02d}", c) for i, c in enumerate(closes)]


def test_backtest_ma_insufficient_data_returns_none():
    assert backtest_ma(_series([1.0] * 5), n=20) is None


def test_backtest_ma_cross_up_then_down_creates_one_trade():
    # 10 phiên đi ngang 100 → tăng vượt MA → rơi xuống dưới MA
    closes = [100.0] * 10 + [105.0, 106.0, 107.0, 108.0, 90.0]
    trades = backtest_ma(_series(closes), n=5)
    assert trades is not None
    assert len(trades) == 1
    buy_date, sell_date, buy_price, sell_price, ret = trades[0]
    assert buy_price == 105.0
    assert sell_price == 90.0
    assert ret < 0  # lệnh này lỗ — backtest phải báo trung thực


def test_backtest_ma_fee_reduces_return():
    closes = [100.0] * 10 + [105.0, 106.0, 107.0, 108.0, 90.0]
    no_fee = backtest_ma(_series(closes), n=5, fee_pct=0.0)
    with_fee = backtest_ma(_series(closes), n=5, fee_pct=0.15)
    assert with_fee[0][4] < no_fee[0][4]
    # phí 0,15%/chiều × 2 chiều = lệch đúng ~0,3 điểm %
    assert abs((no_fee[0][4] - with_fee[0][4]) - 0.3) < 0.01


def test_backtest_rsi_buys_oversold_sells_overbought():
    # Giảm liên tục (RSI → 0, quá bán) rồi tăng liên tục (RSI → 100, quá mua)
    closes = [100.0 - i * 2 for i in range(16)] + [70.0 + i * 3 for i in range(1, 16)]
    trades = backtest_rsi(_series(closes), period=14, buy_th=30, sell_th=70)
    assert trades is not None
    assert len(trades) >= 1
    buy_date, sell_date, buy_price, sell_price, ret = trades[0]
    assert sell_price > buy_price  # mua đáy quá bán, bán vùng quá mua → lãi
    assert ret > 0


def test_backtest_rsi_insufficient_data_returns_none():
    assert backtest_rsi(_series([100.0] * 5), period=14) is None


def test_backtest_rsi_no_signal_in_flat_market_returns_empty():
    trades = backtest_rsi(_series([100.0, 101.0] * 20), period=14)
    assert trades == []
