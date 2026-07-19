"""Test cho reporting/render_dashboard.py — render_html() thuần túy (không
I/O), dùng context giả để kiểm tra cấu trúc output (Phase 8)."""
from reporting.render_dashboard import render_html


def _fake_ctx(**overrides):
    ctx = {
        "generated_at": "2026-07-19T00:00:00+00:00",
        "portfolio_updated": "2026-07-19",
        "networth": {"parts": {"Vàng": 828.8, "Tiết kiệm ngân hàng": 246.0, "Tiền mặt": 35.0},
                     "total": 1109.8, "gold_status": "HEALTHY", "gold_src": "test"},
        "gold_estimate": None,
        "gold_decision": None,
        "deposits": [],
        "watchlist": ["VCB", "CTD"],
        "risk_limits": {},
    }
    ctx.update(overrides)
    return ctx


def test_render_html_contains_total_networth():
    html_out = render_html(_fake_ctx())
    assert "1,109.8" in html_out


def test_render_html_shows_data_quality_badge_ok():
    html_out = render_html(_fake_ctx())
    assert 'class="badge ok"' in html_out
    assert "OK" in html_out


def test_render_html_shows_bad_badge_when_gold_failed():
    html_out = render_html(_fake_ctx(networth={
        "parts": {}, "total": 0, "gold_status": "FAILED", "gold_src": ""
    }))
    assert 'class="badge bad"' in html_out


def test_render_html_escapes_html_in_watchlist():
    html_out = render_html(_fake_ctx(watchlist=["<script>alert(1)</script>"]))
    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;" in html_out


def test_render_html_shows_decision_when_present():
    decision = {"action_vi": "KHÔNG MUA THÊM", "confidence": 92, "data_quality": "GOOD",
                "risk_veto": True, "reasons": ["Vượt ngưỡng critical"]}
    html_out = render_html(_fake_ctx(gold_decision=decision))
    assert "KHÔNG MUA THÊM" in html_out
    assert "92/100" in html_out
    assert "Risk Officer đã điều chỉnh" in html_out


def test_render_html_no_decision_shows_placeholder():
    html_out = render_html(_fake_ctx())
    assert "Chưa có đủ dữ liệu để ra quyết định" in html_out


def test_render_html_is_valid_minimal_structure():
    html_out = render_html(_fake_ctx())
    assert html_out.strip().startswith("<!doctype html>")
    assert "<html" in html_out and "</html>" in html_out
