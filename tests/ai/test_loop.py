from ai.agent.loop import Reply, ToolCall, run

HIT = {
    "ticker": "NVDA",
    "form": "10-K",
    "item": "1A",
    "filing_date": "2026-02-25",
    "score": 0.8,
    "text": "export controls hurt sales",
}


class FakeLLM:
    def __init__(self, replies):
        self.replies, self.seen = list(replies), []

    def chat(self, messages, tools):
        self.seen.append((list(messages), tools))
        return self.replies.pop(0)


def test_tool_then_answer():
    calls = []

    def fake_search(**kw):
        calls.append(kw)
        return [HIT, HIT]

    args = {"query": "export controls", "ticker": "NVDA"}
    llm = FakeLLM([Reply("", [ToolCall("search_filings", args)]), Reply("Answer [x].")])
    r = run("q", llm, funcs={"search_filings": fake_search})
    assert calls == [args]
    assert (r.answer, r.steps) == ("Answer [x].", 2)
    assert r.sources == ["[NVDA 10-K 1A 2026-02-25]"]
    tool_msg = llm.seen[1][0][-1]
    assert tool_msg["role"] == "tool"
    assert "export controls hurt sales" in tool_msg["content"]


def test_unknown_tool_and_bad_args_are_reported():
    def fake_search(query):
        return []

    bad = [ToolCall("nope", {}), ToolCall("search_filings", {"bogus": 1})]
    llm = FakeLLM([Reply("", bad), Reply("done")])
    r = run("q", llm, funcs={"search_filings": fake_search})
    msgs = llm.seen[1][0]
    assert "unknown tool nope" in msgs[-2]["content"]
    assert msgs[-1]["content"].startswith("Error:")
    assert (r.answer, r.sources) == ("done", [])


def test_last_step_has_no_tools():
    looping = Reply("", [ToolCall("search_filings", {"query": "x"})])
    llm = FakeLLM([looping, looping, Reply("final")])
    r = run("q", llm, funcs={"search_filings": lambda **kw: []}, max_steps=3)
    assert [len(t) for _, t in llm.seen] == [1, 1, 0]
    assert (r.answer, r.steps) == ("final", 3)
