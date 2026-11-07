import argparse
from datetime import date, timedelta

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

BRONZE = "s3a://mdp-bronze-388260576625/trades"
SILVER = "s3a://mdp-silver-388260576625/trades"


def build_spark() -> SparkSession:
    return (
        SparkSession.builder.master("local[*]")
        .appName("mdp-bronze-to-silver-trades")
        .config("spark.driver.memory", "4g")
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.5.0")
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider",
        )
        .config("spark.hadoop.fs.s3a.endpoint.region", "us-east-2")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .getOrCreate()
    )


def transform(df: DataFrame) -> DataFrame:
    if "_raw" in df.columns:
        df = df.where(F.col("_raw").isNull())
    typed = df.select(
        F.col("trade_id"),
        F.col("symbol"),
        F.col("price").cast("double").alias("price"),
        F.col("qty").cast("double").alias("qty"),
        F.col("conditions"),
        F.col("side"),
        F.col("exchange"),
        F.col("ts").try_cast("timestamp").alias("event_ts"),
        F.col("ingested_at").try_cast("timestamp").alias("ingested_ts"),
        F.col("_kafka_partition").cast("int").alias("kafka_partition"),
        F.col("_kafka_offset").cast("long").alias("kafka_offset"),
    )
    clean = typed.where(
        F.col("trade_id").isNotNull()
        & F.col("symbol").isNotNull()
        & F.col("event_ts").isNotNull()
        & (F.col("price") > 0)
        & (F.col("qty") > 0)
    )
    return clean.dropDuplicates(["kafka_partition", "kafka_offset"]).withColumn("trade_date", F.to_date("event_ts"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--end", default=date.today().isoformat())
    p.add_argument("--days", type=int, default=2)
    a = p.parse_args()
    end = date.fromisoformat(a.end)
    start = end - timedelta(days=a.days - 1)

    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")
    bronze = (
        spark.read.option("pathGlobFilter", "*.parquet")
        .parquet(BRONZE)
        .where(F.col("dt").between(F.lit(start), F.lit(end)))
        .drop("dt", "hour")
    )
    silver = transform(bronze).cache()
    silver.repartition("trade_date").write.mode("overwrite").partitionBy("trade_date").parquet(SILVER)
    print("dates", start, "->", end, "bronze rows", bronze.count(), "silver rows", silver.count())
    spark.stop()


if __name__ == "__main__":
    main()
