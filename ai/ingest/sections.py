"""Split a 10-K / 10-Q HTML filing into Item sections."""

import re
import sys

from bs4 import BeautifulSoup

ITEM_RE = re.compile(r"^\s*item\s+(\d{1,2}[a-c]?)\s*(?:[.:\u2013\u2014-]|$)", re.IGNORECASE)
PART_RE = re.compile(r"^\s*part\s+(iv|i{1,3})\b(?!\s*,)", re.IGNORECASE)
MAX_HEADING = 200


def html_to_lines(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    lines = soup.get_text("\n").split("\n")
    return [re.sub(r"\s+", " ", ln).strip() for ln in lines if ln.strip()]


def split_items(html: str, form: str = "10-K") -> dict[str, str]:
    """Return {item_key: text}.

    10-K keys: "1", "1A", "7". 10-Q keys carry the Part: "I-2", "II-1A".
    The table of contents repeats every heading; for each key we keep the
    occurrence followed by the most text, which is the real section.
    """
    lines = html_to_lines(html)
    use_parts = form.upper().startswith("10-Q")
    part = ""
    hits = []
    for i, ln in enumerate(lines):
        if len(ln) >= MAX_HEADING:
            continue
        p = PART_RE.match(ln)
        if p:
            part = p.group(1).upper()
            continue
        m = ITEM_RE.match(ln)
        if m:
            item = m.group(1).upper()
            hits.append((i, f"{part}-{item}" if use_parts and part else item))

    # Running page headers ("PART II / Item 7" on every page) repeat the same
    # key back to back; keep only the first hit of each run.
    hits = [h for k, h in enumerate(hits) if k == 0 or h[1] != hits[k - 1][1]]

    best: dict[str, tuple[int, int]] = {}  # key -> (char_length, start_line)
    for k, (start, key) in enumerate(hits):
        end = hits[k + 1][0] if k + 1 < len(hits) else len(lines)
        size = sum(len(x) for x in lines[start:end])
        if key not in best or size > best[key][0]:
            best[key] = (size, start)

    out = {}
    starts = sorted((start, key) for key, (_, start) in best.items())
    for j, (start, key) in enumerate(starts):
        end = starts[j + 1][0] if j + 1 < len(starts) else len(lines)
        out[key] = "\n".join(lines[start:end])
    return out


if __name__ == "__main__":
    from ai.ingest.edgar_docs import fetch_document, list_filings

    form = sys.argv[1] if len(sys.argv) > 1 else "10-K"
    filing = next(f for f in list_filings("0000320193") if f["form"] == form)
    sections = split_items(fetch_document(filing), form=form)
    print(filing["form"], filing["filing_date"])
    for key, text in sections.items():
        print(f"Item {key:>5}: {len(text):>8,} chars | {text[:60]}")
