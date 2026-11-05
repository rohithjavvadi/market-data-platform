import argparse
import gzip
import json
import signal
import time
from collections import defaultdict
from datetime import datetime, timezone

import boto3
from confluent_kafka import Consumer, TopicPartition


def parse_ts(rec, fallback_ms):
    try:
        return datetime.fromisoformat(rec["ts"]).astimezone(timezone.utc)
    except Exception:
        return datetime.fromtimestamp(fallback_ms / 1000, timezone.utc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", default="localhost:19092")
    ap.add_argument("--topic", default="trades.raw")
    ap.add_argument("--group", default="mdp-bronze-writer")
    ap.add_argument("--bucket", default="mdp-bronze-388260576625")
    ap.add_argument("--prefix", default="trades")
    ap.add_argument("--region", default="us-east-2")
    ap.add_argument("--max-records", type=int, default=1000)
    ap.add_argument("--max-seconds", type=int, default=60)
    ap.add_argument("--idle-exit", type=int, default=0, help="exit after N idle seconds; 0 = never")
    args = ap.parse_args()

    s3 = boto3.client("s3", region_name=args.region)
    consumer = Consumer({
        "bootstrap.servers": args.bootstrap,
        "group.id": args.group,
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe([args.topic])

    buf = defaultdict(list)
    state = {"count": 0, "last_flush": time.time(), "last_msg": time.time(), "files": 0, "records": 0}
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    def flush():
        commits = []
        for p, items in buf.items():
            if not items:
                continue
            first, last = items[0][0], items[-1][0]
            groups = defaultdict(list)
            for _, rec, dt in items:
                groups[(dt.strftime("%Y-%m-%d"), dt.strftime("%H"))].append(rec)
            for (d, h), recs in groups.items():
                body = gzip.compress(("\n".join(json.dumps(r) for r in recs) + "\n").encode())
                key = f"{args.prefix}/dt={d}/hour={h}/p{p}-{first:012d}-{last:012d}.json.gz"
                s3.put_object(Bucket=args.bucket, Key=key, Body=body, ContentType="application/gzip")
                state["files"] += 1
                state["records"] += len(recs)
                print(f"wrote s3://{args.bucket}/{key} ({len(recs)} records)")
            commits.append(TopicPartition(args.topic, p, last + 1))
        if commits:
            consumer.commit(offsets=commits, asynchronous=False)
        buf.clear()
        state["count"] = 0
        state["last_flush"] = time.time()

    try:
        while running:
            msg = consumer.poll(1.0)
            now = time.time()
            if msg is None:
                if args.idle_exit and now - state["last_msg"] >= args.idle_exit:
                    break
            elif msg.error():
                print(f"consumer error: {msg.error()}")
            else:
                state["last_msg"] = now
                _, kafka_ts = msg.timestamp()
                try:
                    rec = json.loads(msg.value())
                except Exception:
                    rec = {"_raw": msg.value().decode("utf-8", "replace")}
                rec["_kafka_partition"] = msg.partition()
                rec["_kafka_offset"] = msg.offset()
                rec["_kafka_ts"] = kafka_ts
                buf[msg.partition()].append((msg.offset(), rec, parse_ts(rec, kafka_ts)))
                state["count"] += 1
            if state["count"] >= args.max_records or (state["count"] and now - state["last_flush"] >= args.max_seconds):
                flush()
    finally:
        flush()
        consumer.close()
        print(f"done: files={state['files']} records={state['records']}")


if __name__ == "__main__":
    main()
