import argparse
from datetime import date, timedelta

from bronze_to_silver_trades import build_spark
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

TRADES = "s3a://mdp-silver-388260576625/trades"
BARS = "s3a://mdp-silver-388260576625/bars_1m"


def to_bars(df: DataFrame) -> DataFrame:
    order = F.struct("event_ts", "kafka_partition", "kafka_offset")
    return (
        df.withColumn("bar_ts", F.date_trunc("minute", "event_ts"))
        .groupBy("symbol", "bar_ts")
        .agg(
            F.min_by("price", order).alias("open"),
            F.max("price").alias("high"),
            F.min("price").alias("low"),
            F.max_by("price", order).alias("close"),
            F.sum("qty").alias("volume"),
            (F.sum(F.col("price") * F.col("qty")) / F.sum("qty")).alias("vwap"),
            F.count("*").alias("trade_count"),
        )
        .withColumn("trade_date", F.to_date("bar_ts"))
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--end", default=date.today().isoformat())
    p.add_argument("--days", type=int, default=2)
    a = p.parse_args()
    end = date.fromisoformat(a.end)
    start = end - timedelta(days=a.days - 1)

    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")
    trades = spark.read.parquet(TRADES).where(F.col("trade_date").between(F.lit(start), F.lit(end)))
    bars = to_bars(trades).cache()
    bars.repartition("trade_date").write.mode("overwrite").partitionBy("trade_date").parquet(BARS)
    print("dates", start, "->", end, "bars", bars.count())
    bars.groupBy("symbol").count().orderBy("symbol").show()
    spark.stop()


if __name__ == "__main__":
    main()
