"""Registry thứ tự ưu tiên nguồn dữ liệu.

Phase 2 định nghĩa danh sách mặc định ngay trong code (để module này tự
đứng được, không phụ thuộc Phase 3). Từ Phase 3, `config/source_priority.yaml`
sẽ được nạp và override `DEFAULT_PRIORITY` qua `load_priority_overrides()`.
"""
from __future__ import annotations

from typing import Optional

# Nguồn nào hiện KHÔNG khả dụng trong môi trường này (network policy chặn) —
# đánh dấu tường minh để hệ thống không thử-rồi-timeout mỗi lần, và để
# Risk Officer biết mà không kỳ vọng API cho nhóm này.
BLOCKED_SOURCES = {
    "hose_api",  # api.hsx.vn — CONNECT tunnel failed 403 (xác nhận 2026-07-19)
    "entrade_api",  # services.entrade.com.vn — CONNECT tunnel failed 403
}

# Thứ tự ưu tiên mặc định cho từng loại dữ liệu. Nguồn đầu danh sách được
# thử trước; nếu FAILED/STALE/CONFLICTING thì rơi xuống nguồn kế tiếp.
DEFAULT_PRIORITY: dict[str, list[str]] = {
    "gold_xauusd": ["web_search_summary"],
    "gold_shop_xuan_trieu": ["user_photo_calibration", "derived_from_xauusd"],
    "fx_usdvnd": ["web_search_summary"],
    "vn_index": ["hose_api", "web_search_summary"],
    "equity_price": ["hose_api", "web_search_summary"],
    "deposit_rate": ["bank_official_site", "web_search_summary"],
    "corporate_governance_news": ["hose_disclosure", "web_search_summary"],
}


def _load_config_overrides() -> tuple[set, dict[str, list[str]]]:
    """Đọc config/source_priority.yaml (Phase 3) nếu có; fallback về mặc định
    hard-code trong module này nếu chưa nạp được (VD chưa cài PyYAML, hoặc
    gọi từ ngữ cảnh không có `portfolio` package trên sys.path)."""
    try:
        from portfolio.loader import load_source_priority

        cfg = load_source_priority()
        blocked = set(cfg.get("blocked_sources") or []) or set(BLOCKED_SOURCES)
        priority = cfg.get("priority") or DEFAULT_PRIORITY
        return blocked, priority
    except Exception:
        return set(BLOCKED_SOURCES), DEFAULT_PRIORITY


def priority_for(
    data_type: str, overrides: Optional[dict[str, list[str]]] = None, use_config: bool = True
) -> list[str]:
    """Trả danh sách nguồn ưu tiên cho 1 loại dữ liệu, đã lọc bỏ nguồn bị chặn.

    Thứ tự ưu tiên: `overrides` truyền tay > `config/source_priority.yaml`
    (khi `use_config=True`, mặc định) > bảng mặc định hard-code trong module.
    """
    if overrides is not None:
        blocked, table = set(BLOCKED_SOURCES), overrides
    elif use_config:
        blocked, table = _load_config_overrides()
    else:
        blocked, table = set(BLOCKED_SOURCES), DEFAULT_PRIORITY
    chain = table.get(data_type, DEFAULT_PRIORITY.get(data_type, ["web_search_summary"]))
    return [s for s in chain if s not in blocked]


def is_blocked(source_name: str) -> bool:
    return source_name in BLOCKED_SOURCES
