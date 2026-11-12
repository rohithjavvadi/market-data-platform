import numpy as np
import pyarrow.parquet as pq

from ai.agent.tools import search_filings
from ai.ingest.embed import to_table

ROWS = [
    ("AAPL", "10-K", "2026-11-03", "1A", "apple risk"),
    ("NVDA", "10-Q", "2026-08-26", "II-1A", "nvda risk"),
    ("MSFT", "10-K", "2026-07-29", "7", "msft mdna"),
]
EMB = np.array([[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
KEYS = ["ticker", "form", "filing_date", "item", "text"]


def _source(tmp_path) -> str:
    rows = [dict(zip(KEYS, r, strict=True), chunk_idx=0, context="c") for r in ROWS]
    emb = EMB / np.linalg.norm(EMB, axis=1, keepdims=True)
    pq.write_table(to_table(rows, emb), tmp_path / "chunks.parquet")
    return str(tmp_path / "*.parquet")


def enc(_q: str) -> list[float]:
    return [1.0, 0.0, 0.0]


def test_ranks_by_cosine(tmp_path):
    hits = search_filings("q", encode=enc, source=_source(tmp_path))
    assert [h["ticker"] for h in hits] == ["AAPL", "NVDA", "MSFT"]
    assert hits[0]["score"] == 1.0


def test_ticker_filter_is_case_insensitive(tmp_path):
    hits = search_filings("q", ticker="nvda", encode=enc, source=_source(tmp_path))
    assert [h["ticker"] for h in hits] == ["NVDA"]


def test_item_matches_10q_part_prefix(tmp_path):
    src = _source(tmp_path)
    one_a = search_filings("q", item="1a", encode=enc, source=src)
    seven = search_filings("q", item="7", encode=enc, source=src)
    assert {h["ticker"] for h in one_a} == {"AAPL", "NVDA"}
    assert [h["ticker"] for h in seven] == ["MSFT"]


def test_k_is_clamped(tmp_path):
    src = _source(tmp_path)
    assert len(search_filings("q", k=0, encode=enc, source=src)) == 1
    assert len(search_filings("q", k=100, encode=enc, source=src)) == 3
