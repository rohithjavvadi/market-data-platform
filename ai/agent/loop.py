"""Agent loop: an LLM answers questions about SEC filings using tools."""

import argparse
from dataclasses import dataclass, field
from typing import Protocol

from ai.agent.tools import search_filings

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]
SYSTEM = (
    "You are a market research assistant. Answer questions about AAPL, MSFT, "
    "NVDA, AMZN and GOOGL using only search_filings results. Always search "
    "before answering. Cite every claim with the tag shown in the results, "
    "like [NVDA 10-K 1A 2026-02-25]. If the results do not contain the "
    "answer, say so. Be concise."
)
SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_filings",
        "description": "Semantic search over the latest 10-K and 10-Q text.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for"},
                "ticker": {"type": "string", "enum": TICKERS},
                "form": {"type": "string", "enum": ["10-K", "10-Q"]},
                "item": {
                    "type": "string",
                    "description": "Item number, e.g. 1A risk factors, 7 MD&A, 1 business",
                },
                "k": {"type": "integer", "description": "Results, 1-10 (default 5)"},
            },
            "required": ["query"],
        },
    },
}
TOOL_FUNCS = {"search_filings": search_filings}


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


def run_tool(call: ToolCall, funcs: dict) -> tuple[str, list[dict]]:
    fn = funcs.get(call.name)
    if fn is None:
        return f"Error: unknown tool {call.name}", []
    try:
        hits = fn(**call.args)
    except (TypeError, ValueError) as e:
        return f"Error: {e}", []
    if not hits:
        return "No matching passages.", []
    text = "\n\n".join(f"{cite(h)} (score {h['score']})\n{h['text']}" for h in hits)
    return text, hits


@dataclass
class Result:
    answer: str
    steps: int
    tool_calls: list[ToolCall]
    sources: list[str]


def run(question: str, llm: LLM, funcs: dict | None = None, max_steps: int = 4) -> Result:
    funcs = funcs or TOOL_FUNCS
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": question},
    ]
    calls: list[ToolCall] = []
    sources: list[str] = []
    for step in range(1, max_steps + 1):
        tools = [SEARCH_TOOL] if step < max_steps else []
        reply = llm.chat(messages, tools)
        if not reply.tool_calls:
            return Result(reply.content.strip(), step, calls, sources)
        messages.append(
            {
                "role": "assistant",
                "content": reply.content,
                "tool_calls": [{"function": {"name": c.name, "arguments": c.args}} for c in reply.tool_calls],
            }
        )
        for c in reply.tool_calls:
            calls.append(c)
            text, hits = run_tool(c, funcs)
            for h in hits:
                if cite(h) not in sources:
                    sources.append(cite(h))
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
