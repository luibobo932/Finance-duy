"""Test cho reporting/diff_report.py và các hàm section thuần túy trong
scripts/run_morning.py (Phase 8)."""
import sys as _sys
from pathlib import Path as _Path

_SCRIPTS = _Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS))

from reporting.diff_report import compare_decisions, compare_snapshots, format_diff_section
from run_morning import section_tai_san, section_tong_quan, section_vang


# ---- diff_report.py ----


def test_compare_snapshots_detects_change():
    prev = {"vnindex": {"close": 1787.45}, "vcb": {"close": 58500}}
    cur = {"vnindex": {"close": 1795.2}, "vcb": {"close": 58500}}
    changes = compare_snapshots(prev, cur)
    labels = [c["label"] for c in changes]
    assert "VN-Index" in labels
    assert "VCB" not in labels  # không đổi -> không liệt kê


def test_compare_snapshots_computes_delta_pct():
    prev = {"vnindex": {"close": 100.0}}
    cur = {"vnindex": {"close": 110.0}}
    changes = compare_snapshots(prev, cur)
    assert changes[0]["delta_pct"] == 10.0


def test_compare_snapshots_no_changes_returns_empty():
    snap = {"vnindex": {"close": 1787.45}, "vcb": {"close": 58500}}
    assert compare_snapshots(snap, dict(snap)) == []


def test_compare_snapshots_ignores_both_missing():
    prev = {"vnindex": {"close": 1787.45}}
    cur = {"vnindex": {"close": 1787.45}}
    assert compare_snapshots(prev, cur) == []


def test_compare_decisions_no_previous():
    result = compare_decisions(None, {"asset": "XAUUSD", "action": "HOLD", "action_vi": "GIỮ"})
    assert result["changed"] is False


def test_compare_decisions_changed_requires_reason():
    prev = {"asset": "XAUUSD", "action": "HOLD", "action_vi": "GIỮ"}
    cur = {"asset": "XAUUSD", "action": "DO_NOT_BUY_MORE", "action_vi": "KHÔNG MUA THÊM",
           "reasons": ["Vượt ngưỡng critical"]}
    result = compare_decisions(prev, cur)
    assert result["changed"] is True
    assert result["reason"] == "Vượt ngưỡng critical"


def test_compare_decisions_unchanged():
    prev = {"asset": "XAUUSD", "action": "HOLD", "action_vi": "GIỮ"}
    cur = {"asset": "XAUUSD", "action": "HOLD", "action_vi": "GIỮ"}
    assert compare_decisions(prev, cur)["changed"] is False


def test_format_diff_section_no_changes():
    text = format_diff_section([], [{"asset": "X", "changed": False}])
    assert "Không có thay đổi" in text


def test_format_diff_section_lists_changed_decision_with_reason():
    dc = {"asset": "XAUUSD", "changed": True, "before": "GIỮ", "after": "KHÔNG MUA THÊM", "reason": "Vàng vượt ngưỡng"}
    text = format_diff_section([], [dc])
    assert "KHÔNG MUA THÊM" in text
    assert "Vàng vượt ngưỡng" in text


# ---- run_morning.py section functions (thuần túy, không I/O) ----


def test_section_tong_quan_with_decision():
    text = section_tong_quan({"action_vi": "KHÔNG MUA THÊM", "confidence": 92})
    assert "KHÔNG MUA THÊM" in text
    assert "92" in text


def test_section_tong_quan_without_decision():
    text = section_tong_quan(None)
    assert "chưa đủ dữ liệu" in text.lower()


def test_section_tai_san_lists_all_nonzero_parts():
    ctx = {"parts": {"Vàng": 828.8, "Tiết kiệm ngân hàng": 246.0, "Tiền mặt": 35.0}, "total": 1109.8}
    text = section_tai_san(ctx)
    assert "828.8" in text
    assert "1,109.8" in text


def test_section_vang_none_estimate():
    text = section_vang(None, None)
    assert "Chưa có đủ dữ liệu" in text
