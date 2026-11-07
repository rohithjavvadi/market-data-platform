import sys
from datetime import date
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "spark"))
from bronze_to_silver_trades import transform

SCHEMA = (
    "trade_id string, symbol string, price double, qty double, "
    "conditions array<string>, side string, exchange string, ts string, "
    "ingested_at string, _raw string, _kafka_partition int, _kafka_offset long"
)


@pytest.fixture(scope="session")
def spark():
    s = (
        SparkSession.builder.master("local[1]")
        .appName("mdp-tests")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    s.sparkContext.setLogLevel("ERROR")
    yield s
    s.stop()


def row(tid="t1", sym="AAPL", price=100.0, qty=1.0, ts="2026-11-05T14:30:00.123Z", raw=None, part=0, off=1):
    return (tid, sym, price, qty, ["1"], None, "FINNHUB", ts, "2026-11-05T14:30:00.200Z", raw, part, off)


def run(spark, rows):
    return transform(spark.createDataFrame(rows, SCHEMA)).collect()


def test_dedupes_replayed_offsets(spark):
    out = run(spark, [row(off=1), row(off=1), row(off=2)])
    assert sorted(r.kafka_offset for r in out) == [1, 2]


def test_keeps_identical_prints_at_different_offsets(spark):
    out = run(spark, [row(tid="a", off=1), row(tid="b", off=2)])
    assert len(out) == 2


def test_same_offset_different_partitions_kept(spark):
    out = run(spark, [row(part=0, off=5), row(part=1, off=5)])
    assert len(out) == 2


@pytest.mark.parametrize(
    "bad",
    [
        row(tid=None, off=10),
        row(sym=None, off=11),
        row(price=0.0, off=12),
        row(qty=-1.0, off=13),
        row(ts=None, off=14),
        row(ts="not-a-time", off=15),
        row(raw="{garbage", off=16),
    ],
)
def test_drops_invalid_rows(spark, bad):
    assert run(spark, [bad]) == []


def test_trade_date_is_utc_event_date(spark):
    out = run(
        spark,
        [
            row(ts="2026-11-05T23:59:59.999Z", off=1),
            row(ts="2026-11-06T00:00:00.000Z", off=2),
        ],
    )
    dates = {r.kafka_offset: r.trade_date for r in out}
    assert dates == {1: date(2026, 11, 5), 2: date(2026, 11, 6)}


def test_output_columns(spark):
    out = transform(spark.createDataFrame([row()], SCHEMA))
    assert out.columns == [
        "trade_id",
        "symbol",
        "price",
        "qty",
        "conditions",
        "side",
        "exchange",
        "event_ts",
        "ingested_ts",
        "kafka_partition",
        "kafka_offset",
        "trade_date",
    ]
    assert dict(out.dtypes)["event_ts"] == "timestamp"
