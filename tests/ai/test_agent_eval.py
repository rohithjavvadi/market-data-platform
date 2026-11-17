from ai.agent.loop import Result, ToolCall
from ai.evals.agent import score, sentences

TAG = "[AAPL 10-K 1A 2026-11-03]"


def test_sentences_attach_leading_tags_to_previous():
    s = sentences(f"Sales rose a lot this year. {TAG} Margins fell sharply overall {TAG}.")
    assert len(s) == 2 and all(TAG in x for x in s)


def test_score_search():
    case = {"id": "x", "ticker": "AAPL", "items": ["1A"], "question": "q"}
    res = Result(
        f"Risk is high in China {TAG}. Another uncited sentence here.",
        2,
        [ToolCall("search_filings", {"query": "q", "ticker": "aapl"})],
        [TAG],
    )
    s = score(case, "search", res)
    assert (s["tool_ok"], s["arg_ok"], s["source_ok"], s["citations_valid"]) == (
        True,
        True,
        True,
        True,
    )
    assert s["cite_rate"] == 0.5


def test_score_price_flags_invented_citation():
    case = {"id": "p", "ticker": "AMZN", "period": "1y", "question": "q"}
    res = Result(
        "Return was 6.69% for the year [PRICES AMZN 2025-01-01..2026-01-01].",
        2,
        [ToolCall("get_price_stats", {"ticker": "AMZN", "period": "1y"})],
        ["[PRICES AMZN 2025-11-06..2026-11-06]"],
    )
    s = score(case, "price", res)
    assert s["arg_ok"] and s["source_ok"]
    assert not s["citations_valid"]
