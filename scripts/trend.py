#!/usr/bin/env python3
"""Quản lý lịch sử số liệu bản tin đầu tư và phân tích xu hướng.

Cách dùng:
  python3 scripts/trend.py append '<json snapshot>'   # hoặc đọc từ stdin
  python3 scripts/trend.py append '<json>' --force    # bỏ qua chặn biên độ giá
  python3 scripts/trend.py report

`append` làm 3 việc trong 1 lệnh (cố ý — xem chú thích trong cmd_append):
  1. Ghi snapshot vào data/history.jsonl (chặn giá âm/bằng 0 và giá BẤT KHẢ THI
     so với kỳ trước theo biên độ sàn)
  2. Đồng bộ lãi suất sang data/normalized/deposit_rates.jsonl
  3. Chạy Decision Engine và ghi quyết định vào data/decisions.jsonl
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datacontract.schema import DataPoint  # noqa: E402
from datacontract.validators import is_abnormal  # noqa: E402

HIST = ROOT / "data" / "history.jsonl"
PORT = ROOT / "data" / "portfolio.json"

REQUIRED = ["date", "ky", "vnindex", "gold"]

# Trường giá phải > 0 nếu có mặt (path trong snapshot, nhãn hiển thị lỗi)
PRICE_FIELDS = [
    (("vnindex", "close"), "vnindex.close"),
    (("vcb", "close"), "vcb.close"),
    (("ctd", "close"), "ctd.close"),
    (("gold", "xauusd"), "gold.xauusd"),
    (("gold", "sjc_sell"), "gold.sjc_sell"),
    (("gold", "sjc_buy"), "gold.sjc_buy"),
    (("gold", "ring_sell"), "gold.ring_sell"),
    (("fx_vcb_sell",), "fx_vcb_sell"),
]


def load_history():
    if not HIST.exists():
        return []
    return [json.loads(line) for line in HIST.read_text(encoding="utf-8").splitlines() if line.strip()]


def fmt(x, nd=2):
    if x is None:
        return "n/a"
    s = f"{x:,.{nd}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def validate_snapshot(snap: dict, prev: dict | None = None) -> list[str]:
    """Trả về danh sách lỗi dữ liệu bất thường (rỗng = hợp lệ).

    Chỉ kiểm tra các trường GIÁ (phải > 0 nếu có mặt) — các trường có thể
    hợp lệ bằng 0 hoặc âm (VD foreign_net_ty, change_pct) không bị chặn ở
    đây. Đây là tuyến phòng thủ đầu tiên theo data contract: không cho số
    liệu rõ ràng sai (âm/bằng 0) lọt vào lịch sử — xem datacontract/.
    """
    errors = []
    for path, label in PRICE_FIELDS:
        v = get(snap, *path)
        if v is None:
            continue
        dp = DataPoint(name=label, value=v, unit="", source="snapshot_input")
        if is_abnormal(dp):
            errors.append(f"{label} = {v} bất thường (giá phải > 0)")
    errors.extend(validate_price_plausibility(snap, prev))
    return errors


def validate_price_plausibility(snap: dict, prev: dict | None) -> list[str]:
    """Chặn giá cổ phiếu BẤT KHẢ THI so với kỳ trước, theo biên độ sàn.

    Đây là tuyến phòng thủ ra đời từ lỗi thật: 4/6 bản tin 20–22/7 phải viết
    tay cảnh báo Simplize trả giá CTD 73.800đ trong khi giá đã xác minh là
    59.100đ (+24,9% trong 1 phiên — vượt xa biên 7% của HOSE). Việc phát hiện
    trước đây phụ thuộc vào người soạn NHỚ rằng nguồn đó không đáng tin.

    `prev` truyền TƯỜNG MINH (không tự đọc file) để hàm kiểm tra vẫn là hàm
    thuần: cùng đầu vào luôn cho cùng kết quả, không phụ thuộc trạng thái đĩa.

    So với kỳ TRƯỚC trong history (cùng đơn vị đồng), không so với data/eod/
    (đơn vị nghìn đồng) để không lẫn đơn vị.
    """
    from analytics.price_sanity import check_price

    if not prev:
        return []
    errors = []
    for ticker in ("vcb", "ctd"):
        cur_price = get(snap, ticker, "close")
        ref_price = get(prev, ticker, "close")
        if cur_price is None or ref_price is None:
            continue
        result = check_price(
            ticker.upper(), cur_price, ref_price,
            reference_date=prev.get("date"), target_date=snap.get("date"),
        )
        if not result.ok:
            errors.append(result.message)
    return errors


def cmd_append(arg, force: bool = False):
    raw = arg if arg else sys.stdin.read()
    snap = json.loads(raw)
    missing = [k for k in REQUIRED if k not in snap]
    if missing:
        sys.exit(f"LỖI: snapshot thiếu trường bắt buộc: {missing}")
    if snap["ky"] not in ("sang", "chieu"):
        sys.exit("LỖI: 'ky' phải là 'sang' hoặc 'chieu'")
    existing = load_history()
    errors = validate_snapshot(snap, existing[-1] if existing else None)
    if errors:
        from common import get_logger

        logger = get_logger("trend")
        for e in errors:
            logger.error(e)
        if not force:
            sys.exit(
                "LỖI: dữ liệu bất thường, từ chối ghi:\n"
                + "\n".join(f"  - {e}" for e in errors)
                + "\n\nNếu đây là sự kiện doanh nghiệp THẬT (chia tách, thưởng cổ phiếu, "
                  "phát hành quyền — giá tham chiếu đổi hợp lệ ngoài biên độ), chạy lại với "
                  "--force và ghi lý do vào risk_flags của snapshot."
            )
        # --force: vẫn ghi nhưng để lại dấu vết trong chính dữ liệu, không âm thầm
        snap.setdefault("risk_flags", {})["note_forced_append"] = (
            "Snapshot được ghi với --force dù vượt kiểm tra biên độ giá: "
            + " | ".join(errors)
        )
        print("⚠️  Ghi với --force, đã ghi lý do vào risk_flags.note_forced_append")
    hist = load_history()
    if any(h["date"] == snap["date"] and h["ky"] == snap["ky"] for h in hist):
        sys.exit(f"LỖI: đã có snapshot {snap['date']} kỳ {snap['ky']} — không ghi trùng")
    HIST.parent.mkdir(parents=True, exist_ok=True)
    with HIST.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snap, ensure_ascii=False) + "\n")
    print(f"Đã ghi snapshot {snap['date']} ({snap['ky']}) — tổng {len(hist) + 1} bản ghi")

    # Đổ luôn lãi suất sang kho chuẩn hoá để module deposits/ và bản tin không
    # còn nói 2 chuyện khác nhau (đã từng lệch: bản tin 22/7 vs kho 19/7).
    from deposits.sync import sync_snapshot

    added = sync_snapshot(snap)
    if added:
        print(f"Đã đồng bộ {added} mức lãi suất sang data/normalized/deposit_rates.jsonl")

    # Ghi quyết định NGAY tại đây, không chờ orchestrator. Lý do: 6 bản tin
    # 20-22/7 đều ra khuyến nghị nhưng data/decisions.jsonl chỉ có 2 bản ghi —
    # run_morning/run_evening bị bỏ qua nên Decision Engine không thấy khuyến
    # nghị thật, khiến decision review và confidence score (Phase 9) chạy trên
    # dữ liệu rỗng. Append là bước LUÔN được gọi, nên gắn vào đây thì không
    # còn đường bỏ sót.
    _log_decision_for(snap)


def _log_decision_for(snap: dict) -> None:
    """Chạy Decision Engine cho snapshot vừa ghi và lưu kết quả (bất biến).

    Lỗi ở bước này KHÔNG được làm hỏng việc ghi snapshot — snapshot là dữ liệu
    gốc, quyết định là thứ dẫn xuất và có thể tính lại sau.
    """
    try:
        from decision.decision_log import append_decision, build_entry
        from decision.policy_engine import DecisionInput, decide
        from decision.risk_officer import RiskContext
        from gold.indicators import analyze as gold_analyze
        from gold.indicators import trend_label as gold_trend_label
        from portfolio.loader import load_decision_rules, load_risk_limits

        sys.path.insert(0, str(ROOT / "scripts"))
        from networth import compute as compute_networth

        _port, _lim, _meta, parts, total, _price, _src = compute_networth()
        if not total:
            print("Chưa ghi được quyết định: chưa định giá được danh mục.")
            return
        gold_pct = (parts.get("Vàng") or 0) / total
        decision = decide(
            DecisionInput(asset="Vàng nhẫn", asset_class="gold",
                          trend_label=gold_trend_label(gold_analyze())),
            RiskContext(gold_allocation_pct=gold_pct),
            load_risk_limits(), load_decision_rules(),
        )
        if append_decision(build_entry(decision, asset_class="gold", ky=snap["ky"], snapshot=snap)):
            veto = " (Risk Officer đã điều chỉnh)" if decision["risk_veto"] else ""
            print(f"Quyết định đã ghi: vàng → {decision['action_vi']} "
                  f"({decision['confidence']}/100){veto}")
        else:
            print("Quyết định kỳ này đã có trong data/decisions.jsonl — không ghi trùng.")
    except Exception as exc:  # noqa: BLE001 — không để lỗi dẫn xuất phá dữ liệu gốc
        from common import get_logger

        get_logger("trend").error("khong ghi duoc quyet dinh: %s", exc)
        print(f"⚠️  Snapshot đã ghi nhưng CHƯA ghi được quyết định: {exc}")


def delta_line(name, cur, prev, unit=""):
    if cur is None:
        return f"- {name}: chưa có số liệu kỳ này"
    if prev is None:
        return f"- {name}: {fmt(cur)}{unit} (chưa có kỳ trước để so)"
    d = cur - prev
    arrow = "▲" if d > 0 else ("▼" if d < 0 else "=")
    pct = f" ({d / prev * 100:+.2f}%)" if prev else ""
    return f"- {name}: {fmt(cur)}{unit} {arrow} {fmt(abs(d))}{unit} so với kỳ trước{pct}"


def get(snap, *path):
    cur = snap
    for p in path:
        if not isinstance(cur, dict) or p not in cur or cur[p] is None:
            return None
        cur = cur[p]
    return cur


def cmd_report():
    hist = load_history()
    if not hist:
        sys.exit("Chưa có lịch sử — chạy append trước.")
    cur = hist[-1]
    prev = hist[-2] if len(hist) > 1 else None
    print(f"=== XU HƯỚNG (kỳ hiện tại: {cur['date']} {cur['ky']}, {len(hist)} bản ghi) ===\n")

    print("## So với bản tin trước")
    for name, path, unit in [
        ("VN-Index", ("vnindex", "close"), ""),
        ("VCB", ("vcb", "close"), " đ"),
        ("CTD", ("ctd", "close"), " đ"),
        ("Vàng SJC bán ra", ("gold", "sjc_sell"), " tr"),
        ("Vàng thế giới", ("gold", "xauusd"), " $"),
        ("Chênh lệch vàng VN–TG", ("gold", "premium_trieu"), " tr"),
    ]:
        print(delta_line(name, get(cur, *path), get(prev, *path) if prev else None, unit))

    # Khối lượng đột biến: so KLGD kỳ này với bình quân các phiên chiều trước đó (tối đa 20)
    for ticker in ("vcb", "ctd"):
        vol = get(cur, ticker, "volume")
        past = [get(h, ticker, "volume") for h in hist[:-1] if h["ky"] == "chieu"]
        past = [v for v in past if v is not None][-20:]
        if vol is None:
            continue
        if not past:
            print(f"- KLGD {ticker.upper()}: {fmt(vol)} triệu cp (chưa đủ lịch sử tính bình quân)")
            continue
        avg = sum(past) / len(past)
        ratio = vol / avg if avg else 0
        flag = " ⚠️ ĐỘT BIẾN — kiểm tra tin tức, thỏa thuận, giao dịch nội bộ" if ratio >= 1.5 else ""
        print(f"- KLGD {ticker.upper()}: {fmt(vol)} triệu cp = {ratio:.1f}× bình quân {len(past)} phiên{flag}")

    # Chuỗi khối ngoại: chỉ tính trên các kỳ "chieu" (số chốt phiên) để không đếm trùng
    flows = [(h["date"], h.get("foreign_net_ty")) for h in hist
             if h["ky"] == "chieu" and h.get("foreign_net_ty") is not None]
    if flows:
        sign = 1 if flows[-1][1] > 0 else -1
        streak = 0
        total = 0.0
        for _, v in reversed(flows):
            if v * sign > 0:
                streak += 1
                total += v
            else:
                break
        kind = "MUA ròng" if sign > 0 else "BÁN ròng"
        print(f"- Khối ngoại: {kind} {streak} phiên liên tiếp, lũy kế {fmt(abs(total), 0)} tỷ đồng")

    # Thay đổi lãi suất so với kỳ trước
    if prev:
        prev_rates = {(d["bank"], d["term_months"]): d["rate_pct"] for d in prev.get("deposit_top", [])}
        changes = []
        for d in cur.get("deposit_top", []):
            key = (d["bank"], d["term_months"])
            if key in prev_rates and prev_rates[key] != d["rate_pct"]:
                changes.append(f"{d['bank']} ({d['term_months']}T): {prev_rates[key]}% → {d['rate_pct']}%")
            elif key not in prev_rates:
                changes.append(f"{d['bank']} ({d['term_months']}T): mới vào top với {d['rate_pct']}%")
        print("- Lãi suất thay đổi: " + ("; ".join(changes) if changes else "không đổi so với kỳ trước"))

    # Lãi/lỗ danh mục
    print("\n## Lãi/lỗ danh mục")
    if PORT.exists():
        port = json.loads(PORT.read_text(encoding="utf-8"))
        total_pnl = 0.0
        have_any = False
        for ticker, pos in port.items():
            cost, qty = pos.get("avg_cost"), pos.get("quantity")
            price = get(cur, ticker.lower(), "close")
            if cost is None or qty is None:
                print(f"- {ticker}: chưa có giá vốn/số lượng trong data/portfolio.json")
                continue
            if price is None:
                print(f"- {ticker}: chưa có giá kỳ này để tính")
                continue
            pnl = (price - cost) * qty
            total_pnl += pnl
            have_any = True
            print(f"- {ticker}: giá {fmt(price, 0)} đ vs vốn {fmt(cost, 0)} đ × {fmt(qty, 0)} cp → "
                  f"{'LÃI' if pnl >= 0 else 'LỖ'} {fmt(abs(pnl), 0)} đ ({(price - cost) / cost * 100:+.2f}%)")
        if have_any:
            print(f"- TỔNG: {'LÃI' if total_pnl >= 0 else 'LỖ'} {fmt(abs(total_pnl), 0)} đ")
    else:
        print("- Chưa có data/portfolio.json")

    # Cờ rủi ro kỳ này
    flags = cur.get("risk_flags", {})
    if flags.get("arrest"):
        print(f"\n⚠️ CẢNH BÁO: {flags['arrest']}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("append", "report"):
        sys.exit(__doc__)
    if sys.argv[1] == "append":
        args = [a for a in sys.argv[2:] if a != "--force"]
        cmd_append(args[0] if args else None, force="--force" in sys.argv[2:])
    else:
        cmd_report()


if __name__ == "__main__":
    main()
