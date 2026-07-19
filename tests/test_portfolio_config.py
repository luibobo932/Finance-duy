"""Test cho portfolio/loader.py — nạp config/*.yaml (Phase 3)."""
from portfolio.loader import StockPosition, load_decision_rules, load_portfolio, load_risk_limits, load_source_priority


def test_load_portfolio_matches_known_values():
    port = load_portfolio()
    assert port.currency == "VND"
    assert port.gold_quantity_tael == 6.5
    assert port.savings_principal_vnd == 246_000_000
    assert port.cash_amount_vnd == 35_000_000
    assert port.watchlist == ["VCB", "CTD"]
    assert port.stock_positions == []  # đã bán hết cổ phiếu


def test_stock_market_value_empty_portfolio_is_zero():
    port = load_portfolio()
    assert port.stock_market_value_vnd == 0


def test_stock_position_market_value_and_pnl():
    p = StockPosition(ticker="VCB", quantity=1000, avg_cost_vnd=55000, last_price_vnd=58500)
    assert p.market_value_vnd == 58_500_000
    assert p.unrealized_pnl_vnd == 3_500_000


def test_stock_position_pnl_none_when_missing_cost():
    p = StockPosition(ticker="VCB", quantity=1000, last_price_vnd=58500)
    assert p.unrealized_pnl_vnd is None


def test_load_risk_limits_matches_spec():
    limits = load_risk_limits()
    assert limits["gold_warning"] == 0.60
    assert limits["gold_critical"] == 0.70
    assert limits["single_stock_max"] == 0.10
    assert limits["total_stock_max"] == 0.20
    assert limits["minimum_cash_buffer_vnd"] == 30_000_000


def test_load_source_priority_structure():
    cfg = load_source_priority()
    assert "hose_api" in cfg["blocked_sources"]
    assert "entrade_api" in cfg["blocked_sources"]
    assert "web_search_summary" in cfg["priority"]["vn_index"]


def test_load_decision_rules_gold_thresholds_present():
    rules = load_decision_rules()
    assert rules["gold"]["above_critical_action"] == "DO_NOT_BUY_MORE"
    assert rules["gold"]["above_warning_action"] == "TAKE_PARTIAL_PROFIT"
    assert rules["gold"]["below_warning_action"] == "HOLD"
