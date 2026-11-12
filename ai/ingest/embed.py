"""Embed EDGAR filing chunks and write one Parquet file per filing."""

import argparse
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from ai.ingest.chunk import chunk_words, clean
from ai.ingest.edgar_docs import fetch_document, list_filings
from ai.ingest.sections import split_items

MODEL_ID = "BAAI/bge-small-en-v1.5"
MAX_TOKENS = 512
TICKERS = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "NVDA": "0001045810",
    "AMZN": "0001018724",
    "GOOGL": "0001652044",
}


def fit_to_limit(chunk: str, count_tokens: Callable[[str], int], limit: int = MAX_TOKENS) -> list[str]:
    """Halve a chunk recursively until every piece is within the token limit."""
    words = chunk.split()
    if count_tokens(chunk) <= limit or len(words) < 2:
        return [chunk]
    mid = len(words) // 2
    return fit_to_limit(" ".join(words[:mid]), count_tokens, limit) + fit_to_limit(
        " ".join(words[mid:]), count_tokens, limit
    )


def build_rows(
    ticker: str,
    filing: dict,
    html: str,
    count_tokens: Callable[[str], int] | None = None,
) -> list[dict]:
    rows = []
    for item, text in split_items(html, form=filing["form"]).items():
        chunks = chunk_words(clean(text))
        if count_tokens:
            chunks = [p for c in chunks for p in fit_to_limit(c, count_tokens)]
        for i, chunk in enumerate(chunks):
            rows.append(
                {
                    "ticker": ticker,
                    "form": filing["form"],
                    "filing_date": str(filing["filing_date"]),
                    "item": item,
                    "chunk_idx": i,
                    "text": chunk,
                }
            )
    return rows


def to_table(rows: list[dict], emb: np.ndarray) -> pa.Table:
    flat = pa.array(emb.astype(np.float32).ravel(), type=pa.float32())
    vec = pa.FixedSizeListArray.from_arrays(flat, emb.shape[1])
    table = pa.Table.from_pylist(rows).append_column("embedding", vec)
    return table.append_column("model", pa.array([MODEL_ID] * len(rows)))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tickers", nargs="+", default=list(TICKERS))
    p.add_argument("--forms", nargs="+", default=["10-K", "10-Q"])
    p.add_argument("--per-form", type=int, default=1)
    p.add_argument("--out", default="ai/out/edgar_chunks")
    a = p.parse_args()

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_ID)

    def count(s: str) -> int:
        return len(model.tokenizer(s)["input_ids"])

    for t in a.tickers:
        filings = list_filings(TICKERS[t])
        for form in a.forms:
            for f in [x for x in filings if x["form"] == form][: a.per_form]:
                rows = build_rows(t, f, fetch_document(f), count_tokens=count)
                if not rows:
                    print(f"{t} {form} {f['filing_date']}: no sections found")
                    continue
                texts = [r["text"] for r in rows]
                n_long = sum(count(x) > MAX_TOKENS for x in texts)
                emb = model.encode(texts, batch_size=32, normalize_embeddings=True)
                path = Path(a.out) / f"{t}_{f['filing_date']}_{form}.parquet"
                path.parent.mkdir(parents=True, exist_ok=True)
                pq.write_table(to_table(rows, emb), path)
                print(f"{t} {form} {f['filing_date']}: {len(rows)} chunks, {n_long} over {MAX_TOKENS} tokens -> {path}")


if __name__ == "__main__":
    main()
