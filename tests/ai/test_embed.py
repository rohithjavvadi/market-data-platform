import numpy as np
import pyarrow as pa

from ai.ingest.embed import MODEL_ID, build_rows, embed_text, fit_to_limit, to_table

HTML = "".join(f"<p>{x}</p>" for x in ["Item 1. Business", "word " * 300, "Item 1A. Risk Factors", "risk " * 10])
FILING = {"form": "10-K", "filing_date": "2026-11-03"}


def test_build_rows_items_and_chunk_idx():
    rows = build_rows("AAPL", FILING, HTML)
    assert [(r["item"], r["chunk_idx"]) for r in rows] == [
        ("1", 0),
        ("1", 1),
        ("1A", 0),
    ]
    assert {r["ticker"] for r in rows} == {"AAPL"}


def test_context_line():
    row = build_rows("AAPL", FILING, HTML)[-1]
    assert row["context"] == "Apple (AAPL) 10-K filed 2026-11-03, Item 1A. Risk Factors"
    assert embed_text(row).startswith(row["context"] + "\n")
    assert not row["text"].startswith("Apple")


def test_context_counts_toward_token_limit():
    def words_x2(s: str) -> int:
        return 2 * len(s.split())

    rows = build_rows("AAPL", FILING, HTML, count_tokens=words_x2)
    assert all(words_x2(embed_text(r)) <= 512 for r in rows)


def test_to_table_schema():
    rows = [{"ticker": "AAPL", "item": "1", "chunk_idx": i, "text": "a"} for i in range(2)]
    t = to_table(rows, np.ones((2, 384)))
    assert t.num_rows == 2
    assert t.schema.field("embedding").type == pa.list_(pa.float32(), 384)
    assert t.column("model").to_pylist() == [MODEL_ID, MODEL_ID]


def test_fit_to_limit_halves_until_within_limit():
    def words(s: str) -> int:
        return len(s.split())

    assert fit_to_limit("a b c d e f g", words, limit=3) == ["a b c", "d e", "f g"]
    assert fit_to_limit("a b", words, limit=3) == ["a b"]
