import argparse
import json
import os
import threading
import uuid
from datetime import datetime, timezone

import websocket
from confluent_kafka import Producer
from dotenv import load_dotenv

load_dotenv()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", default="localhost:19092")
    ap.add_argument("--topic", default="trades.raw")
    ap.add_argument("--symbols", default="AAPL,MSFT,NVDA,AMZN,GOOGL,BINANCE:BTCUSDT")
    ap.add_argument("--seconds", type=int, default=0, help="0 = run until Ctrl+C")
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
    stats = {"recv": 0, "ok": 0, "err": 0}

    def on_delivery(err, msg):
        if err:
            stats["err"] += 1
            print(f"delivery failed: {err}")
        else:
            stats["ok"] += 1

    def on_open(ws):
        for s in symbols:
            ws.send(json.dumps({"type": "subscribe", "symbol": s}))
        print(f"subscribed: {symbols}")

    def on_message(ws, raw):
        msg = json.loads(raw)
        if msg.get("type") != "trade":
            return
        for t in msg.get("data", []):
            trade = {
                "trade_id": str(uuid.uuid4()),
                "symbol": t["s"],
                "price": t["p"],
                "qty": t["v"],
                "conditions": t.get("c") or [],
                "exchange": "FINNHUB",
                "ts": datetime.fromtimestamp(t["t"] / 1000, timezone.utc).isoformat(timespec="milliseconds"),
                "ingested_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            }
            producer.produce(args.topic, key=trade["symbol"], value=json.dumps(trade), on_delivery=on_delivery)
            stats["recv"] += 1
        producer.poll(0)
        if stats["recv"] and stats["recv"] % 100 < len(msg.get("data", [])):
            print(f"recv={stats['recv']} ok={stats['ok']} err={stats['err']}")

    def on_error(ws, err):
        print(f"ws error: {err}")

    ws = websocket.WebSocketApp(
        f"wss://ws.finnhub.io?token={api_key}",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
    )
    if args.seconds:
        threading.Timer(args.seconds, ws.close).start()
    try:
        ws.run_forever(ping_interval=30, reconnect=5)
    finally:
        producer.flush(10)
        print(f"done: recv={stats['recv']} ok={stats['ok']} err={stats['err']}")


if __name__ == "__main__":
    main()
