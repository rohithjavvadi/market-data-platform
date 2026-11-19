from ai.agent.loop import Reply, ToolCall, enforce_citations, run

GOOD = "[AAPL 10-K 1A 2026-11-03]"
BAD = "[GOOGL 10-K 7 2026-02-05]"


def test_strips_unretrieved_tag_and_notes_it():
    text, removed = enforce_citations(f"Risk A {GOOD}. Growth B {BAD}.", [GOOD])
    assert removed == [BAD]
    assert GOOD in text and BAD not in text
    assert "Growth B." in text
    assert "GOOGL 10-K 7 2026-02-05" in text


def test_noop_when_all_tags_retrieved():
    text, removed = enforce_citations(f"Risk A {GOOD}.", [GOOD])
    assert (text, removed) == (f"Risk A {GOOD}.", [])


def test_run_applies_guardrail():
    hit = {
        "ticker": "AAPL",
        "form": "10-K",
        "item": "1A",
        "filing_date": "2026-11-03",
        "score": 0.9,
        "text": "t",
    }
    call = ToolCall("search_filings", {"query": "q"})
    replies = [Reply("", [call]), Reply(f"A {GOOD}. B {BAD}.")]

    class LLM:
        def chat(self, messages, tools):
            return replies.pop(0)

    r = run("q", LLM(), funcs={"search_filings": lambda **kw: [hit]})
    assert r.removed == [BAD] and BAD not in r.answer
