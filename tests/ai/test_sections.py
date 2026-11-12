from ai.ingest.sections import split_items

BODY = "x " * 200


def _html(*lines: str) -> str:
    return "".join(f"<p>{ln}</p>" for ln in lines)


def test_toc_duplicate_keeps_body():
    html = _html(
        "Item 1. Business",
        "Item 1A. Risk Factors",
        "Item 7. MDA",
        "Item 1. Business",
        BODY,
        "Item 1A. Risk Factors",
        BODY,
        "Item 7. MDA",
        BODY,
    )
    s = split_items(html)
    assert list(s) == ["1", "1A", "7"]
    assert all(BODY.strip() in v for v in s.values())


def test_cross_reference_is_not_heading():
    html = _html(
        "Item 7. MDA",
        BODY,
        "Item 8 of this Form 10-K has details.",
        BODY,
        "Item 8. Financial Statements",
        BODY,
    )
    s = split_items(html)
    assert "Item 8 of this Form" in s["7"]
    assert s["8"].startswith("Item 8. Financial")


def test_uppercase_and_dash_headings():
    html = _html("ITEM 1A \u2014 RISK FACTORS", BODY, "ITEM 7: MDA", BODY)
    assert list(split_items(html)) == ["1A", "7"]


def test_nbsp_heading():
    assert "1A" in split_items(_html("Item&#160;1A.&#160;Risk Factors", BODY))


def test_10q_parts():
    html = _html(
        "PART I \u2014 FINANCIAL INFORMATION",
        "Item 1. Financial Statements",
        BODY,
        "Item 2. MDA",
        BODY,
        "PART II \u2014 OTHER INFORMATION",
        "Item 1. Legal Proceedings",
        BODY,
        "Item 1A. Risk Factors",
        BODY,
    )
    s = split_items(html, form="10-Q")
    assert list(s) == ["I-1", "I-2", "II-1", "II-1A"]
    assert s["II-1"].startswith("Item 1. Legal")


def test_part_cross_reference_with_comma_ignored():
    html = _html(
        "PART II",
        "Item 1. Legal Proceedings",
        BODY,
        "Part I, Item 2 of this report.",
        BODY,
        "Item 1A. Risk Factors",
        BODY,
    )
    assert list(split_items(html, form="10-Q")) == ["II-1", "II-1A"]


def test_10k_keys_have_no_part():
    assert list(split_items(_html("PART I", "Item 1. Business", BODY))) == ["1"]
