#!/usr/bin/env python3
"""Tầng kế hoạch — sức mua, chứ không phải số dư.

    python3 scripts/plan.py           # bảng đầy đủ
    python3 scripts/plan.py --json    # để nhúng bản tin/dashboard

Trả lời ba câu mà hệ thống chưa từng trả lời:
  1. Tài sản đang tăng hay đang teo lại SAU LẠM PHÁT?
  2. Phần nào của danh mục đang bào mòn sức mua, mất bao nhiêu tiền mỗi năm?
  3. Với mục tiêu đã đặt, tài sản hiện có đòi lợi suất bao nhiêu mới tới đích?
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from planning.feasibility import (  # noqa: E402
    GoalReality, best_lever, horizon_table,
)
from planning.plan import (  # noqa: E402
    check_goal, emergency_fund_months, load_plan, sensitivity,
)
from planning.real_return import (  # noqa: E402
    RealReturn, doubling_years, erosion_trieu, nominal_needed_for,
    portfolio_real_return, purchasing_power_trieu,
)


def best_deposit_rate() -> float | None:
    try:
        from deposits.ranking import load_normalized, rank

        ranked = rank(load_normalized())
        return ranked[0]["rate_pct"] if ranked else None
    except Exception:  # noqa: BLE001
        return None


def build() -> dict:
    from deposits.holding import from_portfolio
    from networth import compute
    from portfolio.loader import load_portfolio

    plan = load_plan()
    port = load_portfolio()
    _p, _l, _m, parts, total, _pr, _s = compute()
    holding = from_portfolio(port, deposit_cfg=port.savings_raw)
    best = best_deposit_rate()

    # Lợi suất danh nghĩa của từng phần. Chỉ điền khi BIẾT THẬT:
    #   - tiền mặt 0% là sự thật, không phải giả định
    #   - tiết kiệm: lãi suất đã khai; chưa khai thì None (không lấy mức tốt
    #     nhất thị trường làm thay — đó là mức CÓ THỂ đạt, không phải mức đang có)
    #   - vàng: không có lợi suất nội tại, phụ thuộc giá => giả định của chủ danh mục
    gold_trieu = parts.get("Vàng") or 0.0
    savings_trieu = parts.get("Tiết kiệm ngân hàng") or 0.0
    cash_trieu = parts.get("Tiền mặt") or 0.0

    holdings = [
        ("Vàng", gold_trieu, plan.expected_for("gold")),
        ("Tiết kiệm", savings_trieu, holding.rate_pct),
        ("Tiền mặt", cash_trieu, plan.expected_for("cash")),
    ]
    pf = portfolio_real_return(holdings, plan.inflation_pct)

    cash_row = RealReturn("Tiền mặt", plan.expected_for("cash") or 0.0,
                          plan.inflation_pct, cash_trieu)
    out = {
        "inflation": {
            "pct": plan.inflation_pct, "source": plan.inflation_source,
            "as_of": plan.inflation_as_of,
        },
        "total_trieu": total,
        "rows": [
            {"label": r.label, "nominal_pct": r.nominal_pct, "real_pct": r.real_pct,
             "amount_trieu": r.amount_trieu, "real_change_trieu": r.real_change_trieu,
             "verdict": r.verdict}
            for r in pf["rows"]
        ],
        "unknown": [{"label": n, "amount_trieu": v} for n, v in pf["unknown"]],
        "known_weight_pct": pf["known_weight_pct"],
        "portfolio_real_pct": pf["real_pct"],
        "cash_erosion_trieu_per_year": erosion_trieu(cash_trieu, plan.inflation_pct),
        "cash_real_pct": cash_row.real_pct,
        "best_deposit_rate_pct": best,
        "best_deposit_real_pct": (
            ((1 + best / 100) / (1 + plan.inflation_pct / 100) - 1) * 100 if best else None),
        "nominal_needed_for_2pct_real": nominal_needed_for(2.0, plan.inflation_pct),
        "emergency_fund_months": emergency_fund_months(cash_trieu, plan.monthly_expense_vnd),
        "goals": [],
        "sensitivity_10y": sensitivity(total, plan.inflation_pct, 10),
        "purchasing_power_10y_trieu": purchasing_power_trieu(total, plan.inflation_pct, 10),
    }
    for g in plan.goals:
        c = check_goal(g, total, plan, date.today().year)
        item = {
            "name": c.goal.name, "years": c.years, "has_deadline": g.has_deadline,
            "basis": g.basis,
            "target_today_trieu": c.target_today_trieu,
            "target_nominal_trieu": c.target_nominal_trieu,
            "required_nominal_pct": c.required_nominal_pct,
            "required_real_pct": c.required_real_pct,
            "note": c.reachable_note,
        }
        # Chưa chốt thời hạn thì câu trả lời KHÔNG phải một con số lợi suất mà
        # là bảng "cần gì ở từng thời hạn" — chính bảng đó giúp chọn thời hạn.
        rows = horizon_table(total, g.target_vnd / 1_000_000, plan.inflation_pct,
                             risk_free_pct=best)
        item["horizons"] = [
            {"years": r.years, "required_return_pct": r.required_return_pct,
             "required_real_return_pct": r.required_real_return_pct,
             "required_monthly_trieu": r.required_monthly_trieu,
             "value_from_current_trieu": r.value_from_current_trieu,
             "band": r.band, "band_label": r.band_label}
            for r in rows
        ]
        item["best_lever"] = best_lever(rows)
        item["reality_20y"] = GoalReality(g.target_vnd / 1_000_000, 20, plan.inflation_pct).note
        out["goals"].append(item)
    return out


def main() -> None:
    d = build()
    if "--json" in sys.argv[1:]:
        print(json.dumps(d, ensure_ascii=False, default=str))
        return

    i = d["inflation"]
    print(f"=== SỨC MUA, KHÔNG PHẢI SỐ DƯ — lạm phát {_vi(i['pct'], 2)}%/năm ===")
    print(f"    {i['source']} (số liệu tới {i['as_of']})\n")

    print(f"{'Khoản':<14}{'Giá trị':>12}{'Danh nghĩa':>13}{'THỰC':>10}   Nhận định")
    for r in d["rows"]:
        print(f"{r['label']:<14}{_vi(r['amount_trieu'], 1) + ' tr':>12}"
              f"{_vi(r['nominal_pct'], 2) + '%':>13}"
              f"{_vi(r['real_pct'], 2) + '%':>10}   {r['verdict']}")
    for u in d["unknown"]:
        print(f"{u['label']:<14}{_vi(u['amount_trieu'], 1) + ' tr':>12}"
              f"{'chưa khai báo lợi suất kỳ vọng':>34}")

    print(f"\nTiền mặt đang bào mòn: **{_vi(d['cash_erosion_trieu_per_year'], 2)} tr/năm** "
          f"sức mua (thực {_vi(d['cash_real_pct'], 2)}%/năm)")
    if d["best_deposit_rate_pct"]:
        print(f"Mức gửi tốt nhất đo được {_vi(d['best_deposit_rate_pct'], 2)}%/năm "
              f"→ THỰC {_vi(d['best_deposit_real_pct'], 2)}%/năm"
              + (f" · gấp đôi sức mua sau {doubling_years(d['best_deposit_real_pct']):.0f} năm"
                 if d["best_deposit_real_pct"] and d["best_deposit_real_pct"] > 0 else ""))
    print(f"Muốn sức mua tăng thật 2%/năm thì phải tìm mức "
          f"{_vi(d['nominal_needed_for_2pct_real'], 2)}%/năm danh nghĩa.")

    if d["portfolio_real_pct"] is not None:
        print(f"\nLợi suất thực bình quân phần ĐO ĐƯỢC "
              f"({_vi(d['known_weight_pct'], 0)}% danh mục): "
              f"{_vi(d['portfolio_real_pct'], 2)}%/năm")
    if d["unknown"]:
        names = ", ".join(f"{u['label']} ({_vi(u['amount_trieu'], 0)} tr)" for u in d["unknown"])
        print(f"Chưa đo được: {names} — chiếm "
              f"{_vi(100 - d['known_weight_pct'], 0)}% danh mục.")

    m = d["emergency_fund_months"]
    print("\nQuỹ khẩn cấp: " + (f"{_vi(m, 1)} tháng chi tiêu" if m is not None else
          "chưa tính được — chưa khai chi tiêu hàng tháng trong config/plan.yaml"))

    print(f"\n=== NẾU KHÔNG LÀM GÌ, 10 NĂM NỮA ===")
    print(f"Để yên {_vi(d['total_trieu'], 0)} tr không sinh lời: còn "
          f"{_vi(d['purchasing_power_10y_trieu'], 0)} tr theo sức mua hôm nay.\n")
    print(f"{'Lợi suất':>10}{'Danh nghĩa':>14}{'Sức mua hôm nay':>18}")
    for rate, nom, real in d["sensitivity_10y"]:
        print(f"{_vi(rate, 1) + '%':>10}{_vi(nom, 0) + ' tr':>14}{_vi(real, 0) + ' tr':>18}")
    print("\n(Bảng độ nhạy, KHÔNG phải dự báo — hệ thống không dự báo lợi suất. "
          "Khai giả định của anh vào config/plan.yaml để thu về một dòng.)")

    if d["goals"]:
        for g in d["goals"]:
            print(f"\n=== MỤC TIÊU: {g['name'].upper()} ===")
            gap = g["target_nominal_trieu"] / d["total_trieu"]
            print(f"Hiện có {_vi(d['total_trieu'], 0)} tr → cần "
                  f"{_vi(g['target_nominal_trieu'], 0)} tr = gấp {_vi(gap, 2)} lần")
            print(f"  {g['note']}")
            if g.get("horizons"):
                print(f"\n{'Thời hạn':>9}{'Lợi suất cần':>14}{'(thực)':>10}"
                      f"{'Hoặc gửi thêm':>16}{'   Phân loại'}")
                print(f"{'':>9}{'nếu KHÔNG gửi thêm':>24}{'ở lãi tiền gửi':>16}")
                for h in g["horizons"]:
                    print(f"{str(h['years']) + ' năm':>9}"
                          f"{_vi(h['required_return_pct'], 2) + '%':>14}"
                          f"{'(' + _vi(h['required_real_return_pct'], 2) + '%)':>10}"
                          f"{(_vi(h['required_monthly_trieu'], 1) + ' tr/th') if h['required_monthly_trieu'] else 'không cần':>16}"
                          f"   {h['band_label']}")
                print(f"\n{g['best_lever']}")
            print(f"\nLƯU Ý VỀ SỨC MUA: {g['reality_20y']}")
    else:
        print("\n=== MỤC TIÊU ===\nChưa khai mục tiêu nào trong config/plan.yaml.")
        print("Thiếu mục tiêu thì mọi ngưỡng rủi ro đều là con số tuỳ tiện: "
              "'vàng ≥70%' — 70% so với cái gì?")


def _vi(value, decimals: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}".translate(str.maketrans({",": ".", ".": ","}))


if __name__ == "__main__":
    main()
