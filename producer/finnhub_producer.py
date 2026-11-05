import argparse
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone

import websocket
from confluent_kafka import Producer
from dotenv import load_dotenv

load_dotenv()

REQUIRED = ("s", "p", "v", "t")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def to_trade(t):
    missing = [k for k in REQUIRED if k not in t]
    if missing:
        raise ValueError(f"missing fields: {missing}")
    price, qty = float(t["p"]), float(t["v"])
    if price <= 0 or qty <= 0:
        raise ValueError(f"non-positive price/qty: {price}/{qty}")
    return {
        "trade_id": str(uuid.uuid4()),
        "symbol": t["s"],
        "price": price,
        "qty": qty,
        "conditions": t.get("c") or [],
        "exchange": "FINNHUB",
        "ts": datetime.fromtimestamp(int(t["t"]) / 1000, timezone.utc).isoformat(timespec="milliseconds"),
        "ingested_at": now_iso(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", default="localhost:19092")
    ap.add_argument("--topic", default="trades.raw")
    ap.add_argument("--dlq-topic", default="trades.dlq")
    ap.add_argument("--symbols", default="AAPL,MSFT,NVDA,AMZN,GOOGL,BINANCE:BTCUSDT")
    ap.add_argument("--seconds", type=int, default=0, help="0 = run until Ctrl+C")
    ap.add_argument("--max-backoff", type=int, default=60)
    args = ap.parse_args()

    api_key = os.environ["MARKET_API_KEY"]
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    producer = Producer({
        "bootstrap.servers": args.bootstrap,
        "enable.idempotence": True,
        "acks": "all",
        "linger.ms": 20,
        "compression.type": "lz4",
    })
    stats = {"recv": 0, "ok": 0, "err": 0, "dlq": 0, "reconnects": 0}
    stop = threading.Event()
    state = {"ws": None, "backoff": 1}

    def on_delivery(err, msg):
        if err:
            stats["err"] += 1
            print(f"delivery failed: {err}")
        else:
            stats["ok"] += 1

    def to_dlq(raw, error):
        producer.produce(args.dlq_topic, value=json.dumps({"error": str(error), "raw": raw, "at": now_iso()}))
        stats["dlq"] += 1

    def on_open(ws):
        for s in symbols:
            ws.send(json.dumps({"type": "subscribe", "symbol": s}))
        print(f"subscribed: {symbols}")

    def on_message(ws, raw):
        try:
            msg = json.loads(raw)
        except Exception as e:
            to_dlq(raw if isinstance(raw, str) else repr(raw), e)
            return
        if msg.get("type") != "trade":
            return
        state["backoff"] = 1
        for t in msg.get("data", []):
            try:
                trade = to_trade(t)
            except Exception as e:
                to_dlq(json.dumps(t), e)
                continue
            producer.produce(args.topic, key=trade["symbol"], value=json.dumps(trade), on_delivery=on_delivery)
            stats["recv"] += 1
            if stats["recv"] % 100 == 0:
                print(f"recv={stats['recv']} ok={stats['ok']} err={stats['err']} dlq={stats['dlq']}")
        producer.poll(0)

    def on_error(ws, err):
        print(f"ws error: {err}")

    def shutdown():
        stop.set()
        if state["ws"]:
            state["ws"].close()

    if args.seconds:
        threading.Timer(args.seconds, shutdown).start()

    try:
        while not stop.is_set():
            ws = websocket.WebSocketApp(
                f"wss://ws.finnhub.io?token={api_key}",
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
            )
            state["ws"] = ws
            ws.run_forever(ping_interval=30, ping_timeout=10)
            if stop.is_set():
                break
            stats["reconnects"] += 1
            wait = state["backoff"]
            print(f"disconnected; reconnecting in {wait}s")
            stop.wait(wait)
            state["backoff"] = min(state["backoff"] * 2, args.max_backoff)
    except KeyboardInterrupt:
        pass
    finally:
        producer.flush(10)
        print(f"done: recv={stats['recv']} ok={stats['ok']} err={stats['err']} dlq={stats['dlq']} reconnects={stats['reconnects']}")


if __name__ == "__main__":
    main()
