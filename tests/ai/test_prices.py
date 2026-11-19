import statistics
from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from ai.agent.prices import get_price_stats

CLOSES = [100.0, 110.0, 99.0, 121.0, 110.0]


def _source(tmp_path) -> str:
    rets = [None] + [CLOSES[i] / CLOSES[i - 1] - 1 for i in range(1, len(CLOSES))]
    table = pa.table(
        {
            "ticker": ["ABC"] * len(CLOSES),
            "bar_date": [date(2026, 1, d) for d in range(1, len(CLOSES) + 1)],
            "adj_close": CLOSES,
            "daily_return": rets,
        }
    )
    path = tmp_path / "bars.parquet"
    pq.write_table(table, path)
    return str(path)


def test_stats(tmp_path):
    s = get_price_stats("abc", "ytd", source=_source(tmp_path))
    assert (s["start_date"], s["end_date"], s["trading_days"]) == (
        "2026-01-01",
        "2026-01-05",
        5,
    )
    assert s["total_return_pct"] == 10.0
    assert s["max_drawdown_pct"] == -10.0
    assert (s["high"], s["low"]) == (121.0, 99.0)
    rets = [CLOSES[i] / CLOSES[i - 1] - 1 for i in range(1, len(CLOSES))]
    assert s["ann_vol_pct"] == round(statistics.stdev(rets) * 252**0.5 * 100, 2)


def test_unknown_ticker(tmp_path):
    assert "error" in get_price_stats("ZZZ", source=_source(tmp_path))


def test_bad_period(tmp_path):
    with pytest.raises(ValueError):
        get_price_stats("ABC", "2w", source=_source(tmp_path))
