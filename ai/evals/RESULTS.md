# Market Research Agent: evaluation results

Setup: qwen3:8b via Ollama (local, temperature 0, 16k context, think off) on an
Apple Silicon Mac with 16 GB RAM. Retrieval: bge-small-en-v1.5 embeddings +
DuckDB BM25, fused with reciprocal rank fusion. Corpus: latest 10-K + 10-Q for
AAPL, MSFT, NVDA, AMZN, GOOGL (1,784 chunks). Prices: daily bars snapshot,
last bar 2026-11-06.

## Retrieval (no LLM; `python -m ai.evals.retrieval`)

Hit = a top-k chunk has the expected ticker and section. k = 5.

| Set | Mode | hit@1 | hit@5 | MRR |
|---|---|---|---|---|
| standard (14, company named) | vector | 1.00 | 1.00 | 1.00 |
| standard | hybrid | 1.00 | 1.00 | 1.00 |
| hard (11, product/segment only) | vector | 0.64 | 0.91 | 0.77 |
| hard | **hybrid** | **0.82** | **1.00** | **0.89** |

The standard set has a ceiling effect (company names make it easy), so the hard
set was added. Hybrid helps most on exact names (LinkedIn, iPhone, third-party
seller services). Small n: one case moves hit@1 by about 9 points.

## Agent end-to-end on the tuning set (30 questions; `python -m ai.evals.agent`)

| Version | tool | args | source | cite rate | no invented tags | sec/q |
|---|---|---|---|---|---|---|
| v1 baseline | 0.70 | 0.87 | 0.37 | 0.28 | 0.47 | 35 |
| v2 no form/item filters + nudge | 0.90 | 0.87 | 0.87 | 0.64 | 0.87 | 54 |
| v3 company list + in-scope rule | 1.00 | 0.93 | 1.00 | 0.73 | 1.00 | 54 |

Findings that drove each change: v1 copied "10-K 1A" from the prompt examples
into every search (risk factors only) and skipped tools on questions without a
company name. v2 removed form/item from the tool schema and nudged once when no
tool was called. v3 named the five companies (the model did not map Alphabet to
GOOGL) and stated that product and segment questions are in scope.

These 30 questions were used for tuning, so v3 overstates real performance.

## Held-out (8 questions written by the user after tuning; run once)

Automatic: tools 0.88, tickers 0.75, cite rate 0.52, no invented tags 0.88,
44 s/question. Rubric: 3 pass, 3 partial, 2 fail.

| Case | Result | Note |
|---|---|---|
| AWS and NVIDIA stock growth | partial | used AMZN for AWS but did not say so |
| NVIDIA vs Apple risks | pass | |
| Widest stock range (all five) | fail | fetched 3 of 5, still named a winner |
| Future growth | fail | no prediction, but one citation not retrieved |
| AWS, NVIDIA, Apple performance | pass | |
| NVIDIA vs Amazon, weaker | pass | |
| SpaceX vs Amazon | partial | said SpaceX not covered, gave no Amazon data |
| Amazon past 5 months | partial | used 6m, did not say it substituted |

Planned guardrails (code, not prompt): strip or flag citation tags that are not
in the retrieved sources; check that every company named in a comparison was
fetched; state assumptions (segment to company, nearest supported period).
Future re-runs use a new held-out set.

Limits: small sets, one model, one run per question (temperature 0); rubric
graded by the author.
