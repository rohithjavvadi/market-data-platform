import json
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pandas as pd
import queries as Q
import snowflake.connector

HERE = Path(__file__).parent
OUT = HERE / "snapshot"
DATASETS = {
    "dim_security_current": Q.DIM_SECURITY_CURRENT,
    "daily_bars": Q.DAILY_BARS_ALL,
    "ohlcv_1m": Q.OHLCV_RECENT_ALL,
    "health": Q.HEALTH,
}


def main():
    secrets = tomllib.loads((HERE / ".streamlit" / "secrets.toml").read_text())
    OUT.mkdir(exist_ok=True)
    con = snowflake.connector.connect(**Q.connect_kwargs(secrets["snowflake"]))
    cur = con.cursor()
    for name, sql in DATASETS.items():
        cur.execute(sql)
        df = cur.fetch_pandas_all()
        df.columns = [c.lower() for c in df.columns]
        df.to_parquet(OUT / f"{name}.parquet", index=False)
        print(f"{name}: {len(df):,} rows")
    con.close()

    a = secrets["aws"]
    table = boto3.resource(
        "dynamodb",
        region_name=a.get("region", "us-east-2"),
        aws_access_key_id=a["access_key_id"],
        aws_secret_access_key=a["secret_access_key"],
    ).Table(a.get("table", "mdp-latest-price"))
    prices = pd.DataFrame(Q.price_rows(table.scan().get("Items", [])))
    prices.to_parquet(OUT / "latest_price.parquet", index=False)
    print(f"latest_price: {len(prices)} rows")

    meta = {"exported_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"meta: {meta}")


if __name__ == "__main__":
    main()
