"""Test cho scripts/fetch_market_snapshot.py — phần logic thuần túy (parse
XML tỷ giá, build snapshot), không gọi mạng thật."""
from fetch_market_snapshot import build_snapshot, parse_vcb_usd_sell


def test_parse_vcb_usd_sell_extracts_usd_row():
    xml = '''<ExrateList>
      <Exrate CurrencyCode="EUR" CurrencyName="EURO" Buy="29,183.09" Transfer="29,477.87" Sell="30,721.59" />
      <Exrate CurrencyCode="USD" CurrencyName="US DOLLAR" Buy="26,150.00" Transfer="26,180.00" Sell="26,490.00" />
    </ExrateList>'''
    assert parse_vcb_usd_sell(xml) == 26490.0


def test_parse_vcb_usd_sell_missing_usd_returns_none():
    xml = '<ExrateList><Exrate CurrencyCode="EUR" Sell="30,721.59" /></ExrateList>'
    assert parse_vcb_usd_sell(xml) is None


def test_parse_vcb_usd_sell_invalid_xml_returns_none():
    assert parse_vcb_usd_sell("not xml at all") is None


def test_build_snapshot_only_fills_real_fields_rest_stays_absent():
    snap = build_snapshot(date="2026-07-27", ky="chieu", xau_usd=4110.6, fx_vcb_sell=26490.0,
                          vcb=None, ctd=None)
    assert snap["date"] == "2026-07-27"
    assert snap["ky"] == "chieu"
    assert snap["gold"] == {"xauusd": 4110.6}
    assert snap["fx_vcb_sell"] == 26490.0
    # Không bịa VN-Index, khối ngoại, giá SJC/vàng nhẫn, lãi suất — required
    # key "vnindex" vẫn phải có mặt (trend.py REQUIRED) nhưng RỖNG, trung thực.
    assert snap["vnindex"] == {}
    assert "foreign_net_ty" not in snap
    assert "deposit_top" not in snap


def test_build_snapshot_includes_vcb_ctd_when_provided():
    vcb = {"close": 58500, "change_pct": -1.2, "volume": 1.99}
    snap = build_snapshot(date="2026-07-27", ky="chieu", xau_usd=4110.6, fx_vcb_sell=26490.0,
                          vcb=vcb, ctd=None)
    assert snap["vcb"] == vcb
    assert "ctd" not in snap
