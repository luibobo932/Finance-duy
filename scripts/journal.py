#!/usr/bin/env python3
"""Nhật ký giao dịch — ghi lệnh mua/bán của bạn, đối chiếu khuyến nghị, tổng kết win-rate.

Cách dùng:
  python3 scripts/journal.py add BUY VCB 58.5 1000 --note "mua theo hỗ trợ" --rec HOLD
  python3 scripts/journal.py add SELL VCB 61.0 1000
  python3 scripts/journal.py report          # tổng kết lãi/lỗ đã chốt + đối chiếu khuyến nghị
Ghi vào data/journal.jsonl. Giá đơn vị nghìn đồng, khớp cặp BUY→SELL theo FIFO từng mã.
"""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOURNAL = ROOT / "data" / "journal.jsonl"


def load():
    if not JOURNAL.exists():
        return []
    return [json.loads(l) for l in JOURNAL.read_text(encoding="utf-8").splitlines() if l.strip()]


def cmd_add(args):
    side = args[0].upper()
    if side not in ("BUY", "SELL"):
        sys.exit("Lệnh phải là BUY hoặc SELL")
    try:
        price, qty = float(args[2]), float(args[3])
    except (ValueError, IndexError):
        sys.exit("Giá và khối lượng phải là số. VD: journal.py add BUY VCB 58.5 1000")
    # Chặn tại CỬA VÀO. Một lệnh qty=0 lọt vào file sẽ làm `report` sập bằng
    # ZeroDivisionError ở dòng tính giá vốn trung bình (docs/AUDIT_REPORT.md
    # mục L8) — và lúc đó cuốn nhật ký đã hỏng, sửa phải mở file ra tay.
    if price <= 0:
        sys.exit(f"Giá phải > 0 (đang nhận {price}). Đơn vị nghìn đồng, VD 58.5")
    if qty <= 0:
        sys.exit(f"Khối lượng phải > 0 (đang nhận {qty}). Đơn vị: cổ phiếu")
    entry = {"date": str(date.today()), "side": side, "ticker": args[1].upper(),
             "price": price, "qty": qty, "note": "", "rec": ""}
    if "--note" in args:
        entry["note"] = args[args.index("--note") + 1]
    if "--rec" in args:
        entry["rec"] = args[args.index("--rec") + 1]
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"Đã ghi: {side} {entry['ticker']} {entry['price']} × {entry['qty']}")


def cmd_report():
    rows = load()
    if not rows:
        print("Nhật ký trống. Ghi lệnh bằng: journal.py add BUY VCB 58.5 1000")
        return
    from collections import defaultdict, deque
    lots = defaultdict(deque)
    realized = 0.0
    wins = losses = 0
    print("=== GIAO DỊCH ĐÃ CHỐT ===")
    for r in rows:
        t = r["ticker"]
        if r["side"] == "BUY":
            lots[t].append([r["price"], r["qty"]])
        else:
            qty = r["qty"]
            while qty > 0 and lots[t]:
                bp, bq = lots[t][0]
                m = min(qty, bq)
                pnl = (r["price"] - bp) * m * 1000
                realized += pnl
                wins += pnl > 0
                losses += pnl < 0
                print(f"  {t}: mua {bp} → bán {r['price']} × {m:.0f}cp = "
                      f"{'LÃI' if pnl >= 0 else 'LỖ'} {abs(pnl):,.0f} đ")
                bq -= m
                qty -= m
                if bq == 0:
                    lots[t].popleft()
                else:
                    lots[t][0][1] = bq
    print(f"\nTổng đã chốt: {'LÃI' if realized >= 0 else 'LỖ'} {abs(realized):,.0f} đ")
    total = wins + losses
    if total:
        print(f"Win-rate: {wins}/{total} = {wins/total*100:.0f}%")
    # Đối chiếu khuyến nghị — bằng ENUM, không dò chuỗi tiếng Việt.
    # Logic cũ dò chuỗi con: bỏ sót MỌI lệnh mua sai, và gắn cờ oan cho lệnh
    # bán sau khuyến nghị "KHÔNG MUA THÊM" (vì chuỗi đó chứa "MUA").
    # Xem decision/discipline.py để có bảng đối chiếu đầy đủ 9 hành động.
    from decision.discipline import AGAINST, NO_BASIS, UNKNOWN, classify, explain

    buckets = {AGAINST: [], NO_BASIS: [], UNKNOWN: []}
    for r in rows:
        if not r.get("rec"):
            continue
        v = classify(r["side"], r["rec"])
        if v in buckets:
            buckets[v].append(r)

    def _show(rows_, title):
        if not rows_:
            return
        print(f"\n{title}")
        for r in rows_:
            print(f"  {r['date']} {r['ticker']}: {explain(r['side'], r['rec'])}")

    _show(buckets[AGAINST],
          f"⚠️ {len(buckets[AGAINST])} lệnh ĐI NGƯỢC khuyến nghị hệ thống — xem lại kỷ luật:")
    _show(buckets[NO_BASIS],
          f"ℹ️ {len(buckets[NO_BASIS])} lệnh vào lúc hệ thống CHƯA RA ĐƯỢC khuyến nghị "
          "(không phải vô kỷ luật, nhưng cũng không có gì chống lưng):")
    _show(buckets[UNKNOWN],
          f"❓ {len(buckets[UNKNOWN])} lệnh có khuyến nghị KHÔNG ĐỌC ĐƯỢC — ghi bằng nhãn "
          "chuẩn (VD MUA THĂM DÒ) để đối chiếu được:")
    # Vị thế còn mở
    open_pos = {t: sum(q for _, q in dq) for t, dq in lots.items() if dq}
    if open_pos:
        print("\nVị thế đang mở:")
        for t, q in open_pos.items():
            # Guard cho dữ liệu cũ đã lỡ ghi trước khi có validate ở cmd_add:
            # tổng khối lượng 0 thì không có giá vốn trung bình để nói, và
            # chia cho 0 làm sập cả báo cáo vì đúng một dòng hỏng.
            if q <= 0:
                print(f"  {t}: khối lượng ghi nhận {q:.0f} — dòng nhật ký hỏng, "
                      "không tính được giá vốn TB (sửa data/journal.jsonl)")
                continue
            avg = sum(p * qn for p, qn in lots[t]) / q
            print(f"  {t}: {q:.0f}cp, giá vốn TB {avg:.2f}")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "add":
        cmd_add(sys.argv[2:])
    elif sys.argv[1] == "report":
        cmd_report()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
