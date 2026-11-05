import argparse
import gzip
import json
import os
import time
from datetime import datetime, timezone

import boto3
import requests
from dotenv import load_dotenv

load_dotenv()

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def get(session, url, tries=5):
    wait = 1
    for attempt in range(tries):
        r = session.get(url, timeout=30)
        if r.status_code == 200:
            return r.content
        if r.status_code in (429, 500, 502, 503, 504) and attempt < tries - 1:
            time.sleep(wait)
            wait *= 2
            continue
        r.raise_for_status()
    raise RuntimeError(f"failed: {url}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="AAPL,MSFT,NVDA,AMZN,GOOGL")
    ap.add_argument("--bucket", default="mdp-bronze-388260576625")
    ap.add_argument("--prefix", default="edgar")
    ap.add_argument("--region", default="us-east-2")
    ap.add_argument("--dt", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    args = ap.parse_args()

    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in ua:
        raise SystemExit("Set SEC_USER_AGENT in .env to 'Your Name your-email'")

    session = requests.Session()
    session.headers.update({"User-Agent": ua, "Accept-Encoding": "gzip, deflate"})
    s3 = boto3.client("s3", region_name=args.region)

    mapping = json.loads(get(session, TICKERS_URL))
    cik_by_ticker = {v["ticker"].upper(): f"{int(v['cik_str']):010d}" for v in mapping.values()}

    totals = {"files": 0, "bytes": 0}
    for ticker in [t.strip().upper() for t in args.tickers.split(",") if t.strip()]:
        cik = cik_by_ticker.get(ticker)
        if not cik:
            print(f"skip {ticker}: no CIK")
            continue
        for kind, url in (("submissions", SUBMISSIONS_URL), ("companyfacts", FACTS_URL)):
            raw = get(session, url.format(cik=cik))
            body = gzip.compress(raw)
            key = f"{args.prefix}/{kind}/dt={args.dt}/ticker={ticker}/CIK{cik}.json.gz"
            s3.put_object(Bucket=args.bucket, Key=key, Body=body, ContentType="application/gzip")
            totals["files"] += 1
            totals["bytes"] += len(body)
            print(f"wrote s3://{args.bucket}/{key} ({len(raw)} raw bytes, {len(body)} gz)")
            time.sleep(0.15)

    print(f"done: files={totals['files']} bytes={totals['bytes']}")


if __name__ == "__main__":
    main()
