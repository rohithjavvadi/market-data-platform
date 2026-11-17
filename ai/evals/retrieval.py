"""Retrieval eval: hit@1, hit@k and MRR for search_filings on labelled questions."""

import argparse
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ai.evals.cases import SEARCH_CASES


def first_hit_rank(hits: list[dict], ticker: str, items: set[str]) -> int | None:
    for i, h in enumerate(hits, 1):
        if h["ticker"] == ticker and h["item"] in items:
            return i
    return None


def evaluate(cases: list[dict], search, k: int = 5, use_ticker: bool = False) -> list[dict]:
    rows = []
    for c in cases:
        hits = search(c["question"], ticker=c["ticker"] if use_ticker else None, k=k)
        rows.append(
            {
                "id": c["id"],
                "use_ticker": use_ticker,
                "k": k,
                "rank": first_hit_rank(hits, c["ticker"], set(c["items"])),
                "top": f"{hits[0]['ticker']} {hits[0]['item']}" if hits else None,
            }
        )
    return rows


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    ranks = [r["rank"] for r in rows]
    return {
        "n": n,
        "hit@1": round(sum(r == 1 for r in ranks) / n, 3),
        "hit@k": round(sum(r is not None for r in ranks) / n, 3),
        "mrr": round(sum(1 / r for r in ranks if r) / n, 3),
    }


if __name__ == "__main__":
    from ai.agent.tools import search_filings

    p = argparse.ArgumentParser()
    p.add_argument("-k", type=int, default=5)
    p.add_argument("--out", default="ai/out/evals")
    a = p.parse_args()
    all_rows = []
    for use_ticker in (False, True):
        rows = evaluate(SEARCH_CASES, search_filings, a.k, use_ticker)
        all_rows += rows
        print(f"ticker filter={use_ticker}:", summarize(rows))
        for r in rows:
            if r["rank"] != 1:
                print(f"   {r['id']:<18} rank={r['rank']} top={r['top']}")
    Path(a.out).mkdir(parents=True, exist_ok=True)
    path = Path(a.out) / f"retrieval_{datetime.now(UTC):%Y%m%dT%H%M}.parquet"
    pq.write_table(pa.Table.from_pylist(all_rows), path)
    print("->", path)
