"""Agent eval: run labelled questions through the agent; score tools and citations."""

import argparse
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ai.agent.loop import Result
from ai.evals.cases import HARD_CASES, PRICE_CASES, SEARCH_CASES

TAG_RE = re.compile(r"\[(?:PRICES [A-Z]+ [\d-]+\.\.[\d-]+|[A-Z]+ 10-[KQ] [\w-]+ [\d-]+)\]")
SENT_RE = re.compile(r"(?<=[.!?])\s+")
LEAD_TAGS = re.compile(r"^(\[[^\]]*\]\s*)+")


def sentences(text: str) -> list[str]:
    """Split into sentences; tags that open a fragment belong to the previous one."""
    out: list[str] = []
    for s in SENT_RE.split(text.strip()):
        m = LEAD_TAGS.match(s)
        if m and out:
            out[-1] += " " + m.group().strip()
            s = s[m.end() :]
        if len(s.split()) >= 4:
            out.append(s)
    return out


def _ticker_item(tag: str) -> tuple[str, str] | None:
    parts = tag.strip("[]").split()
    return (parts[0], parts[2]) if len(parts) == 4 else None


def score(case: dict, kind: str, res: Result) -> dict:
    tool = "get_price_stats" if kind == "price" else "search_filings"
    calls = [c for c in res.tool_calls if c.name == tool]
    t = case["ticker"]
    good = [c for c in calls if str(c.args.get("ticker", "")).upper() == t]
    if kind == "price":
        good = [c for c in good if str(c.args.get("period", "")).lower() == case["period"]]
        source_ok = any(s.startswith(f"[PRICES {t} ") for s in res.sources)
    else:
        want = {(t, i) for i in case["items"]}
        source_ok = any(_ticker_item(s) in want for s in res.sources)
    tags = TAG_RE.findall(res.answer)
    sents = sentences(res.answer)
    cited = [s for s in sents if TAG_RE.search(s)]
    return {
        "tool_ok": bool(calls),
        "arg_ok": bool(good),
        "source_ok": source_ok,
        "cite_rate": round(len(cited) / len(sents), 3) if sents else 0.0,
        "citations_valid": bool(tags) and set(tags) <= set(res.sources),
        "steps": res.steps,
        "n_calls": len(res.tool_calls),
    }


def all_cases() -> list[tuple[dict, str, str]]:
    return (
        [(c, "search", "standard") for c in SEARCH_CASES]
        + [(c, "search", "hard") for c in HARD_CASES]
        + [(c, "price", "price") for c in PRICE_CASES]
    )


METRICS = ["tool_ok", "arg_ok", "source_ok", "cite_rate", "citations_valid", "seconds"]


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    return {"n": n, **{m: round(sum(float(r[m]) for r in rows) / n, 3) for m in METRICS}}


if __name__ == "__main__":
    from ai.agent.loop import OllamaLLM, run

    p = argparse.ArgumentParser()
    p.add_argument("--model", default="qwen3:8b")
    p.add_argument("--ids", nargs="*")
    p.add_argument("--limit", type=int)
    p.add_argument("--out", default="ai/out/evals")
    a = p.parse_args()
    cases = [x for x in all_cases() if not a.ids or x[0]["id"] in a.ids][: a.limit]
    llm = OllamaLLM(a.model)
    rows = []
    for case, kind, set_name in cases:
        t0 = time.perf_counter()
        try:
            res = run(case["question"], llm)
        except Exception as e:
            res = Result(f"ERROR {type(e).__name__}: {e}", 0, [], [])
        row = {
            "id": case["id"],
            "set": set_name,
            "model": a.model,
            "seconds": round(time.perf_counter() - t0, 1),
            **score(case, kind, res),
            "answer": res.answer,
            "sources": ", ".join(res.sources),
            "calls": "; ".join(f"{c.name} {c.args}" for c in res.tool_calls),
        }
        rows.append(row)
        print(
            f"{row['id']:<18} tool={row['tool_ok']:d} arg={row['arg_ok']:d} "
            f"src={row['source_ok']:d} cite={row['cite_rate']:.2f} "
            f"valid={row['citations_valid']:d} {row['seconds']}s",
            flush=True,
        )
    for set_name in ("standard", "hard", "price"):
        rs = [r for r in rows if r["set"] == set_name]
        if rs:
            print(f"{set_name:<8}", summarize(rs))
    print(f"{'all':<8}", summarize(rows))
    Path(a.out).mkdir(parents=True, exist_ok=True)
    path = Path(a.out) / f"agent_{datetime.now(UTC):%Y%m%dT%H%M}.parquet"
    pq.write_table(pa.Table.from_pylist(rows), path)
    print("->", path)
