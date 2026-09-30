# Jev testing

Hands-on testing of [Jev](https://www.typesafe.ai/), TypeSafe AI's "System One"
decision model — a non-generative model that takes unstructured state plus
typed questions (`Noul`, `Choice`, `Score`) and returns typed decisions with
probabilities, instead of generated text.

This repo follows the [Real Python Jev tutorial](https://realpython.com/jev-python/),
with fixes noted below where the tutorial text didn't match the current SDK.

## Setup

Requires Python 3.10+ and an [OpenRouter](https://openrouter.ai/) API key
with a few dollars of credit (Jev is served through OpenRouter).

```bash
# with uv (as the tutorial does)
uv sync
export OPENROUTER_API_KEY=sk-or-...
uv run --env-file .env jev_noul.py

# or plain pip
python -m venv .venv && .venv/bin/pip install -e .
export OPENROUTER_API_KEY=sk-or-...
.venv/bin/python jev_desk.py
```

## Scripts

- `plain_python.py` — tutorial step 1: no AI, strict uppercase Y/N loop.
- `jev_noul.py` — tutorial step 2: free-text reply classified by a `Noul`
  (yes/no probability). Scores > 0.8 count as yes, < 0.2 as no, anything
  between asks the visitor to rephrase.
- `jev_desk.py` — tutorial step 3: one request, three questions — a `Choice`
  (which desk), a `Score` (urgency 0–3), and a `Noul` (needs assistance).
- `results/probe-2026-09-30.json` — raw output of a non-interactive probe run
  of steps 2 and 3.

## Independent evaluation (2026-09-30)

`METHODS.md` describes the protocol. Headline results, `Noul` via
OpenRouter (`jev-latest`):

- **Phase 1 — calibration** (200 labeled true/false statements, one call
  each): Brier **0.026**, 10-bin ECE **0.085**, accuracy at 0.5 threshold
  **98%**. Slight underconfidence on true statements.
- **Phase 2 — stability** (10 inputs × 20 identical repeats): zero decision
  flips at the 0.5 threshold; per-input std ≤ 0.013 for 9/10 inputs
  (one negated comparative reached std 0.075, range 0.54–0.80).

Scripts:

- `jev_eval_common.py` — shared client/auth, retry + backoff, per-call cost
  tracking with a $2 circuit breaker.
- `jev_eval_dataset.py` — builds the 200-item labeled dataset
  (`results/calibration-dataset-2026-09-30.json`).
- `jev_eval_calibration.py` — Phase 1 runner + metrics.
- `jev_eval_stability.py` — Phase 2 runner + per-input statistics.

Raw results live under `results/` (`calibration-2026-09-30-raw.jsonl`,
`calibration-2026-09-30-metrics.json`, `stability-2026-09-30-raw.jsonl`,
`stability-2026-09-30-stats.json`). Total measured spend for all 400 calls
was about **$0.005** (estimated from input tokens; see METHODS.md).

## Deviations from the tutorial (typesafe-sdk as of 2026-09-30)

1. `base_url` must be `https://openrouter.ai/api`, **not**
   `https://openrouter.ai/api/v1` — this SDK version appends `/v1/systemone`
   itself, so the tutorial's value double-prefixes and 404s.
2. `Choice` and `Score` also require an `instructions` field, not just `Noul`.
3. The `systemone` endpoint takes TypeSafe model names like `jev-latest`;
   OpenRouter's chat-style id `typesafe/jev-router` is rejected with 400.
4. The SDK's default 10 s timeout can be too short on slow/cold connections;
   these scripts use 180 s.

## First results (2026-09-30)

`Noul` on "did you lose something?":

| reply | score |
|---|---|
| "Yeah, I've lost something." | 0.86 |
| "nope, just looking around" | 0.48 |
| "yes" | 0.98 |

Note the middle row: a clear "no" to a human lands in the 0.2–0.8 dead zone
where the tutorial script just asks again — the calibration story is where
the interesting testing lives.

Desk scenario ("I left my suitcase on the 8:15 train and my connection leaves
in ten minutes!"): `desk=lost_and_found` at 0.99 confidence, urgency score
2.86/3 (P("right now")=0.86), `needs_assistance` Noul=0.96. About 0.5 s per
call once warm.
