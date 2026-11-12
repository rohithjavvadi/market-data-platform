import pytest

from ai.ingest.chunk import chunk_words, clean


def test_clean_drops_footer_and_toc():
    text = "Risk text\nApple Inc. | 2026 Form 10-K | 23\nTable of Contents\n1,234\nMore"
    assert clean(text) == "Risk text\n1,234\nMore"


def test_clean_drops_10q_footer():
    assert clean("a\nApple Inc. | Q3 2026 Form 10-Q | 7\nb") == "a\nb"


def test_short_text_is_one_chunk():
    assert chunk_words("one two three") == ["one two three"]


def test_empty_text_has_no_chunks():
    assert chunk_words("   ") == []


def test_windows_and_overlap():
    words = [f"w{i}" for i in range(500)]
    chunks = chunk_words(" ".join(words), max_words=250, overlap=40)
    assert [len(c.split()) for c in chunks] == [250, 250, 80]
    assert chunks[1].split()[:40] == chunks[0].split()[-40:]
    assert chunks[-1].split()[-1] == "w499"


def test_bad_overlap_raises():
    with pytest.raises(ValueError):
        chunk_words("a b", max_words=10, overlap=10)
