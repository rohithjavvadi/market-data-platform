import json
from datetime import datetime, timezone
from decimal import Decimal


def trade_ts_ms(rec, fallback_ms):
    try:
        dt = datetime.fromisoformat(rec["ts"])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return int(fallback_ms)


def parse(value, fallback_ms):
    try:
        rec = json.loads(value)
        symbol = rec["symbol"]
        price = float(rec["price"])
    except Exception:
        return None
    if not symbol or price <= 0:
        return None
    return {
        "symbol": symbol,
        "price": price,
        "qty": float(rec.get("qty") or 0),
        "exchange": rec.get("exchange") or "UNKNOWN",
        "trade_id": str(rec.get("trade_id") or ""),
        "ts_ms": trade_ts_ms(rec, fallback_ms),
    }


def merge_latest(buffer, rec):
    cur = buffer.get(rec["symbol"])
    n = (cur["window_trades"] if cur else 0) + 1
    if cur is None or rec["ts_ms"] >= cur["ts_ms"]:
        buffer[rec["symbol"]] = {**rec, "window_trades": n}
    else:
        cur["window_trades"] = n


def build_update(rec, now_ms):
    iso = datetime.fromtimestamp(rec["ts_ms"] / 1000, timezone.utc).isoformat(timespec="milliseconds")
    return {
        "Key": {"symbol": rec["symbol"]},
        "UpdateExpression": (
            "SET price = :p, qty = :q, trade_ts_ms = :t, trade_ts = :iso, exchange = :e, "
            "trade_id = :id, updated_at_ms = :u ADD trades_seen :n"
        ),
        "ConditionExpression": "attribute_not_exists(trade_ts_ms) OR trade_ts_ms < :t",
        "ExpressionAttributeValues": {
            ":p": Decimal(str(rec["price"])),
            ":q": Decimal(str(rec["qty"])),
            ":t": rec["ts_ms"],
            ":iso": iso,
            ":e": rec["exchange"],
            ":id": rec["trade_id"],
            ":u": now_ms,
            ":n": rec["window_trades"],
        },
    }
