"""Clean filing section text and split it into overlapping word windows."""

import re

FOOTER_RE = re.compile(r"\|\s*(?:Q\d\s+)?\d{4}\s+Form\s+10-[KQ]\s*\|\s*\d+\s*$", re.IGNORECASE)


def clean(text: str) -> str:
    keep = [ln for ln in text.split("\n") if not FOOTER_RE.search(ln) and ln.strip().lower() != "table of contents"]
    return "\n".join(keep)


def chunk_words(text: str, max_words: int = 250, overlap: int = 40) -> list[str]:
    if not 0 <= overlap < max_words:
        raise ValueError("need 0 <= overlap < max_words")
    words = text.split()
    chunks = []
    step = max_words - overlap
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start : start + max_words]))
        if start + max_words >= len(words):
            break
    return chunks


if __name__ == "__main__":
    from ai.ingest.edgar_docs import fetch_document, list_filings
    from ai.ingest.sections import split_items

    filing = next(f for f in list_filings("0000320193") if f["form"] == "10-K")
    sections = split_items(fetch_document(filing), form="10-K")
    total = 0
    for key, text in sections.items():
        chunks = chunk_words(clean(text))
        total += len(chunks)
        print(f"Item {key:>4}: {len(chunks):>4} chunks")
    joined = "\n".join(clean(t) for t in sections.values())
    print("total chunks:", total, "| footers left:", bool(FOOTER_RE.search(joined)))
