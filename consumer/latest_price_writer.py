import argparse
import signal
import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from confluent_kafka import Consumer, KafkaException
from latest_price_logic import build_update, merge_latest, parse


def flush(table, buffer, stats):
    now_ms = int(time.time() * 1000)
    for rec in buffer.values():
        try:
            table.update_item(**build_update(rec, now_ms))
            stats["writes"] += 1
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                stats["stale"] += 1
            else:
                raise
    buffer.clear()


def commit(consumer):
    try:
        consumer.commit(asynchronous=False)
    except KafkaException:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", default="localhost:19092")
    ap.add_argument("--topic", default="trades.raw")
    ap.add_argument("--group", default="mdp-latest-price")
    ap.add_argument("--table", default="mdp-latest-price")
    ap.add_argument("--region", default="us-east-2")
    ap.add_argument("--flush-seconds", type=float, default=5.0)
    args = ap.parse_args()

    cfg = Config(retries={"max_attempts": 10, "mode": "standard"})
    table = boto3.resource("dynamodb", region_name=args.region, config=cfg).Table(args.table)
    consumer = Consumer(
        {
            "bootstrap.servers": args.bootstrap,
            "group.id": args.group,
            "enable.auto.commit": False,
            "auto.offset.reset": "latest",
        }
    )
    consumer.subscribe([args.topic])

    stop = False

    def handle(_sig, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)

    buffer = {}
    stats = {"msgs": 0, "bad": 0, "writes": 0, "stale": 0}
    last_flush = time.monotonic()
    flushes = 0
    try:
        while not stop:
            msg = consumer.poll(1.0)
            if msg is not None:
                if msg.error():
                    print(f"kafka error: {msg.error()}")
                else:
                    stats["msgs"] += 1
                    rec = parse(msg.value(), msg.timestamp()[1])
                    if rec is None:
                        stats["bad"] += 1
                    else:
                        merge_latest(buffer, rec)
            if time.monotonic() - last_flush >= args.flush_seconds:
                flush(table, buffer, stats)
                commit(consumer)
                last_flush = time.monotonic()
                flushes += 1
                if flushes % 12 == 0:
                    print(" ".join(f"{k}={v}" for k, v in stats.items()))
    finally:
        flush(table, buffer, stats)
        commit(consumer)
        consumer.close()
        print("done: " + " ".join(f"{k}={v}" for k, v in stats.items()))


if __name__ == "__main__":
    main()
