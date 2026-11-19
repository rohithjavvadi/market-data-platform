"""Agent loop: an LLM answers market questions using filing and price tools."""

import argparse
import json
import re
from dataclasses import dataclass, field
from typing import Protocol

from ai.agent.prices import PERIODS, get_price_stats
from ai.agent.tools import search_filings

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]
SYSTEM = (
    "You are a market research assistant for five companies: Apple (AAPL), "
    "Microsoft (MSFT), NVIDIA (NVDA), Amazon (AMZN) and Alphabet/Google (GOOGL). "
    "Any question about their businesses, products, segments, risks, results or "
    "stock is in scope. Use search_filings for what the companies say in their "
    "10-K/10-Q filings: set ticker when you know which company it is, otherwise "
    "leave ticker empty to search all five. Use get_price_stats for stock "
    "performance (return, volatility, drawdown). Always call a tool before "
    "answering and never use outside knowledge. End every sentence with a "
    "citation tag copied from the tool results, e.g. [NVDA 10-K 1A 2026-02-25] "
    "or [PRICES AMZN 2025-11-06..2026-11-06]. Mention the end date of any price "
    "data. If the results do not answer the question, say so. Be concise."
)
SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_filings",
        "description": (
            "Keyword + semantic search over the latest 10-K and 10-Q text of "
            "AAPL, MSFT, NVDA, AMZN and GOOGL. Set ticker whenever the company is "
            "known, including when the question only names one of its products, "
            "brands or segments."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for, in plain words"},
                "ticker": {"type": "string", "enum": TICKERS},
                "k": {"type": "integer", "description": "Results, 1-10 (default 5)"},
            },
            "required": ["query"],
        },
    },
}
PRICE_TOOL = {
    "type": "function",
    "function": {
        "name": "get_price_stats",
        "description": "Total return, annualized volatility, max drawdown and "
        "high/low for one ticker over a trailing period (daily adjusted closes).",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "enum": TICKERS},
                "period": {"type": "string", "enum": PERIODS},
            },
            "required": ["ticker"],
        },
    },
}
SCHEMAS = {"search_filings": SEARCH_TOOL, "get_price_stats": PRICE_TOOL}
TOOL_FUNCS = {"search_filings": search_filings, "get_price_stats": get_price_stats}


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class Reply:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLM(Protocol):
    def chat(self, messages: list[dict], tools: list[dict]) -> Reply: ...


class OllamaLLM:
    def __init__(self, model: str = "qwen3:8b", num_ctx: int = 16384):
        self.model, self.num_ctx = model, num_ctx

    def chat(self, messages: list[dict], tools: list[dict]) -> Reply:
        import ollama

        r = ollama.chat(
            model=self.model,
            messages=messages,
            tools=tools,
            think=False,
            options={"num_ctx": self.num_ctx, "temperature": 0},
        )
        calls = [ToolCall(c.function.name, dict(c.function.arguments)) for c in r.message.tool_calls or []]
        return Reply(r.message.content or "", calls)


def cite(h: dict) -> str:
    return f"[{h['ticker']} {h['form']} {h['item']} {h['filing_date']}]"


def format_search(hits: list[dict]) -> tuple[str, list[str]]:
    if not hits:
        return "No matching passages.", []
    text = "\n\n".join(f"{cite(h)} (score {h['score']})\n{h['text']}" for h in hits)
    return text, [cite(h) for h in hits]


def format_prices(stats: dict) -> tuple[str, list[str]]:
    if "error" in stats:
        return json.dumps(stats), []
    tag = f"[PRICES {stats['ticker']} {stats['start_date']}..{stats['end_date']}]"
    return f"{tag}\n{json.dumps(stats)}", [tag]


FORMATTERS = {"search_filings": format_search, "get_price_stats": format_prices}


def run_tool(call: ToolCall, funcs: dict) -> tuple[str, list[str]]:
    fn = funcs.get(call.name)
    if fn is None:
        return f"Error: unknown tool {call.name}", []
    try:
        out = fn(**call.args)
    except (TypeError, ValueError) as e:
        return f"Error: {e}", []
    fmt = FORMATTERS.get(call.name)
    return fmt(out) if fmt else (json.dumps(out, default=str), [])


CITE_RE = re.compile(r"\[(?:PRICES [A-Z]+ [\d-]+\.\.[\d-]+|[A-Z]+ 10-[KQ] [\w-]+ [\d-]+)\]")


def enforce_citations(answer: str, sources: list[str]) -> tuple[str, list[str]]:
    """Remove citation tags that were not retrieved this run; append a note."""
    removed = sorted({t for t in CITE_RE.findall(answer) if t not in sources})
    for t in removed:
        answer = answer.replace(t, "")
    answer = re.sub(r"[ \t]+([.,;:])", r"\1", answer)
    answer = re.sub(r"[ \t]{2,}", " ", answer).strip()
    if removed:
        names = ", ".join(t.strip("[]") for t in removed)
        answer += f"\n\n(Removed citation not found in retrieved sources: {names})"
    return answer, removed


@dataclass
class Result:
    answer: str
    steps: int
    tool_calls: list[ToolCall]
    sources: list[str]
    removed: list[str] = field(default_factory=list)


NUDGE = "Call one of the tools before answering. Answer only from tool results."


def run(question: str, llm: LLM, funcs: dict | None = None, max_steps: int = 4) -> Result:
    funcs = funcs or TOOL_FUNCS
    schemas = [SCHEMAS[n] for n in funcs if n in SCHEMAS]
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": question},
    ]
    calls: list[ToolCall] = []
    sources: list[str] = []
    nudged = False
    for step in range(1, max_steps + 1):
        reply = llm.chat(messages, schemas if step < max_steps else [])
        if not reply.tool_calls:
            if not calls and not nudged and step < max_steps - 1:
                nudged = True
                messages.append({"role": "assistant", "content": reply.content})
                messages.append({"role": "user", "content": NUDGE})
                continue
            answer, removed = enforce_citations(reply.content.strip(), sources)
            return Result(answer, step, calls, sources, removed)
        messages.append(
            {
                "role": "assistant",
                "content": reply.content,
                "tool_calls": [{"function": {"name": c.name, "arguments": c.args}} for c in reply.tool_calls],
            }
        )
        for c in reply.tool_calls:
            calls.append(c)
            text, srcs = run_tool(c, funcs)
            for x in srcs:
                if x not in sources:
                    sources.append(x)
            messages.append({"role": "tool", "tool_name": c.name, "content": text})
    return Result("Stopped: no final answer.", max_steps, calls, sources)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("question")
    p.add_argument("--model", default="qwen3:8b")
    a = p.parse_args()
    res = run(a.question, OllamaLLM(a.model))
    print(res.answer)
    print("\nsteps:", res.steps)
    for c in res.tool_calls:
        print("tool:", c.name, c.args)
    print("sources:", ", ".join(res.sources))
