"""Test cho gold/ — quy đổi, mô hình hiệu chuẩn (Phase 4)."""
import pytest

from gold.conversion import (
    GRAMS_PER_TROY_OUNCE,
    GRAMS_PER_VIETNAMESE_TAEL,
    theoretical_trieu_per_tael,
    theoretical_vnd_per_tael,
)
from gold.xuan_trieu_model import calibration_sample_size, estimate, mae


def test_constants_match_spec_exactly():
    assert GRAMS_PER_TROY_OUNCE == 31.1034768
    assert GRAMS_PER_VIETNAMESE_TAEL == 37.5


def test_theoretical_vnd_per_tael_known_value():
    v = theoretical_vnd_per_tael(4017, 26460)
    assert v == pytest.approx(128_148_639.96, rel=1e-6)


def test_theoretical_trieu_per_tael_matches_photo_calibration_within_rounding():
    # Ảnh bảng giá thật: thế giới quy đổi ~128.15 tr/lượng tại XAU=4017, fx=26460
    v = theoretical_trieu_per_tael(4017, 26460)
    assert v == pytest.approx(128.15, abs=0.01)


def test_estimate_matches_known_shop_prices_at_calibration_point():
    r = estimate(xau_usd=4017, usd_vnd=26460)
    assert r is not None
    assert r.shop_buy_trieu == pytest.approx(127.5, abs=0.01)
    assert r.shop_sell_trieu == pytest.approx(130.0, abs=0.01)


def test_estimate_confidence_low_with_single_calibration_sample():
    r = estimate(xau_usd=4017, usd_vnd=26460)
    assert r.confidence == "LOW"
    assert r.sample_size == 1


def test_estimate_reacts_upward_to_world_price_increase():
    base = estimate(xau_usd=4017, usd_vnd=26460)
    higher = estimate(xau_usd=4200, usd_vnd=26460)
    assert higher.shop_buy_trieu > base.shop_buy_trieu
    assert higher.shop_sell_trieu > base.shop_sell_trieu


def test_estimate_returns_none_for_zero_xau():
    assert estimate(xau_usd=0, usd_vnd=26460) is None


def test_estimate_returns_none_for_zero_fx():
    assert estimate(xau_usd=4017, usd_vnd=0) is None


def test_calibration_sample_size_at_least_one():
    assert calibration_sample_size() >= 1


def test_mae_returns_none_with_insufficient_samples_not_a_fake_number():
    result = mae()
    assert result["mae_trieu"] is None
    assert result["confidence"] == "LOW"
    assert "reason" in result
