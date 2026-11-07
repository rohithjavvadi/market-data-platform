import argparse
import io
import os
import time
from datetime import date, datetime, timedelta, timezone

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from dotenv import load_dotenv

load_dotenv()

URL = "https://api.tiingo.com/tiingo/daily/{ticker}/prices"

SCHEMA = pa.schema(
    [
        ("ticker", pa.string()),
        ("date", pa.string()),
        ("open", pa.float64()),
        ("high", pa.float64()),
        ("low", pa.float64()),
        ("close", pa.float64()),
        ("volume", pa.float64()),
        ("adjOpen", pa.float64()),
        ("adjHigh", pa.float64()),
        ("adjLow", pa.float64()),
        ("adjClose", pa.float64()),
        ("adjVolume", pa.float64()),
        ("divCash", pa.float64()),
        ("splitFactor", pa.float64()),
        ("source", pa.string()),
        ("ingested_at", pa.string()),
    ]
)


def fetch(session, ticker, start, end, tries=5):
    wait = 2
    for attempt in range(tries):
        r = session.get(
            URL.format(ticker=ticker), params={"startDate": start, "endDate": end, "format": "json"}, timeout=60
        )
        if r.status_code == 200:
            data = r.json()
            if not isinstance(data, list):
                raise RuntimeError(f"{ticker}: unexpected response: {str(data)[:200]}")
            return data
        if r.status_code in (429, 500, 502, 503, 504) and attempt < tries - 1:
            time.sleep(wait)
            wait *= 2
            continue
        raise RuntimeError(f"{ticker}: HTTP {r.status_code}: {r.text[:200]}")
    raise RuntimeError(f"{ticker}: failed after retries")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="AAPL,MSFT,NVDA,AMZN,GOOGL")
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("--days", type=int, default=0, help="if >0, fetch only the last N calendar days")
    ap.add_argument("--bucket", default="mdp-bronze-388260576625")
    ap.add_argument("--prefix", default="daily_bars/source=tiingo")
    ap.add_argument("--region", default="us-east-2")
    args = ap.parse_args()

    key = os.environ.get("TIINGO_API_KEY", "").strip()
    if not key:
        raise SystemExit("Set TIINGO_API_KEY in .env")

    end = date.today()
    start = end - timedelta(days=args.days) if args.days else end - timedelta(days=365 * args.years + 2)
    session = requests.Session()
    session.headers.update({"Authorization": f"Token {key}", "Content-Type": "application/json"})
    s3 = boto3.client("s3", region_name=args.region)
    ingested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    totals = {"files": 0, "rows": 0, "bytes": 0}
    for ticker in [t.strip().upper() for t in args.tickers.split(",") if t.strip()]:
        rows = fetch(session, ticker, start.isoformat(), end.isoformat())
        recs = [
            {
                **{k: r.get(k) for k in SCHEMA.names},
                "ticker": ticker,
                "date": str(r["date"])[:10],
                "source": "tiingo",
                "ingested_at": ingested_at,
            }
            for r in rows
        ]
        out = io.BytesIO()
        pq.write_table(pa.Table.from_pylist(recs, schema=SCHEMA), out, compression="snappy")
        body = out.getvalue()
        s3_key = f"{args.prefix}/ticker={ticker}/bars_{start.isoformat()}_{end.isoformat()}.parquet"
        s3.put_object(Bucket=args.bucket, Key=s3_key, Body=body, ContentType="application/vnd.apache.parquet")
        first = recs[0]["date"] if recs else "-"
        last = recs[-1]["date"] if recs else "-"
        print(f"wrote s3://{args.bucket}/{s3_key} ({len(recs)} rows, {first}..{last}, {len(body)} bytes)")
        totals["files"] += 1
        totals["rows"] += len(recs)
        totals["bytes"] += len(body)
        time.sleep(1)

    print(f"done: files={totals['files']} rows={totals['rows']} bytes={totals['bytes']}")


if __name__ == "__main__":
    main()
