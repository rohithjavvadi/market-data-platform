import numpy as np
import pyarrow as pa

from ai.ingest.embed import MODEL_ID, build_rows, fit_to_limit, to_table

HTML = "".join(
    f"<p>{x}</p>"
    for x in ["Item 1. Business", "word " * 300, "Item 1A. Risk Factors", "risk " * 10]
)


def test_build_rows_items_and_chunk_idx():
    rows = build_rows("AAPL", {"form": "10-K", "filing_date": "2026-11-03"}, HTML)
    assert [(r["item"], r["chunk_idx"]) for r in rows] == [
        ("1", 0),
        ("1", 1),
        ("1A", 0),
    ]
    assert {r["ticker"] for r in rows} == {"AAPL"}


def test_to_table_schema():
    rows = [
        {"ticker": "AAPL", "item": "1", "chunk_idx": i, "text": "a"} for i in range(2)
    ]
    t = to_table(rows, np.ones((2, 384)))
    assert t.num_rows == 2
    assert t.schema.field("embedding").type == pa.list_(pa.float32(), 384)
    assert t.column("model").to_pylist() == [MODEL_ID, MODEL_ID]


def test_fit_to_limit_halves_until_within_limit():
    def words(s: str) -> int:
        return len(s.split())

    assert fit_to_limit("a b c d e f g", words, limit=3) == ["a b c", "d e", "f g"]
    assert fit_to_limit("a b", words, limit=3) == ["a b"]