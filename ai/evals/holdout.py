"""Held-out eval: multi-ticker / out-of-scope questions; auto metrics + rubric review."""

import argparse
import time
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ai.agent.loop import Result
from ai.evals.agent import TAG_RE, sentences
from ai.evals.cases import HOLDOUT_CASES


def score_holdout(case: dict, res: Result) -> dict:
    called = {c.name for c in res.tool_calls}
    tickers = {str(c.args.get("ticker", "")).upper() for c in res.tool_calls}
    tags = TAG_RE.findall(res.answer)
    sents = sentences(res.answer)
    return {
        "tools_ok": set(case["tools"]) <= called,
        "tickers_ok": set(case["tickers"]) <= tickers,
        "cite_rate": round(sum(bool(TAG_RE.search(s)) for s in sents) / len(sents), 3) if sents else 0.0,
        "no_invented_tags": set(tags) <= set(res.sources),
        "n_calls": len(res.tool_calls),
    }


if __name__ == "__main__":
    from ai.agent.loop import OllamaLLM, run

    p = argparse.ArgumentParser()
    p.add_argument("--model", default="qwen3:8b")
    p.add_argument("--out", default="ai/out/evals")
    a = p.parse_args()
    llm = OllamaLLM(a.model)
    rows = []
    for case in HOLDOUT_CASES:
        t0 = time.perf_counter()
        res = run(case["question"], llm, max_steps=5)
        row = {
            "id": case["id"],
            "seconds": round(time.perf_counter() - t0, 1),
            **score_holdout(case, res),
            "rubric": case["rubric"],
            "calls": "; ".join(f"{c.name} {c.args}" for c in res.tool_calls),
            "answer": res.answer,
        }
        rows.append(row)
        print(
            f"\n=== {row['id']}  tools={row['tools_ok']:d} tickers={row['tickers_ok']:d} "
            f"cite={row['cite_rate']:.2f} no_invented={row['no_invented_tags']:d} "
            f"{row['seconds']}s\nRUBRIC: {row['rubric']}\nCALLS: {row['calls']}\n"
            f"ANSWER: {row['answer'][:600]}",
            flush=True,
        )
    n = len(rows)
    print(
        "\nSUMMARY",
        {
            m: round(sum(float(r[m]) for r in rows) / n, 3)
            for m in ["tools_ok", "tickers_ok", "cite_rate", "no_invented_tags", "seconds"]
        },
    )
    Path(a.out).mkdir(parents=True, exist_ok=True)
    path = Path(a.out) / f"holdout_{datetime.now(UTC):%Y%m%dT%H%M}.parquet"
    pq.write_table(pa.Table.from_pylist(rows), path)
    print("->", path)
