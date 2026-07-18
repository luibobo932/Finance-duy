#!/usr/bin/env python3
"""Chấm điểm minh bạch cho Vàng, cổ phiếu và gửi tiết kiệm.

Điểm số là công cụ sàng lọc theo quy tắc, không phải dự báo giá hay lệnh mua/bán.

Cách dùng:
  python scripts/decision_engine.py report
  python scripts/decision_engine.py export data/decision_latest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from .finance_data import DataValidationError, load_history
except ImportError:  # Chạy trực tiếp
    from finance_data import DataValidationError, load_history

ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = ROOT / "data" / "history.jsonl"
PROFILE_PATH = ROOT / "config" / "decision_profile.json"
SOURCE_REGISTRY_PATH = ROOT / "config" / "sources.json"

DEFAULT_PROFILE = {
    "version": 1,
    "profile_name": "Khung cân bằng mặc định",
    "risk_tolerance": "balanced",
    "investment_horizon_months": 24,
    "liquidity_need": "medium",
    "max_single_stock_pct": 20,
    "gold_premium_caution_trieu": 15,
    "volume_spike_ratio": 1.5,
    "stale_after_days": 3,
    "minimum_emergency_fund_months": 6,
    "deposit_insurance_limit_vnd": 350_000_000,
    "deposit_insurance_effective_date": "2026-07-13",
    "stock_round_trip_cost_pct": 0.35,
    "fundamentals_stale_after_days": 200,
    "gold_stale_after_days": 1,
}


def get(value, *path):
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def clamp(value, low=0, high=100):
    return max(low, min(high, round(value)))


def percent_change(current, previous):
    if not is_number(current) or not is_number(previous) or previous == 0:
        return None
    return (current - previous) / previous * 100


def load_profile(path=PROFILE_PATH):
    profile = dict(DEFAULT_PROFILE)
    path = Path(path)
    if path.exists():
        try:
            custom = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DataValidationError(f"{path.name}: JSON lỗi ({exc.msg})") from None
        if not isinstance(custom, dict):
            raise DataValidationError("decision_profile.json phải là object")
        profile.update(custom)

    if profile["risk_tolerance"] not in ("conservative", "balanced", "growth"):
        raise DataValidationError("risk_tolerance phải là conservative, balanced hoặc growth")
    for field in (
        "investment_horizon_months",
        "max_single_stock_pct",
        "gold_premium_caution_trieu",
        "volume_spike_ratio",
        "stale_after_days",
        "minimum_emergency_fund_months",
        "deposit_insurance_limit_vnd",
        "stock_round_trip_cost_pct",
        "fundamentals_stale_after_days",
        "gold_stale_after_days",
    ):
        if not is_number(profile.get(field)) or profile[field] < 0:
            raise DataValidationError(f"decision_profile.{field} phải là số không âm")
    return profile


def latest_previous(history):
    if not history:
        raise DataValidationError("history.jsonl chưa có dữ liệu")
    return history[-1], history[-2] if len(history) > 1 else None


def load_source_registry(path=SOURCE_REGISTRY_PATH):
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataValidationError(f"không đọc được registry nguồn: {exc}") from None
    sources = payload.get("sources", []) if isinstance(payload, dict) else []
    return {item["id"]: item for item in sources if isinstance(item, dict) and item.get("id") and item.get("url")}


def verified_sources(snapshot):
    registry = load_source_registry()
    verified = []
    try:
        collected_at = datetime.fromisoformat(snapshot["collected_at"])
    except (KeyError, TypeError, ValueError):
        return verified
    for source in snapshot.get("sources", []):
        registered = registry.get(source.get("id"))
        if not registered:
            continue
        declared_url = source.get("url", "")
        registered_url = registered["url"]
        if not (declared_url == registered_url or declared_url.startswith(registered_url + "?")):
            continue
        try:
            retrieved_at = datetime.fromisoformat(source["retrieved_at"])
            source_age = collected_at - retrieved_at
        except (KeyError, TypeError, ValueError):
            continue
        if source_age < -timedelta(minutes=5):
            continue
        stale_after_hours = registered.get("stale_after_hours")
        if is_number(stale_after_hours) and source_age > timedelta(hours=stale_after_hours):
            continue
        allowed_fields = set(registered.get("allowed_fields", []))
        sanitized_fields = [field for field in source.get("fields", []) if field in allowed_fields]
        if not sanitized_fields:
            continue
        verified.append({**source, "fields": sanitized_fields})
    return verified


def source_fields(snapshot):
    fields = set()
    for source in verified_sources(snapshot):
        if not isinstance(source, dict):
            continue
        fields.update(source.get("fields", []))
    return fields


def verified_risk_flags(snapshot):
    covered = source_fields(snapshot)
    return {
        key: value
        for key, value in snapshot.get("risk_flags", {}).items()
        if value and f"risk_flags.{key}" in covered
    }


def data_quality(history, today, profile):
    current, _ = latest_previous(history)
    try:
        effective_date = datetime.fromisoformat(current["collected_at"]).date()
    except (KeyError, TypeError, ValueError):
        effective_date = date.fromisoformat(current["date"])
    raw_age_days = (today - effective_date).days
    is_future = raw_age_days < 0
    age_days = max(0, raw_age_days)
    expected = [
        ("vnindex.close", get(current, "vnindex", "close")),
        ("schema_version", current.get("schema_version")),
        ("market_date", current.get("market_date")),
        ("collected_at", current.get("collected_at")),
        ("vcb.close", get(current, "vcb", "close")),
        ("ctd.close", get(current, "ctd", "close")),
        ("vcb.volume_million_shares", get(current, "vcb", "volume_million_shares")),
        ("ctd.volume_million_shares", get(current, "ctd", "volume_million_shares")),
        ("gold.sjc_buy", get(current, "gold", "sjc_buy")),
        ("gold.sjc_sell", get(current, "gold", "sjc_sell")),
        ("gold.xauusd", get(current, "gold", "xauusd")),
        ("gold.observed_at", get(current, "gold", "observed_at")),
        ("gold.premium_trieu", get(current, "gold", "premium_trieu")),
        ("foreign_net_ty", current.get("foreign_net_ty")),
        ("deposit_top", current.get("deposit_top")),
    ]
    missing = [name for name, value in expected if value is None or value == []]
    completeness = (len(expected) - len(missing)) / len(expected)
    declared_sources = current.get("sources", [])
    sources = verified_sources(current)
    covered = source_fields(current)
    source_targets = ("vnindex", "vcb", "ctd", "gold", "foreign_net_ty", "deposit_top")
    source_hits = sum(
        any(target == field or target.startswith(field + ".") or field.startswith(target + ".") for field in covered)
        for target in source_targets
    )
    source_score = source_hits / len(source_targets)
    freshness = max(0, 1 - age_days / max(profile["stale_after_days"], 1))
    score = clamp(completeness * 65 + source_score * 20 + freshness * 15)
    if source_score < 0.5:
        score = min(score, 54)
    if is_future:
        score = min(score, 20)
    elif age_days > profile["stale_after_days"]:
        score = min(score, 40)
    warnings = []
    if current.get("schema_version") != 2:
        warnings.append("schema_version không tương thích; cần migration lên phiên bản 2")
    if is_future:
        warnings.append("collected_at nằm trong tương lai so với ngày đánh giá")
    if age_days > profile["stale_after_days"]:
        warnings.append(f"Dữ liệu đã cũ {age_days} ngày")
    if not sources:
        warnings.append("Snapshot chưa có nguồn khớp registry nên chưa thể kiểm toán số liệu")
    if len(declared_sources) != len(sources):
        warnings.append(f"Bỏ qua {len(declared_sources) - len(sources)} nguồn không khớp config/sources.json")
    if missing:
        warnings.append("Thiếu: " + ", ".join(missing))
    raw_risks = [key for key, value in current.get("risk_flags", {}).items() if value]
    if raw_risks and not verified_risk_flags(current):
        warnings.append("Cờ tin tức chưa có provenance nên không được chấm điểm")
    grade = "Tốt" if score >= 80 else "Trung bình" if score >= 55 else "Thấp"
    return {
        "score": score,
        "grade": grade,
        "age_days": age_days,
        "source_count": len(sources),
        "source_coverage_pct": round(source_score * 100),
        "is_stale": is_future or age_days > profile["stale_after_days"],
        "is_future": is_future,
        "schema_compatible": current.get("schema_version") == 2,
        "evaluation_date": today.isoformat(),
        "missing_fields": missing,
        "warnings": warnings,
    }


def confidence(current, required_paths, quality):
    present = sum(get(current, *path.split(".")) is not None for path in required_paths)
    coverage = present / len(required_paths) if required_paths else 1
    covered_fields = source_fields(current)
    def is_covered(path):
        if path == "gold.premium_trieu":
            return {"gold.sjc_sell", "gold.xauusd", "fx_vcb_sell"}.issubset(covered_fields)
        return any(path == field or path.startswith(field + ".") for field in covered_fields)

    source_hits = sum(is_covered(path) for path in required_paths)
    source_coverage = source_hits / len(required_paths) if required_paths else 1
    freshness = 1 if quality["age_days"] <= 1 else 0 if quality["is_stale"] else 0.5
    value = clamp(coverage * 45 + source_coverage * 35 + freshness * 20)
    # URL không gắn đúng field không được nâng độ tin cậy.
    return min(value, 60) if source_coverage == 0 else value


def signal(score, confidence_score=100):
    if confidence_score < 65:
        return "Chờ dữ liệu"
    if score >= 70:
        return "Ưu tiên cao"
    if score >= 55:
        return "Theo dõi tích cực"
    if score >= 40:
        return "Trung lập"
    return "Thận trọng"


def finalize_decision(item, quality):
    item["confidence"] = clamp(item["confidence"])
    blocked = item["confidence"] < 65 or quality["is_stale"] or not quality["schema_compatible"] or bool(item.get("hard_blockers"))
    item["signal"] = "Chờ dữ liệu" if blocked else signal(item["score"], item["confidence"])
    item["decision_status"] = "WAIT_DATA" if blocked else "READY"
    if item["decision_status"] == "WAIT_DATA":
        item["action"] = "CHỜ DỮ LIỆU — " + item["action"]
    if quality["is_stale"] and "Dữ liệu đã quá hạn" not in item["missing_data"]:
        item["missing_data"].append("Dữ liệu đã quá hạn")
    return item


def analyze_gold(current, previous, quality, profile):
    score = 50
    reasons, risks, missing, invalidation, hard_blockers = [], [], [], [], []
    if not current.get("collected_at"):
        hard_blockers.append("Thiếu thời điểm thu thập dữ liệu (collected_at)")
    xau = get(current, "gold", "xauusd")
    fx_sell = current.get("fx_vcb_sell")
    prev_xau = get(previous, "gold", "xauusd")
    observed_at = get(current, "gold", "observed_at")
    previous_observed_at = get(previous, "gold", "observed_at")
    if not observed_at:
        hard_blockers.append("Thiếu thời điểm hiệu lực giá vàng (gold.observed_at)")
    else:
        try:
            observed_time = datetime.fromisoformat(observed_at)
            collected_time = datetime.fromisoformat(current["collected_at"])
            evaluation_date = date.fromisoformat(quality["evaluation_date"])
            if observed_time > collected_time + timedelta(minutes=5):
                hard_blockers.append("Thời điểm giá vàng nằm sau thời điểm thu thập")
            if (evaluation_date - observed_time.date()).days > profile["gold_stale_after_days"]:
                hard_blockers.append("Giá vàng đã quá hạn sử dụng")
        except (KeyError, TypeError, ValueError):
            hard_blockers.append("Không xác minh được thứ tự thời gian của giá vàng")
    if not is_number(xau) or xau <= 0:
        hard_blockers.append("Thiếu giá XAU/USD hợp lệ")
    if not is_number(fx_sell) or fx_sell <= 0:
        hard_blockers.append("Thiếu tỷ giá bán USD/VND hợp lệ để quy đổi premium")
    current_fields = source_fields(current)
    previous_fields = source_fields(previous or {})
    comparable_gold = bool(
        observed_at
        and previous_observed_at
        and observed_at != previous_observed_at
        and "gold.xauusd" in current_fields
        and "gold.xauusd" in previous_fields
    )
    required_gold_sources = {"gold.xauusd", "gold.sjc_buy", "gold.sjc_sell", "gold.observed_at", "fx_vcb_sell"}
    missing_gold_sources = sorted(required_gold_sources - current_fields)
    if missing_gold_sources:
        hard_blockers.append("Thiếu nguồn đúng field cho vàng: " + ", ".join(missing_gold_sources))
    momentum = percent_change(xau, prev_xau) if comparable_gold else None
    if momentum is None:
        missing.append("Giá XAU/USD kỳ trước")
    elif momentum >= 1:
        score += 9
        reasons.append(f"XAU/USD tăng {momentum:.2f}% so với kỳ trước")
    elif momentum > 0:
        score += 4
        reasons.append(f"XAU/USD tăng nhẹ {momentum:.2f}%")
    elif momentum <= -1:
        score -= 9
        risks.append(f"XAU/USD giảm {abs(momentum):.2f}% so với kỳ trước")
    else:
        score -= 3
        risks.append("Động lượng XAU/USD đang yếu")

    premium = get(current, "gold", "premium_trieu")
    caution = profile["gold_premium_caution_trieu"]
    premium_covered = {"gold.sjc_sell", "gold.xauusd", "fx_vcb_sell"}.issubset(current_fields)
    if premium is None:
        missing.append("Chênh lệch giá vàng Việt Nam – thế giới")
        hard_blockers.append("Thiếu premium vàng trong nước – thế giới")
    elif not premium_covered:
        missing.append("Nguồn thành phần để tính premium vàng")
    elif premium <= 10:
        score += 12
        reasons.append(f"Premium trong nước {premium:.1f} triệu/lượng ở vùng thấp")
    elif premium <= caution:
        score += 4
        reasons.append(f"Premium {premium:.1f} triệu/lượng chưa vượt ngưỡng thận trọng")
    elif premium <= caution + 5:
        score -= 6
        risks.append(f"Premium {premium:.1f} triệu/lượng cao hơn ngưỡng {caution:.1f}")
    else:
        score -= 14
        risks.append(f"Premium {premium:.1f} triệu/lượng rất cao")

    if premium_covered and all(is_number(value) and value > 0 for value in (xau, fx_sell, get(current, "gold", "sjc_sell"))) and is_number(premium):
        world_million_per_tael = xau * fx_sell * 37.5 / 31.1034768 / 1_000_000
        calculated_premium = get(current, "gold", "sjc_sell") - world_million_per_tael
        if abs(calculated_premium - premium) > 1:
            hard_blockers.append("Premium vàng không khớp SJC, XAU/USD và tỷ giá VCB")

    sjc_buy = get(current, "gold", "sjc_buy")
    sjc_sell = get(current, "gold", "sjc_sell")
    spread_covered = {"gold.sjc_buy", "gold.sjc_sell"}.issubset(current_fields)
    spread_pct = percent_change(sjc_sell, sjc_buy) if spread_covered else None
    if not is_number(sjc_buy) or not is_number(sjc_sell):
        missing.append("Chênh lệch mua–bán SJC")
        hard_blockers.append("Thiếu giá mua hoặc bán SJC")
    elif not spread_covered:
        missing.append("Nguồn đúng field cho spread SJC")
    elif spread_pct > 2:
        score -= 6
        risks.append(f"Spread mua–bán SJC rộng {spread_pct:.2f}%")
    else:
        score += 2
        reasons.append(f"Spread mua–bán SJC {spread_pct:.2f}%")

    if verified_risk_flags(current).get("war"):
        score += 3
        reasons.append("Rủi ro địa chính trị hỗ trợ nhu cầu phòng thủ")
        risks.append("Địa chính trị làm biến động vàng khó dự báo")
    invalidation.extend([
        "XAU/USD mất vùng hỗ trợ gần nhất với khối lượng bán tăng",
        f"Premium trong nước duy trì trên {caution + 5:.1f} triệu/lượng",
        "Fed chuyển sang lập trường diều hâu hơn kỳ vọng",
    ])
    final_score = clamp(score)
    action = (
        "Chưa nên đuổi giá SJC; ưu tiên theo dõi premium và spread, chỉ mô phỏng mua từng phần."
        if premium_covered and premium is not None and premium > caution
        else "Theo dõi phương án mua từng phần, giữ giới hạn tỷ trọng và điểm dừng luận điểm."
    )
    return finalize_decision({
        "id": "gold",
        "name": "Vàng",
        "role": "Phòng thủ / chống bất định",
        "risk_level": "Trung bình",
        "score": final_score,
        "confidence": confidence(current, ["gold.xauusd", "gold.sjc_buy", "gold.sjc_sell", "gold.premium_trieu", "gold.observed_at", "fx_vcb_sell"], quality),
        "action": action,
        "reasons": reasons,
        "risks": risks,
        "missing_data": missing,
        "hard_blockers": hard_blockers,
        "invalidation": invalidation,
        "metrics": {
            "xauusd": xau,
            "sjc_buy": sjc_buy,
            "sjc_sell": sjc_sell,
            "momentum_pct": momentum,
            "premium_trieu": premium,
            "sjc_spread_pct": spread_pct,
        },
    }, quality)


def past_volume_ratio(history, ticker):
    latest = history[-1]
    current = get(latest, ticker, "volume_million_shares")
    latest_fields = source_fields(latest)
    if latest.get("ky") != "chieu" or not latest.get("market_date") or f"{ticker}.volume_million_shares" not in latest_fields or "market_date" not in latest_fields:
        return None
    by_market_date = {}
    for item in history[:-1]:
        market_date = item.get("market_date")
        volume = get(item, ticker, "volume_million_shares")
        fields = source_fields(item)
        if item.get("ky") == "chieu" and market_date and is_number(volume) and f"{ticker}.volume_million_shares" in fields and "market_date" in fields:
            by_market_date[market_date] = volume
    values = list(by_market_date.values())[-20:]
    if not is_number(current) or not values:
        return None
    average = sum(values) / len(values)
    return current / average if average else None


def analyze_stock(history, ticker, quality, profile):
    current, previous = latest_previous(history)
    score = 50
    reasons, risks, missing, hard_blockers = [], [], [], []
    name = ticker.upper()
    price = get(current, ticker, "close")
    prior_close = get(current, ticker, "prior_close")
    prev_price = get(previous, ticker, "close")
    market_date = current.get("market_date")
    previous_market_date = previous.get("market_date") if previous else None
    comparable_periods = bool(
        market_date
        and previous_market_date
        and market_date != previous_market_date
        and f"{ticker}.close" in source_fields(current)
        and f"{ticker}.close" in source_fields(previous or {})
        and "market_date" in source_fields(previous or {})
    )
    momentum = percent_change(price, prev_price) if comparable_periods else None
    stock_change = get(current, ticker, "change_pct")
    market_change = get(current, "vnindex", "change_pct")
    current_fields = source_fields(current)
    current_volume = get(current, ticker, "volume_million_shares")
    market_close = get(current, "vnindex", "close")
    if not is_number(price) or price <= 0:
        hard_blockers.append(f"Thiếu giá đóng cửa hợp lệ của {name}")
    if not is_number(prior_close) or prior_close <= 0:
        hard_blockers.append(f"Thiếu giá tham chiếu hợp lệ của {name}")
    if not is_number(stock_change):
        hard_blockers.append(f"Thiếu biến động phần trăm chính thức của {name}")
    if not is_number(current_volume) or current_volume < 0:
        hard_blockers.append(f"Thiếu khối lượng giao dịch hợp lệ của {name}")
    if not is_number(market_close) or market_close <= 0 or not is_number(market_change):
        hard_blockers.append("Thiếu giá/biến động VN-Index để so sánh tương đối")
    if is_number(price) and is_number(prior_close) and prior_close > 0 and is_number(stock_change):
        calculated_change = (price - prior_close) / prior_close * 100
        if abs(calculated_change - stock_change) > 0.08:
            hard_blockers.append(f"Biến động {name} không khớp giá đóng cửa và giá tham chiếu")
    stock_change_verified = is_number(stock_change) and f"{ticker}.change_pct" in current_fields
    if stock_change is None:
        stock_change = momentum
    if not market_date:
        missing.append("Ngày hiệu lực giá thị trường (market_date)")
        hard_blockers.append("Thiếu market_date của giá cổ phiếu")
    else:
        try:
            market_day = date.fromisoformat(market_date)
            collected_day = datetime.fromisoformat(current["collected_at"]).date()
            evaluation_day = date.fromisoformat(quality["evaluation_date"])
            if market_day > collected_day:
                hard_blockers.append("market_date nằm sau thời điểm thu thập")
            if (evaluation_day - market_day).days > profile["stale_after_days"]:
                hard_blockers.append("Giá cổ phiếu đã quá hạn sử dụng")
        except (KeyError, TypeError, ValueError):
            hard_blockers.append("Không xác minh được thứ tự thời gian của giá cổ phiếu")
    if not current.get("collected_at"):
        hard_blockers.append("Thiếu thời điểm thu thập dữ liệu (collected_at)")
    if not stock_change_verified:
        missing.append(f"Biến động giá {name}")
    else:
        score += max(-10, min(10, stock_change * 2))
        (reasons if stock_change > 0 else risks).append(f"{name} biến động {stock_change:+.2f}%")

    if stock_change_verified and is_number(market_change) and "vnindex.change_pct" in current_fields:
        relative = stock_change - market_change
        score += max(-8, min(8, relative * 2))
        if relative > 0:
            reasons.append(f"Mạnh hơn VN-Index {relative:.2f} điểm %")
        elif relative < 0:
            risks.append(f"Yếu hơn VN-Index {abs(relative):.2f} điểm %")
    else:
        relative = None
        missing.append("Sức mạnh tương đối với VN-Index")

    volume_ratio = past_volume_ratio(history, ticker)
    if volume_ratio is None:
        missing.append(f"KLGD {name} và bình quân phiên chiều")
        hard_blockers.append(f"Chưa đủ lịch sử phiên chiều để xác minh thanh khoản {name}")
    elif volume_ratio >= profile["volume_spike_ratio"]:
        if not stock_change_verified:
            missing.append(f"Chiều biến động giá {name} để đọc tín hiệu khối lượng")
        elif stock_change > 0:
            score += 9
            reasons.append(f"KLGD {volume_ratio:.1f}× bình quân đi cùng giá tăng")
        else:
            score -= 9
            risks.append(f"KLGD {volume_ratio:.1f}× bình quân nhưng giá không tăng")
    else:
        reasons.append(f"KLGD {volume_ratio:.1f}× bình quân, chưa đột biến")

    foreign = current.get("foreign_net_ty")
    if foreign is None or "foreign_net_ty" not in source_fields(current):
        missing.append("Khối ngoại kỳ chiều")
    elif foreign > 0:
        score += 4
        reasons.append("Khối ngoại mua ròng toàn thị trường")
    elif foreign < 0:
        score -= 4
        risks.append("Khối ngoại bán ròng toàn thị trường")

    if verified_risk_flags(current).get("arrest"):
        score -= 15
        risks.append("Có cờ rủi ro quản trị/doanh nghiệp cần xác minh")

    fundamentals = get(current, ticker, "fundamentals")
    fundamentals_sourced = f"{ticker}.fundamentals" in current_fields
    required_fundamentals = ("report_end_date", "earnings_growth_pct", "roe_pct", "pe")
    fundamentals_complete = bool(
        isinstance(fundamentals, dict)
        and isinstance(fundamentals.get("report_end_date"), str)
        and all(is_number(fundamentals.get(field)) for field in required_fundamentals[1:])
    )
    if not fundamentals_complete:
        missing.append(f"Định giá và cơ bản {name}")
        hard_blockers.append(f"Thiếu ngày cuối kỳ, tăng trưởng lợi nhuận, ROE hoặc P/E đã kiểm chứng của {name}")
    elif fundamentals_sourced:
        try:
            report_end = date.fromisoformat(fundamentals["report_end_date"])
            reference_date = date.fromisoformat(market_date or current["date"])
            fundamentals_age = (reference_date - report_end).days
        except (TypeError, ValueError):
            fundamentals_age = None
        if fundamentals_age is None or fundamentals_age < 0 or fundamentals_age > profile["fundamentals_stale_after_days"]:
            hard_blockers.append(f"Dữ liệu cơ bản {name} đã quá hạn hoặc có kỳ báo cáo không hợp lệ")
        else:
            growth = fundamentals.get("earnings_growth_pct")
            roe = fundamentals["roe_pct"]
            pe = fundamentals["pe"]
            score += max(-8, min(8, growth / 5))
            (reasons if growth > 0 else risks).append(f"Tăng trưởng lợi nhuận {growth:+.1f}%")
            if roe >= 15:
                score += 5
                reasons.append(f"ROE {roe:.1f}%")
            elif roe < 8:
                score -= 4
                risks.append(f"ROE thấp {roe:.1f}%")
            if 0 < pe <= 15:
                score += 4
                reasons.append(f"P/E {pe:.1f}×")
            elif pe > 25 or pe <= 0:
                score -= 5
                risks.append(f"P/E cần thận trọng: {pe:.1f}×")
    if not fundamentals_sourced:
        hard_blockers.append(f"Thiếu nguồn IR chính thức cho dữ liệu cơ bản {name}")
    required_stock_sources = {
        "market_date",
        "vnindex.close",
        "vnindex.change_pct",
        f"{ticker}.prior_close",
        f"{ticker}.close",
        f"{ticker}.change_pct",
        f"{ticker}.volume_million_shares",
        f"{ticker}.fundamentals",
    }
    missing_stock_sources = sorted(required_stock_sources - source_fields(current))
    if missing_stock_sources:
        hard_blockers.append(f"Thiếu nguồn đúng field cho {name}: " + ", ".join(missing_stock_sources))

    final_score = clamp(score)
    if len(missing) >= 3:
        action = "Chưa đủ dữ liệu để tăng tỷ trọng; cần bổ sung khối lượng, định giá và nguồn công bố."
    elif final_score >= 55:
        action = "Theo dõi điểm vào từng phần; chỉ hành động khi giá, khối lượng và luận điểm cơ bản cùng xác nhận."
    else:
        action = "Giữ trạng thái quan sát; chờ tín hiệu xác nhận hoặc mức định giá an toàn hơn."
    return finalize_decision({
        "id": ticker,
        "name": name,
        "role": "Tăng trưởng vốn",
        "risk_level": "Cao",
        "score": final_score,
        "confidence": confidence(current, [f"{ticker}.prior_close", f"{ticker}.close", f"{ticker}.change_pct", f"{ticker}.volume_million_shares", f"{ticker}.fundamentals", "vnindex.close", "vnindex.change_pct", "market_date"], quality) - (10 if not fundamentals_complete else 0),
        "action": action,
        "reasons": reasons,
        "risks": risks,
        "missing_data": missing,
        "hard_blockers": hard_blockers,
        "invalidation": [
            "Luận điểm tăng trưởng lợi nhuận/backlog không còn đúng",
            "Phá hỗ trợ quan trọng với khối lượng bán tăng",
            "Xuất hiện cờ đỏ quản trị hoặc giao dịch nội bộ đã xác minh",
        ],
        "metrics": {"price": price, "momentum_pct": momentum, "relative_strength_pct": relative, "volume_ratio": volume_ratio},
    }, quality)


def analyze_savings(current, quality, profile):
    all_rates = current.get("deposit_top", [])
    required_product_fields = (
        "channel",
        "minimum_amount_vnd",
        "maximum_amount_vnd",
        "conditions",
        "effective_date",
        "payout_method",
        "source_id",
        "source_url",
        "retrieved_at",
    )
    current_date = date.fromisoformat(current["date"])
    registry = load_source_registry()
    verified_by_id = {source["id"]: source for source in verified_sources(current)}

    def product_is_verified(item):
        if not isinstance(item, dict) or not all(item.get(field) is not None for field in required_product_fields):
            return False
        source_id = item.get("source_id")
        source = verified_by_id.get(source_id)
        registered = registry.get(source_id)
        if not source or not registered or "deposit_top" not in source.get("fields", []):
            return False
        if item.get("source_url") != registered.get("url") or item.get("retrieved_at") != source.get("retrieved_at"):
            return False
        if item.get("bank") not in registered.get("allowed_banks", []):
            return False
        if not all(isinstance(item.get(field), str) and item[field].strip() for field in ("bank", "channel", "conditions", "payout_method")):
            return False
        if not all(is_number(item.get(field)) for field in ("term_months", "rate_pct", "minimum_amount_vnd", "maximum_amount_vnd")):
            return False
        if not (item["term_months"] >= 1 and 0 < item["rate_pct"] <= 20):
            return False
        if not (0 <= item["minimum_amount_vnd"] < 1_000_000_000 and item["maximum_amount_vnd"] >= item["minimum_amount_vnd"]):
            return False
        try:
            effective_date = date.fromisoformat(item["effective_date"])
        except (TypeError, ValueError):
            return False
        return 0 <= (current_date - effective_date).days <= 60

    verified_rates = [
        item for item in all_rates
        if product_is_verified(item)
    ]
    rates = sorted(
        verified_rates,
        key=lambda item: item.get("rate_pct", 0),
        reverse=True,
    )
    score = 50
    reasons, risks, missing, hard_blockers = [], [], [], []
    if not current.get("collected_at"):
        hard_blockers.append("Thiếu thời điểm thu thập dữ liệu (collected_at)")
    top = rates[0] if rates else None
    if not top:
        score -= 20
        missing.append("Bảng lãi suất theo kỳ hạn và điều kiện số dư")
    else:
        rate = top["rate_pct"]
        qualifier = "đã xác minh dải số tiền có thể dùng dưới 1 tỷ"
        if rate >= 7:
            score += 16
            reasons.append(f"Mức niêm yết cao nhất {rate:.2f}%/năm; {qualifier}")
        elif rate >= 6:
            score += 10
            reasons.append(f"Mức cao nhất {rate:.2f}%/năm")
        elif rate >= 5:
            score += 4
        else:
            score -= 5
            risks.append("Lãi suất danh nghĩa thấp")
        if top.get("term_months", 99) <= 12:
            score += 4
            reasons.append(f"Kỳ hạn {top['term_months']} tháng không quá dài")
        else:
            risks.append("Kỳ hạn dài làm giảm thanh khoản")
    bank_count = len({item["bank"] for item in rates})
    if bank_count >= 3:
        score += 4
        reasons.append(f"Có {bank_count} ngân hàng để so sánh")
    else:
        missing.append("Ít nhất 3 ngân hàng cùng điều kiện gửi")
    missing.append("Lạm phát kỳ vọng để tính lãi suất thực")
    missing_rate_fields = [field for field in required_product_fields if not top or top.get(field) is None]
    if missing_rate_fields:
        missing.append("Điều kiện sản phẩm tiết kiệm: " + ", ".join(missing_rate_fields))
        hard_blockers.append("Chưa có sản phẩm tiết kiệm đủ trường để xác minh khoản dưới 1 tỷ")
    risks.extend([
        "Rút trước hạn thường chỉ nhận lãi không kỳ hạn",
        "Cần xác minh điều kiện online, khách hàng mới và số dư tối thiểu",
        f"Hạn mức bảo hiểm tiền gửi theo cấu hình là {profile['deposit_insurance_limit_vnd']:,.0f} đồng/người/tổ chức tham gia",
    ])
    final_score = clamp(score)
    action = "Phù hợp phần vốn cần bảo toàn; nên chia bậc thang kỳ hạn thay vì khóa toàn bộ một lần."
    rate_confidence = confidence(current, ["deposit_top"], quality)
    if missing_rate_fields:
        rate_confidence -= 25
    return finalize_decision({
        "id": "savings",
        "name": "Gửi tiết kiệm",
        "role": "Bảo toàn vốn / tạo thanh khoản",
        "risk_level": "Thấp",
        "score": final_score,
        "confidence": rate_confidence,
        "action": action,
        "reasons": reasons,
        "risks": risks,
        "missing_data": missing,
        "hard_blockers": hard_blockers,
        "invalidation": [
            "Cần dùng tiền trước ngày đáo hạn",
            "Lạm phát kỳ vọng vượt xa lãi suất sau thuế/phí",
            "Điều kiện thực tế không áp dụng cho khoản tiền của người dùng",
        ],
        "metrics": {"top_rate_pct": top.get("rate_pct") if top else None, "term_months": top.get("term_months") if top else None, "bank": top.get("bank") if top else None},
        "eligible_products": rates,
    }, quality)


def build_decision_report(history, portfolio=None, profile=None, today=None):
    profile = profile or dict(DEFAULT_PROFILE)
    # portfolio được giữ trong chữ ký để tương thích; engine không đọc hay xuất dữ liệu cá nhân.
    today = today or date.today()
    current, previous = latest_previous(history)
    quality = data_quality(history, today, profile)
    gold = analyze_gold(current, previous, quality, profile)
    stocks = [analyze_stock(history, ticker, quality, profile) for ticker in ("vcb", "ctd")]
    savings = analyze_savings(current, quality, profile)
    stock_class = {
        "id": "stocks",
        "name": "Cổ phiếu theo dõi",
        "role": "Tăng trưởng vốn · chỉ VCB/CTD",
        "scope": "VCB và CTD; không đại diện toàn thị trường chứng khoán",
        "risk_level": "Cao",
        "score": clamp(sum(item["score"] for item in stocks) / len(stocks)),
        "confidence": clamp(sum(item["confidence"] for item in stocks) / len(stocks)),
        "action": "Chỉ xem xét sau khi từng mã đạt ngưỡng dữ liệu giá, thanh khoản và cơ bản.",
        "reasons": [f"{item['name']}: {item['signal']} ({item['confidence']}/100)" for item in stocks],
        "risks": [],
        "missing_data": list(dict.fromkeys(value for item in stocks for value in item["missing_data"])),
        "hard_blockers": list(dict.fromkeys(value for item in stocks for value in item["hard_blockers"])),
        "invalidation": list(dict.fromkeys(value for item in stocks for value in item["invalidation"])),
    }
    stocks_ready = all(item["decision_status"] == "READY" for item in stocks)
    stock_class["decision_status"] = "READY" if stocks_ready and not quality["is_stale"] else "WAIT_DATA"
    stock_class["signal"] = signal(stock_class["score"], stock_class["confidence"]) if stock_class["decision_status"] == "READY" else "Chờ dữ liệu"
    if stock_class["decision_status"] == "WAIT_DATA":
        stock_class["action"] = "CHỜ DỮ LIỆU — " + stock_class["action"]
    classes = [savings, gold, stock_class]
    ranking = [item["id"] for item in sorted(classes, key=lambda item: (-item["score"], -item["confidence"]))]
    return {
        "schema_version": 2,
        "as_of": {
            "date": current["date"],
            "ky": current["ky"],
            "market_date": current.get("market_date"),
            "collected_at": current.get("collected_at"),
            "gold_observed_at": get(current, "gold", "observed_at"),
        },
        "generated_on": today.isoformat(),
        "profile": profile,
        "data_quality": quality,
        "verified_sources": verified_sources(current),
        "verified_risks": verified_risk_flags(current),
        "asset_classes": classes,
        "gold": gold,
        "savings": savings,
        "stocks": stocks,
        "ranking": ranking,
        "guardrails": [
            "Không dùng điểm số khi dữ liệu quá hạn hoặc không có nguồn kiểm chứng.",
            "Không vay tiền để đầu tư và không dùng quỹ dự phòng khẩn cấp.",
            "Không giải ngân một lần; xác định trước tỷ trọng tối đa và điều kiện thoát.",
            "Tín hiệu lệnh tròn số không phải bằng chứng giao dịch nội bộ.",
        ],
    }


def print_report(report):
    print(f"=== MA TRẬN QUYẾT ĐỊNH {report['as_of']['date']} {report['as_of']['ky']} ===")
    quality = report["data_quality"]
    print(f"Chất lượng dữ liệu: {quality['score']}/100 ({quality['grade']})")
    for warning in quality["warnings"]:
        print(f"- CẢNH BÁO: {warning}")
    print("\nThứ tự kiểm tra theo điểm sàng lọc (không phải xếp hạng lợi suất):")
    by_id = {item["id"]: item for item in report["asset_classes"]}
    for index, asset_id in enumerate(report["ranking"], 1):
        item = by_id[asset_id]
        print(f"{index}. {item['name']}: {item['score']}/100 — {item['signal']} (tin cậy {item['confidence']}/100)")
    print("\nChi tiết:")
    for item in [report["savings"], report["gold"], *report["stocks"]]:
        print(f"\n## {item['name']} — {item['score']}/100 · {item['signal']}")
        print(item["action"])
        for reason in item["reasons"]:
            print(f"+ {reason}")
        for risk in item["risks"]:
            print(f"! {risk}")
        if item["missing_data"]:
            print("? Thiếu: " + "; ".join(item["missing_data"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("report", help="In ma trận quyết định")
    export_parser = sub.add_parser("export", help="Xuất báo cáo JSON")
    export_parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        history = load_history(HISTORY_PATH)
        profile = load_profile(PROFILE_PATH)
        report = build_decision_report(history, {}, profile)
        if args.command == "report":
            print_report(report)
        else:
            args.path.parent.mkdir(parents=True, exist_ok=True)
            args.path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Đã xuất {args.path}")
    except (DataValidationError, OSError) as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
