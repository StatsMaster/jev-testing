# Phase 5 — Baselines and cost (summary fragment for EVALUATION.md)

## Hypothesis

Jev beats cheap alternatives — constant predictors, a conventional LLM
constrained to output probabilities, and exact symbolic checking where it
applies — on calibration per dollar and per millisecond. If a $0.02/M-token
LLM prompted for a number matches Jev, there is no reason to adopt a
specialized decision model.

## Why it matters

"Better than an LLM at decisions" is Jev's implicit claim, and good absolute
numbers don't answer the adoption question. This is the build-vs-buy test:
what do you give up (calibration, latency) and what do you save (money) by
using the cheap thing instead?

## What the test showed

Same 200 labeled items as Phase 1. Headline comparison:

| Baseline | Brier ↓ | ECE ↓ | Acc@0.5 | Mean latency | Cost / 1k decisions |
|---|---|---|---|---|---|
| **Jev (Noul)** | **0.026** | 0.085 | 0.98 | 0.27 s | $0.0130 |
| Constrained LLM (mistral-nemo) | 0.227 | 0.187 | 0.735 | 1.38 s | $0.0016 |
| Constant 0.5 | 0.250 | 0.025 | 0.475 | 0 | $0 |
| Constant base-rate (0.475) | 0.249 | 0.000 | 0.525 | 0 | $0 |
| Constant majority-class (0.0) | 0.475 | 0.475 | 0.525 | 0 | $0 |

- **The constrained LLM is barely better than guessing 0.5** (Brier 0.227 vs
  0.250). Its outputs are spiky and overconfident — 86× "0.0", 76× in
  [0.9, 1.0], 26× "0.5" — and miscalibrated at the extremes: when it says
  0.0 the statement is actually true 24% of the time; when it says ~0.93,
  true only 76% of the time. Directionally better than chance (73.5%
  accuracy) but nearly useless *as probabilities*.
- **Model-selection note:** 8 cheap OpenRouter models (≤$0.10/M input, prices
  verified 2026-09-30) were probed with the exact task prompt before the run.
  llama-3.1-8b, qwen3-30b, nova-micro and command-r7b collapsed to constant
  "0"/"0.0" (nova-micro even answered 0.99 on a false-labeled item);
  gpt-oss-120b and deepseek-v4.1-flash returned empty strings. mistral-nemo
  ($0.019/M in, $0.030/M out) was the only one producing varied,
  directionally sensible outputs — the fairest "just prompt an LLM"
  representative, and it still fails as a probability machine.
- **Cost:** Jev is ~8× pricier per decision ($0.0130 vs $0.0016 per 1k) but
  ~9× better on Brier — and both are fractions of a cent per thousand
  decisions. At 1M decisions that's ~$13 (Jev) vs ~$1.60 (LLM). The LLM
  alternative isn't viable regardless of price: you can't buy calibration
  with it at any discount.
- **Latency:** Jev is ~5× faster (0.27 s vs 1.38 s mean).
- **Exact symbolic baseline (50 arithmetic items):** Brier **0.0** vs Jev's
  **0.051** on the same subset — perfect where it applies.
- Amusing calibration footnote: the base-rate constant has ECE **0.000**
  (perfectly calibrated) and is still useless — calibration without
  sharpness scores nothing. Brier captures both; ECE alone doesn't.
- Spend: $0.0003 for the 200 LLM calls (OpenRouter reported usage.cost
  directly); the $2 circuit breaker was never approached.

## Impact

The build-vs-buy question resolves decisively for Jev on this task class: a
naively constrained cheap LLM does not substitute for a calibrated decision
model — its numbers look like probabilities but don't behave like them. The
8× cost premium buys 9× better calibration *and* 5× lower latency, at
absolute costs (~~$13 per million decisions) that are negligible for any
serious use. The symbolic result sharpens the Phase 1 caveat into a rule:
where exact verification is possible (arithmetic, logic, lookups), use the
exact checker (Brier 0.0) — reserve Jev for judgments no symbolic rule can
express. Caveat: this tests the *naive* constrained-LLM approach; fancier
elicitation (reasoning-then-score, logit-based) might do better and is out
of scope here.
