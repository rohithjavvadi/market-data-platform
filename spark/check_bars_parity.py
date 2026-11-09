import argparse
import os
import sys
from datetime import date, datetime, timedelta, timezone

import snowflake.connector
from bronze_to_silver_trades import build_spark
from pyspark.sql import functions as F

BARS = "s3a://mdp-silver-388260576625/bars_1m"
COLS = ["open", "high", "low", "close", "volume", "vwap", "trade_count"]
TIE_COLS = set()
FMT = "%Y-%m-%d %H:%M"


def snowflake_bars(day, cutoff):
    conn = snowflake.connector.connect(
        account="VZKISNL-UC48480",
        user="DBT_SVC",
        authenticator="SNOWFLAKE_JWT",
        private_key_file=os.path.expanduser("~/.snowflake/dbt_svc_key.p8"),
        role="TRANSFORMER",
        warehouse="MDP_WH",
    )
    try:
        cur = conn.cursor()
        cur.execute("alter session set timezone = 'UTC'")
        cur.execute(
            """
            select bar_key, open, high, low, close, volume, vwap, trade_count
            from ANALYTICS.PROD_MARTS.FCT_OHLCV_1M
            where to_varchar(bar_ts_utc, 'YYYY-MM-DD HH24:MI') >= %s
              and to_varchar(bar_ts_utc, 'YYYY-MM-DD HH24:MI') < %s
            """,
            (f"{day} 00:00", cutoff),
        )
        return [(r[0], *(float(v) if v is not None else None for v in r[1:7]), int(r[7])) for r in cur.fetchall()]
    finally:
        conn.close()


def split_key(df):
    parts = F.split("bar_key", r"\|")
    return df.withColumn("symbol", parts.getItem(0)).withColumn("k", parts.getItem(1))


def watermark_filter(lake, wh):
    """Keep only bars strictly older than the newest bar both sides have for that symbol.

    Each symbol's trades live in one ordered Kafka partition, so every bar before the
    common watermark is complete in both systems; later bars may still be in flight.
    """
    lake_s, wh_s = split_key(lake), split_key(wh)
    wm = (
        lake_s.groupBy("symbol")
        .agg(F.max("k").alias("lake_wm"))
        .join(wh_s.groupBy("symbol").agg(F.max("k").alias("wh_wm")), "symbol", "full_outer")
        .select("symbol", "lake_wm", "wh_wm", F.least("lake_wm", "wh_wm").alias("wm"))
    )

    def keep(df):
        return df.join(wm.select("symbol", "wm"), "symbol").where(F.col("k") < F.col("wm")).drop("symbol", "k", "wm")

    return keep(lake_s), keep(wh_s), wm


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    p.add_argument("--lag-minutes", type=int, default=30)
    a = p.parse_args()
    day = date.fromisoformat(a.date)
    now_cut = (datetime.now(timezone.utc) - timedelta(minutes=a.lag_minutes)).strftime(FMT)
    cutoff = min(now_cut, f"{day + timedelta(days=1)} 00:00")

    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")

    lake = (
        spark.read.parquet(BARS)
        .where(F.col("trade_date") == F.lit(day))
        .withColumn("k", F.date_format("bar_ts", "yyyy-MM-dd HH:mm"))
        .where(F.col("k") < F.lit(cutoff))
        .select(
            F.concat_ws("|", "symbol", "k").alias("bar_key"),
            *[F.col(c).cast("double" if c != "trade_count" else "long").alias(c) for c in COLS],
        )
    )
    wh = spark.createDataFrame(
        snowflake_bars(day, cutoff),
        "bar_key string, open double, high double, low double, close double, "
        "volume double, vwap double, trade_count long",
    )

    lake, wh, wm = watermark_filter(lake, wh)
    wm.orderBy("symbol").show(20, False)

    j = lake.alias("s").join(wh.alias("w"), "bar_key", "full_outer").cache()
    only_spark = j.where(F.col("w.trade_count").isNull()).count()
    only_wh = j.where(F.col("s.trade_count").isNull()).count()
    both = j.where(F.col("s.trade_count").isNotNull() & F.col("w.trade_count").isNotNull())

    def differs(c):
        s, w = F.col(f"s.{c}"), F.col(f"w.{c}")
        if c == "trade_count":
            return s != w
        return F.abs(s - w) > F.greatest(F.lit(1e-9), F.abs(w) * 1e-9)

    print(f"date {day}  bars before {cutoff} UTC")
    print(f"spark {lake.count()}  snowflake {wh.count()}  matched {both.count()}")
    print(f"only_spark {only_spark}  only_snowflake {only_wh}")
    hard = 0
    for c in COLS:
        n = both.where(differs(c)).count()
        tag = " (same-ms tie-break, informational)" if c in TIE_COLS else ""
        print(f"  {c:<12} mismatches {n}{tag}")
        if c not in TIE_COLS:
            hard += n
    if hard or only_spark or only_wh:
        bad = both.where(F.greatest(*[differs(c).cast("int") for c in COLS if c not in TIE_COLS]) == 1)
        bad.select(
            "bar_key", *[F.col(f"{x}.{c}").alias(f"{x}_{c}") for c in ["volume", "trade_count"] for x in "sw"]
        ).show(5, False)
        j.where(F.col("w.trade_count").isNull() | F.col("s.trade_count").isNull()).select("bar_key").show(5, False)
    spark.stop()
    status = "PASS" if not (hard or only_spark or only_wh) else "FAIL"
    print(status)
    sys.exit(0 if status == "PASS" else 1)


if __name__ == "__main__":
    main()
