"""Nhật ký GIAO DỊCH — vòng lặp còn hở giữa "khuyến nghị" và "vị thế".

Hệ thống vừa nói được "MUA CTD tối đa 83 tr". Thử làm đúng theo lời khuyên đó
rồi xem chuyện gì xảy ra:

    Tổng tài sản trước khi mua               1.172,7 tr
    Thêm vị thế 83 tr vào config/portfolio   1.255,7 tr   ← TĂNG 83 tr

Tài sản ròng **tự nhiên nhiều thêm 83 triệu**. Tiền mua phải lấy từ đâu đó —
bán vàng hoặc rút tiền mặt — nhưng `config/portfolio.yaml` chỉ mô tả *đang
nắm gì*, không mô tả *đã đổi gì lấy gì*. Khai thêm một vị thế mà quên giảm
nguồn tiền là danh mục phồng lên trên giấy, và mọi con số phía sau (tỷ trọng
vàng, biên an toàn, tiến độ tới 10 tỷ) đều lệch theo.

Đây cũng là chỗ trả lời câu đã hỏi mà chưa có: **giá vốn**. Giá vốn không phải
một con số cần nhớ, nó là kết quả cộng dồn của các giao dịch.

Nguyên tắc: module này KHÔNG tự sửa `config/portfolio.yaml`. Nó đối chiếu và
**báo lệch**, để việc sửa danh mục luôn là hành động có ý thức của chủ danh
mục — cùng lý do mà `--force` của `trend.py append` phải ghi lại dấu vết.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent
TRANSACTIONS_PATH = ROOT / "data" / "transactions.jsonl"

BUY, SELL = "MUA", "BAN"
# Nguồn tiền hợp lệ. Bắt khai nguồn là cố ý: một giao dịch mua không có nguồn
# tiền là một giao dịch chưa xảy ra.
FUNDING_SOURCES = {"tien_mat", "tiet_kiem", "ban_vang", "ban_co_phieu"}


@dataclass
class Transaction:
    date: date
    asset: str            # mã cổ phiếu, hoặc "VANG"
    side: str             # MUA | BAN
    quantity: float       # số cổ phiếu, hoặc số chỉ vàng
    price: float          # nghìn đồng/cp, hoặc triệu đồng/lượng
    amount_trieu: float   # tiền thực trả/thực nhận, đã gồm phí
    funded_from: Optional[str] = None  # bắt buộc với MUA
    fee_trieu: float = 0.0
    note: str = ""

    @property
    def is_buy(self) -> bool:
        return self.side == BUY

    def signed_quantity(self) -> float:
        return self.quantity if self.is_buy else -self.quantity


@dataclass
class Holding:
    """Vị thế suy ra TỪ giao dịch — không phải từ khai báo."""

    asset: str
    quantity: float
    cost_basis_trieu: float  # tổng tiền đã bỏ ra cho phần đang còn nắm

    @property
    def avg_cost(self) -> Optional[float]:
        """Giá vốn bình quân, cùng đơn vị với `price` của giao dịch."""
        return self.cost_basis_trieu * 1000 / self.quantity if self.quantity else None


def load_transactions(path: Optional[Path] = None) -> list[Transaction]:
    p = path or TRANSACTIONS_PATH
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        out.append(Transaction(
            date=_parse(d.get("date")) or date.min,
            asset=str(d["asset"]).upper(),
            side=str(d.get("side") or BUY).upper(),
            quantity=float(d.get("quantity") or 0),
            price=float(d.get("price") or 0),
            amount_trieu=float(d.get("amount_trieu") or 0),
            funded_from=d.get("funded_from"),
            fee_trieu=float(d.get("fee_trieu") or 0),
            note=str(d.get("note") or ""),
        ))
    return sorted(out, key=lambda t: t.date)


def validate(tx: Transaction) -> list[str]:
    """Lỗi khiến một giao dịch KHÔNG được ghi. Rỗng = hợp lệ."""
    errors = []
    if tx.side not in (BUY, SELL):
        errors.append(f"side phải là {BUY} hoặc {SELL}, nhận '{tx.side}'")
    if tx.quantity <= 0:
        errors.append("quantity phải > 0")
    if tx.price <= 0:
        errors.append("price phải > 0")
    if tx.amount_trieu <= 0:
        errors.append("amount_trieu phải > 0")
    # Nguồn tiền chỉ bắt buộc với MUA: bán thì tiền ĐI RA khỏi tài sản đó, vào
    # đâu là chuyện của giao dịch kế tiếp.
    if tx.is_buy and tx.funded_from not in FUNDING_SOURCES:
        errors.append(f"MUA phải khai funded_from thuộc {sorted(FUNDING_SOURCES)} — "
                      "một giao dịch mua không có nguồn tiền là giao dịch chưa xảy ra")
    return errors


def holdings_from(transactions: Sequence[Transaction]) -> dict[str, Holding]:
    """Vị thế và GIÁ VỐN suy ra từ lịch sử giao dịch.

    Bán làm giảm giá vốn theo TỶ LỆ phần đã bán (bình quân gia quyền), không
    theo giá bán — dùng giá bán sẽ khiến giá vốn phần còn lại nhảy lung tung
    theo thị trường, trong khi giá vốn là chi phí đã bỏ ra, không phải thị giá.
    """
    out: dict[str, Holding] = {}
    for tx in transactions:
        h = out.setdefault(tx.asset, Holding(tx.asset, 0.0, 0.0))
        if tx.is_buy:
            h.quantity += tx.quantity
            h.cost_basis_trieu += tx.amount_trieu
        else:
            if h.quantity <= 0:
                continue  # bán thứ không nắm — bắt ở validate_history
            sold_ratio = min(1.0, tx.quantity / h.quantity)
            h.cost_basis_trieu *= (1 - sold_ratio)
            h.quantity -= tx.quantity
    return {k: v for k, v in out.items() if abs(v.quantity) > 1e-9}


def validate_history(transactions: Sequence[Transaction]) -> list[str]:
    """Lỗi trên toàn bộ lịch sử: bán nhiều hơn đang nắm, số âm..."""
    errors, running = [], {}
    for tx in transactions:
        q = running.get(tx.asset, 0.0)
        q += tx.signed_quantity()
        if q < -1e-9:
            errors.append(f"{tx.date} {tx.asset}: bán {tx.quantity:g} nhưng chỉ đang nắm "
                          f"{q + tx.quantity:g} — lịch sử giao dịch không nhất quán")
            q = 0.0
        running[tx.asset] = q
    return errors


def reconcile(declared_positions: Sequence, transactions: Sequence[Transaction]) -> list[str]:
    """Đối chiếu vị thế KHAI BÁO trong config với vị thế SUY RA từ giao dịch.

    Không tự sửa config — chỉ báo lệch. Việc sửa danh mục phải là hành động có
    ý thức của chủ danh mục, cùng lý do mà `--force` của `trend.py append`
    buộc ghi lại dấu vết thay vì âm thầm bỏ qua kiểm tra.
    """
    derived = holdings_from(transactions)
    issues = []
    declared = {p.ticker.upper(): p for p in declared_positions if getattr(p, "quantity", 0)}

    for ticker, pos in declared.items():
        h = derived.get(ticker)
        if h is None:
            issues.append(
                f"{ticker}: khai {pos.quantity:g} cp trong config/portfolio.yaml nhưng "
                "KHÔNG có giao dịch mua nào trong data/transactions.jsonl — "
                "chưa truy được nguồn tiền, và tài sản ròng có thể đang bị thổi phồng"
            )
        elif abs(h.quantity - pos.quantity) > 1e-6:
            issues.append(f"{ticker}: config khai {pos.quantity:g} cp, giao dịch cộng lại ra "
                          f"{h.quantity:g} cp — lệch {pos.quantity - h.quantity:+g}")
    for ticker, h in derived.items():
        if ticker not in declared and ticker != "VANG":
            issues.append(f"{ticker}: giao dịch cho thấy đang nắm {h.quantity:g} cp nhưng "
                          "config/portfolio.yaml không khai vị thế nào")
    return issues


def append(tx: Transaction, path: Optional[Path] = None) -> None:
    """Ghi 1 giao dịch. Từ chối ghi khi không hợp lệ — dữ liệu gốc phải sạch."""
    errors = validate(tx)
    if errors:
        raise ValueError("Giao dịch không hợp lệ:\n" + "\n".join(f"  - {e}" for e in errors))
    p = path or TRANSACTIONS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "date": tx.date.isoformat(), "asset": tx.asset, "side": tx.side,
            "quantity": tx.quantity, "price": tx.price, "amount_trieu": tx.amount_trieu,
            "funded_from": tx.funded_from, "fee_trieu": tx.fee_trieu, "note": tx.note,
        }, ensure_ascii=False) + "\n")


def _parse(value: object) -> Optional[date]:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None
