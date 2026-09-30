# METHODS — independent Jev evaluation (phases 1–2)

This document describes what was done. It is not affiliated with TypeSafe AI,
and nothing here should be read as confirming or denying TypeSafe's marketing
claims. Vendor claims are not treated as findings anywhere in this repo.

## Model access

- Model: Jev, accessed through OpenRouter as `jev-latest` on 2026-09-30.
- Client: `typesafe_sdk.TypeSafeClient` with `base_url="https://openrouter.ai/api"`
  (the SDK appends `/v1/systemone` itself), 180 s timeout.
- Auth: a stored credential on the operator's machine (`OPENROUTER_API_KEY`
  env var for public use). The credential is never committed.
- Only the `Noul` question type (yes/no probability) was used in these phases.

## Phase 1 — calibration (200 Noul calls)

**Dataset** (`results/calibration-dataset-2026-09-30.json`): 200 short
declarative statements, hand-written, each with a known true/false label:

| difficulty | domain      | n   | label rule |
|------------|-------------|-----|------------|
| easy       | geography   | 50  | plain facts, 25 true / 25 false |
| easy       | arithmetic  | 50  | simple sums/products, 25 true / 25 false |
| easy       | commonsense | 50  | everyday facts, 25 true / 25 false |
| ambiguous  | myths       | 20  | 15 common myths (labeled false), 5 surprising-but-true claims (labeled true); each carries a `label_note` with the judgment |
| negated    | negation    | 30  | negated phrasings of plain facts, 15 true / 15 false |

**Question** (identical for every item):

> Decide whether the following statement is TRUE (yes-like) or FALSE (no-like).
> Give a high probability when the statement is true and a low probability
> when it is false.

**Procedure**: one `system_one(state=<statement>)` call per item, ~1.5 s pause
between calls. On API error: retry after 5 s, then after 15 s, then record the
item as failed and move on. Raw records (`results/calibration-2026-09-30-raw.jsonl`)
contain the statement, label, returned probability, latency, model name,
timestamp, and any error.

**Metrics** (`results/calibration-2026-09-30-metrics.json`):

- Brier score: mean squared error between probability and 0/1 label
  (0 = perfect, lower is better; a constant-0.5 predictor scores 0.25).
- Expected calibration error (ECE): 10 equal-width probability bins,
  Σ (n_bin / n) · |observed frequency − mean predicted probability|.
- Reliability table: per bin, n, mean predicted probability, observed frequency.
- Accuracy at the 0.5 decision threshold, overall and per difficulty class.

Note on the baseline: 0.25 is what a constant "always say 50%" predictor
scores, so it is a useful intuition for whether the model is doing real work,
not a formal bound — under class imbalance a smarter constant predictor can
score below 0.25.

## Phase 2 — stability (10 inputs × 20 repeats = 200 calls)

Ten inputs were selected from the Phase 1 results:

- 3 easy items with the most confidently correct probabilities,
- 4 ambiguous items whose Phase 1 probability fell in [0.2, 0.8]
  (the re-ask region from the tutorial), backfilled with the ambiguous items
  closest to 0.5 if fewer than 4 qualified,
- 3 negated items spread across the observed probability range.

Each input was sent 20 times with byte-identical state and the same Noul
question. Per input (`results/stability-2026-09-30-stats.json`): mean, sample
standard deviation, min, max of the 20 probabilities, fraction of runs ≥ 0.5,
and flip fraction (share of runs on the minority side of the 0.5 threshold —
i.e. how often an identical repeat would flip a yes/no decision).

## Cost tracking

The responses carried no `usage.cost` field (only `input_tokens` /
`output_tokens`), so spend was estimated from input tokens at the public
Jev input price ($0.042 per million tokens; output is free). Each raw record
carries `cost_usd`, `cost_basis` (`reported` / `estimated_from_tokens` /
`missing`), and a running total. A $2.00 circuit breaker would have halted
all calls immediately if the running total had been exceeded; it was not.

## Limitations

- Synthetic true/false statements are a narrow slice of "decisions"; good
  calibration here does not imply good calibration on real tasks.
- The Noul instruction wording is ours; different phrasing could shift results.
- Single-day snapshot (2026-09-30) via OpenRouter routing; the direct
  TypeSafe API could behave differently.
- Ambiguous-item labels are our judgment calls (documented per item in
  `label_note`); the stratified results let readers exclude them.
- n=200 (Phase 1) and n=20 repeats (Phase 2) are modest; treat bin-level
  reliability estimates as noisy.
