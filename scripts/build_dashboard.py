#!/usr/bin/env python3
"""Sinh dashboard bản tin từ dữ liệu — CLI mỏng gọi reporting/dashboard_builder.

Cách dùng:
  python3 scripts/build_dashboard.py          # ghi dashboard/ban-tin-dau-tu.html
  python3 scripts/build_dashboard.py --check  # chỉ kiểm tra, KHÔNG ghi file

`--check` dùng cho health check / CI: xác nhận dashboard sinh được từ dữ liệu
hiện có mà không chạm vào file đang phục vụ.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reporting.dashboard_builder import OUTPUT_PATH, build_context, render  # noqa: E402


def main() -> None:
    check_only = "--check" in sys.argv[1:]
    ctx = build_context()
    out = render(ctx)
    latest = ctx["latest"]
    n = len(ctx["history"])
    if check_only:
        print(f"OK: sinh được dashboard {len(out):,} ký tự từ {n} snapshot "
              f"(mới nhất {latest.get('date')} {latest.get('ky')}) — chưa ghi file.")
        return
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(out, encoding="utf-8")
    print(f"Đã sinh {OUTPUT_PATH.relative_to(ROOT)} từ {n} snapshot "
          f"(mới nhất {latest.get('date')} {latest.get('ky')}).")
    fresh_label, fresh_level = ctx["freshness"]
    if fresh_level != "ok":
        print(f"⚠️  Tuổi dữ liệu: {fresh_label}")
    if ctx["pending"].get("message"):
        print(f"⚠️  {ctx['pending']['tag']}")


if __name__ == "__main__":
    main()
