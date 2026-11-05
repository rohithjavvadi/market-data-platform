import sys
from datetime import datetime
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "spark"))
from silver_to_bars_1m import to_bars

SCHEMA = "symbol string, price double, qty double, event_ts timestamp, kafka_partition int, kafka_offset long"


@pytest.fixture(scope="module")
def spark():
    s = (
        SparkSession.builder.master("local[1]")
        .appName("mdp-tests-bars")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    s.sparkContext.setLogLevel("ERROR")
    yield s


def ts(s):
    return datetime.fromisoformat(s)


def bars(spark, rows):
    return {(r.symbol, r.bar_ts): r for r in to_bars(spark.createDataFrame(rows, SCHEMA)).collect()}


def test_ohlcv_vwap_count(spark):
    rows = [
        ("AAPL", 10.0, 1.0, ts("2026-11-05 14:30:05"), 0, 1),
        ("AAPL", 12.0, 2.0, ts("2026-11-05 14:30:20"), 0, 2),
        ("AAPL", 9.0, 1.0, ts("2026-11-05 14:30:40"), 0, 3),
        ("AAPL", 11.0, 4.0, ts("2026-11-05 14:30:59"), 0, 4),
    ]
    b = bars(spark, rows)[("AAPL", ts("2026-11-05 14:30:00"))]
    assert (b.open, b.high, b.low, b.close) == (10.0, 12.0, 9.0, 11.0)
    assert b.volume == 8.0
    assert b.trade_count == 4
    assert b.vwap == pytest.approx((10 + 24 + 9 + 44) / 8)


def test_open_close_use_event_time_not_offset(spark):
    rows = [
        ("AAPL", 20.0, 1.0, ts("2026-11-05 14:30:50"), 0, 1),
        ("AAPL", 10.0, 1.0, ts("2026-11-05 14:30:10"), 0, 2),
    ]
    b = bars(spark, rows)[("AAPL", ts("2026-11-05 14:30:00"))]
    assert (b.open, b.close) == (10.0, 20.0)


def test_same_ms_tie_broken_by_offset(spark):
    t = ts("2026-11-05 14:30:10")
    rows = [("AAPL", 10.0, 1.0, t, 0, 1), ("AAPL", 20.0, 1.0, t, 0, 2)]
    b = bars(spark, rows)[("AAPL", ts("2026-11-05 14:30:00"))]
    assert (b.open, b.close) == (10.0, 20.0)


def test_minute_and_symbol_buckets(spark):
    rows = [
        ("AAPL", 10.0, 1.0, ts("2026-11-05 14:30:59.999"), 0, 1),
        ("AAPL", 11.0, 1.0, ts("2026-11-05 14:31:00"), 0, 2),
        ("MSFT", 50.0, 1.0, ts("2026-11-05 14:30:30"), 1, 1),
    ]
    b = bars(spark, rows)
    assert set(b) == {
        ("AAPL", ts("2026-11-05 14:30:00")),
        ("AAPL", ts("2026-11-05 14:31:00")),
        ("MSFT", ts("2026-11-05 14:30:00")),
    }


def test_trade_date_from_bar(spark):
    rows = [("AAPL", 10.0, 1.0, ts("2026-11-05 23:59:30"), 0, 1)]
    b = bars(spark, rows)[("AAPL", ts("2026-11-05 23:59:00"))]
    assert str(b.trade_date) == "2026-11-05"
