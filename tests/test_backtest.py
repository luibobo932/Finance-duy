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
    # Chi phí tính CHUNG với equity/costs.py, không phải công thức riêng.
    # Công thức cũ `- 2*fee_pct` trừ phí như điểm phần trăm phẳng nên chênh
    # lệch luôn đúng bằng 0,3 — con số đó chính là cái sai đã được mã hoá vào
    # test. Phí mua tính trên tiền VÀO, phí bán trên tiền RA, nên chênh lệch
    # phụ thuộc mức lãi/lỗ của lệnh.
    from equity.costs import net_upside_pct

    for tr, fee in ((no_fee[0], 0.0), (with_fee[0], 0.15)):
        gross = (tr[3] - tr[2]) / tr[2] * 100
        assert abs(tr[4] - net_upside_pct(gross, fee)) < 1e-9


def test_thue_ban_luon_bi_tru_ke_ca_khi_khong_khai_phi():
    """Thuế bán 0,1% là bắt buộc, nộp KỂ CẢ KHI LỖ — `--fee 0` không có nghĩa
    là giao dịch miễn phí. Công thức cũ trả về đúng lợi nhuận gộp ở đây."""
    from equity.costs import SELL_TAX_PCT

    closes = [100.0] * 10 + [105.0, 106.0, 107.0, 108.0, 90.0]
    tr = backtest_ma(_series(closes), n=5, fee_pct=0.0)[0]
    gross = (tr[3] - tr[2]) / tr[2] * 100
    assert tr[4] < gross, "lợi nhuận sau chi phí không được bằng lợi nhuận gộp"
    assert abs((gross - tr[4]) - SELL_TAX_PCT * (1 + gross / 100)) < 1e-6



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


# --- Backtest phải trả lời được "có đáng theo không", không chỉ "được bao nhiêu" ---

def test_lai_gop_khong_bao_gio_duoc_bao_cao_nhu_lai_thuc():
    """Chống tái phát lớp lỗi gốc: một công thức chi phí RIÊNG trong backtest.

    Mọi mức phí, mọi mức lãi/lỗ — kết quả phải khớp `equity/costs.py`, module
    duy nhất mô hình hoá thuế phí trong cả dự án.
    """
    from equity.costs import net_upside_pct

    closes = [100.0] * 10 + [105.0, 106.0, 107.0, 108.0, 90.0]
    for fee in (0.0, 0.15, 0.2, 0.35):
        tr = backtest_ma(_series(closes), n=5, fee_pct=fee)[0]
        gross = (tr[3] - tr[2]) / tr[2] * 100
        assert abs(tr[4] - net_upside_pct(gross, fee)) < 1e-9, f"lệch ở phí {fee}"


def test_cong_thuc_cu_luon_lac_quan_hon_cong_thuc_dung():
    """Sai số của công thức cũ luôn CÙNG MỘT CHIỀU — đó mới là vấn đề, không
    phải độ lớn: nó cộng dồn theo số lệnh, đúng ở phía làm quy tắc trông tốt
    hơn thực tế."""
    from equity.costs import net_upside_pct

    for buy, sell in [(62.4, 63.0), (62.4, 70.0), (62.4, 93.0), (62.4, 55.0), (100, 200)]:
        gross = (sell - buy) / buy * 100
        cu = gross - 2 * 0.2                      # công thức cũ
        dung = net_upside_pct(gross, 0.2)
        assert cu > dung, f"mua {buy} bán {sell}: công thức cũ không lạc quan hơn?"


def test_so_voi_tien_gui_khong_qui_nam_mau_qua_nho(capsys):
    """3 lệnh trong 43 phiên qui ra %/năm là phóng đại một mẫu nhỏ thành tuyên
    bố về tương lai. Phép so phải trên ĐÚNG số ngày vốn nằm trong thị trường."""
    from backtest import _so_voi_tien_gui

    trades = [("2026-06-30", "2026-07-02", 72.7, 72.0, -1.5)]
    _so_voi_tien_gui(trades, -1.5)
    out = capsys.readouterr().out
    if "Chưa có bảng lãi suất" in out:
        import pytest
        pytest.skip("chưa có bảng lãi suất chuẩn hoá")
    assert "2 ngày" in out
    assert "%/năm" in out          # nêu rõ mức tiền gửi lấy từ đâu
    assert "quá ít" in out         # cảnh báo cỡ mẫu
