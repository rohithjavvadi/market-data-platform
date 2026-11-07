from pyspark.sql import SparkSession

spark = (
    SparkSession.builder.master("local[*]")
    .appName("mdp-smoke-s3a")
    .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.5.0")
    .config(
        "spark.hadoop.fs.s3a.aws.credentials.provider",
        "software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider",
    )
    .config("spark.hadoop.fs.s3a.endpoint.region", "us-east-2")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")

df = spark.read.option("pathGlobFilter", "*.parquet").parquet("s3a://mdp-bronze-388260576625/trades/dt=2026-11-05/")
df.printSchema()
print("rows", df.count())
df.groupBy("symbol").count().orderBy("symbol").show()
spark.stop()
