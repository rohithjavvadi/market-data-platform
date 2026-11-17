from ai.evals.retrieval import evaluate, first_hit_rank, summarize

CASES = [
    {"id": "a", "ticker": "AAPL", "items": ["1A"], "question": "qa"},
    {"id": "b", "ticker": "NVDA", "items": ["7", "I-2"], "question": "qb"},
]


def fake_search(question, ticker=None, k=5):
    if question == "qa":
        return [{"ticker": "AAPL", "item": "1A"}]
    return [{"ticker": "MSFT", "item": "7"}, {"ticker": "NVDA", "item": "I-2"}]


def test_first_hit_rank():
    hits = [{"ticker": "X", "item": "1"}, {"ticker": "AAPL", "item": "1A"}]
    assert first_hit_rank(hits, "AAPL", {"1A"}) == 2
    assert first_hit_rank(hits, "AAPL", {"7"}) is None


def test_evaluate_and_summarize():
    rows = evaluate(CASES, fake_search)
    assert [r["rank"] for r in rows] == [1, 2]
    assert summarize(rows) == {"n": 2, "hit@1": 0.5, "hit@k": 1.0, "mrr": 0.75}
