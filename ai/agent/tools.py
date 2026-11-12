"""Agent tools: semantic search over embedded SEC filing chunks."""

import argparse
import os
from collections.abc import Callable
from functools import lru_cache

import duckdb

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
DEFAULT_SOURCE = "ai/out/edgar_chunks/*.parquet"
MAX_K = 10
COLUMNS = ["ticker", "form", "filing_date", "item", "chunk_idx", "context", "text"]


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    from ai.ingest.embed import MODEL_ID

    return SentenceTransformer(MODEL_ID)


def encode_query(text: str) -> list[float]:
    return _model().encode(QUERY_PREFIX + text, normalize_embeddings=True).tolist()


def _connect(source: str) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    if source.startswith("s3://"):
        con.execute("INSTALL httpfs; LOAD httpfs; INSTALL aws; LOAD aws;")
        con.execute("CREATE SECRET (TYPE s3, PROVIDER credential_chain, REGION 'us-east-2');")
    return con


def search_filings(
    query: str,
    ticker: str | None = None,
    form: str | None = None,
    item: str | None = None,
    k: int = 5,
    *,
    encode: Callable[[str], list[float]] = encode_query,
    source: str | None = None,
) -> list[dict]:
    """Top-k filing chunks by cosine similarity, with optional exact filters."""
    source = source or os.environ.get("AI_CHUNKS_URI", DEFAULT_SOURCE)
    vec = encode(query)
    dim = len(vec)
    k = max(1, min(int(k), MAX_K))

    where, params = [], []
    if ticker:
        where.append("ticker = ?")
        params.append(ticker.upper())
    if form:
        where.append("form = ?")
        params.append(form.upper())
    if item:
        where.append("(item = ? OR item LIKE ?)")
        params += [item.upper(), f"%-{item.upper()}"]

    src = source.replace("'", "''")
    sql = (
        f"select {', '.join(COLUMNS)}, "
        f"array_cosine_similarity(embedding::FLOAT[{dim}], ?::FLOAT[{dim}]) as score "
        f"from read_parquet('{src}') "
        + (f"where {' and '.join(where)} " if where else "")
        + f"order by score desc limit {k}"
    )
    rows = _connect(source).execute(sql, [vec, *params]).fetchall()
    hits = [dict(zip(COLUMNS + ["score"], r, strict=True)) for r in rows]
    for h in hits:
        h["score"] = round(float(h["score"]), 3)
    return hits


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("query")
    p.add_argument("--ticker")
    p.add_argument("--form")
    p.add_argument("--item")
    p.add_argument("-k", type=int, default=5)
    a = p.parse_args()
    for h in search_filings(a.query, a.ticker, a.form, a.item, a.k):
        print(h["score"], h["ticker"], h["form"], h["filing_date"], h["item"], "|", h["text"][:80])
