"""Agent tools: hybrid (BM25 + vector) search over embedded SEC filing chunks."""

import argparse
import os
from collections.abc import Callable
from functools import lru_cache

import duckdb

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
DEFAULT_SOURCE = "ai/out/edgar_chunks/*.parquet"
MAX_K = 10
RRF_K = 60
MODES = ("hybrid", "vector")
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


@lru_cache(maxsize=4)
def _index(source: str) -> duckdb.DuckDBPyConnection:
    """Load chunks into an in-memory table with a BM25 index (cached per source)."""
    con = _connect(source)
    con.execute("INSTALL fts; LOAD fts;")
    src = source.replace("'", "''")
    con.execute(f"create table chunks as select row_number() over () as id, * from read_parquet('{src}')")
    con.execute("pragma create_fts_index('chunks', 'id', 'context', 'text', stemmer = 'porter', stopwords = 'english')")
    return con


def search_filings(
    query: str,
    ticker: str | None = None,
    form: str | None = None,
    item: str | None = None,
    k: int = 5,
    mode: str = "hybrid",
    *,
    encode: Callable[[str], list[float]] = encode_query,
    source: str | None = None,
) -> list[dict]:
    """Top-k chunks by RRF of BM25 and cosine ranks (or cosine only), with filters."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
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
    filt = f"where {' and '.join(where)}" if where else ""
    order = "fused" if mode == "hybrid" else "v.cos"
    cols = ", ".join(f"base.{c}" for c in COLUMNS)
    sql = f"""
        with base as (select * from chunks {filt}),
        v0 as (select id, array_cosine_similarity(
                   embedding::FLOAT[{dim}], ?::FLOAT[{dim}]) as cos from base),
        v as (select id, cos, row_number() over (order by cos desc) as rv from v0),
        b0 as (select id, fts_main_chunks.match_bm25(id, ?) as bm from base),
        b as (select id, row_number() over (order by bm desc) as rb
              from b0 where bm is not null)
        select {cols}, v.cos, b.rb is not null as kw,
               1.0 / ({RRF_K} + v.rv) + coalesce(1.0 / ({RRF_K} + b.rb), 0) as fused
        from base join v using (id) left join b using (id)
        order by {order} desc limit {k}
    """
    rows = _index(source).execute(sql, [*params, vec, query]).fetchall()
    hits = [dict(zip(COLUMNS + ["cos", "kw", "fused"], r, strict=True)) for r in rows]
    for h in hits:
        h["cos"] = round(float(h["cos"]), 3)
        h["fused"] = round(float(h["fused"]), 4)
        h["score"] = h["fused"] if mode == "hybrid" else h["cos"]
    return hits


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("query")
    p.add_argument("--ticker")
    p.add_argument("--form")
    p.add_argument("--item")
    p.add_argument("--mode", default="hybrid", choices=MODES)
    p.add_argument("-k", type=int, default=5)
    a = p.parse_args()
    for h in search_filings(a.query, a.ticker, a.form, a.item, a.k, a.mode):
        print(h["score"], h["cos"], "kw" if h["kw"] else "  ", h["ticker"], h["form"], h["item"], "|", h["text"][:70])
