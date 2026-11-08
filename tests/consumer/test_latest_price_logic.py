from decimal import Decimal

from latest_price_logic import build_update, merge_latest, parse


def rec(symbol, ts_ms, price=100.0):
    return {"symbol": symbol, "price": price, "qty": 1.0, "exchange": "FINNHUB", "trade_id": "x", "ts_ms": ts_ms}


def test_parse_valid_and_naive_ts_is_utc():
    r = parse(b'{"symbol":"AAPL","price":"190.5","qty":3,"ts":"2026-11-09T14:30:00"}', 0)
    assert r["symbol"] == "AAPL" and r["price"] == 190.5 and r["qty"] == 3.0
    assert r["ts_ms"] == 1794234600000


def test_parse_rejects_bad_json_and_nonpositive_price():
    assert parse(b"not json", 0) is None
    assert parse(b'{"symbol":"AAPL","price":0}', 0) is None
    assert parse(b'{"price":1}', 0) is None


def test_parse_falls_back_to_kafka_ts():
    assert parse(b'{"symbol":"AAPL","price":1}', 1234)["ts_ms"] == 1234


def test_merge_keeps_newest_and_counts_all():
    buf = {}
    merge_latest(buf, rec("AAPL", 2000, 101.0))
    merge_latest(buf, rec("AAPL", 1000, 99.0))
    merge_latest(buf, rec("BTC", 5000))
    assert buf["AAPL"]["price"] == 101.0
    assert buf["AAPL"]["window_trades"] == 2
    assert buf["BTC"]["window_trades"] == 1


def test_build_update_is_conditional_and_uses_decimal():
    buf = {}
    merge_latest(buf, rec("AAPL", 1794234600000, 190.5))
    u = build_update(buf["AAPL"], 1794234601000)
    assert u["Key"] == {"symbol": "AAPL"}
    assert "trade_ts_ms < :t" in u["ConditionExpression"]
    assert u["ExpressionAttributeValues"][":p"] == Decimal("190.5")
    assert u["ExpressionAttributeValues"][":iso"].startswith("2026-11-09T14:30:00.000")
