"""Nạp config/*.yaml thành dữ liệu Python có kiểu.

Không có số tài sản/rủi ro nào được viết chết trong file .py — mọi giá trị
đọc từ YAML tại đây. Sửa danh mục/hạn mức rủi ro = sửa YAML, không sửa code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Thiếu file cấu hình: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


@dataclass
class StockPosition:
    ticker: str
    quantity: float = 0.0
    avg_cost_vnd: Optional[float] = None
    last_price_vnd: Optional[float] = None

    @property
    def market_value_vnd(self) -> float:
        return (self.last_price_vnd or 0) * self.quantity

    @property
    def unrealized_pnl_vnd(self) -> Optional[float]:
        if self.avg_cost_vnd is None or self.last_price_vnd is None:
            return None
        return (self.last_price_vnd - self.avg_cost_vnd) * self.quantity


@dataclass
class PortfolioConfig:
    currency: str
    updated: str
    gold_quantity_tael: float
    savings_principal_vnd: float
    cash_amount_vnd: float
    # Khối `savings` thô, giữ nguyên để deposits/holding.py đọc thêm lãi
    # suất/kỳ hạn/ngày gửi mà không phải nạp lại YAML lần hai.
    savings_raw: dict[str, Any] = field(default_factory=dict)
    stock_positions: list[StockPosition] = field(default_factory=list)
    watchlist: list[str] = field(default_factory=list)

    @property
    def stock_market_value_vnd(self) -> float:
        return sum(p.market_value_vnd for p in self.stock_positions)


def load_portfolio(path: Optional[Path] = None) -> PortfolioConfig:
    path = path or (CONFIG_DIR / "portfolio.yaml")
    raw = _load_yaml(path)
    assets = raw.get("assets", {}) or {}
    gold = assets.get("gold_ring", {}) or {}
    savings = assets.get("savings", {}) or {}
    cash = assets.get("cash", {}) or {}
    stocks_cfg = assets.get("stocks", {}) or {}
    positions_raw = stocks_cfg.get("positions", []) or []
    positions = [
        StockPosition(
            ticker=s["ticker"],
            quantity=s.get("quantity", 0),
            avg_cost_vnd=s.get("avg_cost_vnd"),
            last_price_vnd=s.get("last_price_vnd"),
        )
        for s in positions_raw
    ]
    return PortfolioConfig(
        currency=raw.get("currency", "VND"),
        updated=raw.get("updated", ""),
        gold_quantity_tael=gold.get("quantity_tael", 0.0),
        savings_principal_vnd=savings.get("principal_vnd", 0.0),
        cash_amount_vnd=cash.get("amount_vnd", 0.0),
        savings_raw=savings,
        stock_positions=positions,
        watchlist=raw.get("watchlist", []) or [],
    )


def load_risk_limits(path: Optional[Path] = None) -> dict[str, Any]:
    path = path or (CONFIG_DIR / "risk_limits.yaml")
    return _load_yaml(path).get("allocation_limits", {})


def load_source_priority(path: Optional[Path] = None) -> dict[str, Any]:
    """Trả {"blocked_sources": [...], "priority": {data_type: [nguồn...]}}."""
    path = path or (CONFIG_DIR / "source_priority.yaml")
    return _load_yaml(path)


def load_decision_rules(path: Optional[Path] = None) -> dict[str, Any]:
    path = path or (CONFIG_DIR / "decision_rules.yaml")
    return _load_yaml(path)
