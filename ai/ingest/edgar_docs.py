"""Fetch 10-K / 10-Q primary documents from SEC EDGAR."""

import os
import time

import requests

USER_AGENT = os.environ.get("SEC_USER_AGENT", "MarketDataPlatform contact@example.com")
HEADERS = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}
FORMS = {"10-K", "10-Q"}
SLEEP_S = 0.15  # SEC asks for ≤10 requests/second


def _get(url: str) -> requests.Response:
    time.sleep(SLEEP_S)
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r


def list_filings(cik: str, limit: int = 8) -> list[dict]:
    """Recent 10-K/10-Q filings for a CIK (10-digit, zero-padded)."""
    data = _get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()
    recent = data["filings"]["recent"]
    rows = []
    for form, acc, doc, date in zip(
        recent["form"],
        recent["accessionNumber"],
        recent["primaryDocument"],
        recent["filingDate"],
        strict=True,
    ):
        if form in FORMS:
            rows.append(
                {
                    "cik": cik,
                    "form": form,
                    "filing_date": date,
                    "accession": acc,
                    "primary_doc": doc,
                }
            )
        if len(rows) >= limit:
            break
    return rows


def fetch_document(row: dict) -> str:
    """Return the filing's main HTML/text body."""
    cik_int = int(row["cik"])
    acc_nodash = row["accession"].replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{row['primary_doc']}"
    return _get(url).text


if __name__ == "__main__":
    # Smoke test: Apple (CIK 0000320193), latest two filings
    for f in list_filings("0000320193", limit=2):
        body = fetch_document(f)
        print(f["form"], f["filing_date"], f["primary_doc"], len(body), "chars")
