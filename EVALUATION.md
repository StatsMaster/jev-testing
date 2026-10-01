# Jev evaluation — structured test log

Independent evaluation of the Jev decision model (TypeSafe AI), run by James Baxter
for Samuel Seibert. Each phase is recorded in the same four-part structure:

- **Hypothesis** — what we expected to be true going in.
- **Why it matters** — which real-world decision or vendor claim this tests.
- **What the test showed** — the observed result, with numbers.
- **Impact** — what changes because of the finding (what we'd do differently,
  what it rules in or out).

Vendor marketing claims are never treated as findings. See METHODS.md for
procedure details and limitations.

---

## A note on the Brier score (read this first)

The Brier score is the mean squared error between a predicted probability and
the actual 0/1 outcome:

    Brier = (1/n) · Σ (predictedᵢ − outcomeᵢ)²

0 is perfect; 1 is the worst possible. It is a *strictly proper* scoring rule:
in expectation, you minimize it by reporting your true beliefs — hedging and
exaggerating both cost you.

**Worked micro-example.** Five forecasts:

| predicted | outcome   | (p − o)² |
|-----------|-----------|----------|
| 0.90      | true (1)  | 0.0100   |
| 0.70      | true (1)  | 0.0900   |
| 0.30      | false (0) | 0.0900   |
| 0.20      | false (0) | 0.0400   |
| 0.55      | true (1)  | 0.2025   |

Sum = 0.4325, Brier = 0.4325 / 5 = **0.0865**.

**Reference points** (binary outcomes):

| Forecaster                                             | Brier  |
|--------------------------------------------------------|--------|
| Perfect (1.0 on trues, 0.0 on falses)                  | 0.00   |
| Perfectly calibrated, 98% confident                    | 0.0196 |
| Perfectly calibrated, 95% confident                    | 0.0475 |
| Perfectly calibrated, 90% confident                    | 0.09   |
| Always says 0.5 ("I don't know")                       | 0.25   |
| Says 0.9 but right only half the time (overconfident)  | 0.41   |

Notes:

- A perfectly calibrated forecaster predicting a constant c when the base
  rate is also c scores exactly c·(1−c) — hence the 0.09 / 0.0475 / 0.0196
  rows above.
- The last row is the cautionary tale: confident-and-wrong (0.41) scores
  *worse* than saying "I don't know" (0.25), because the penalty is quadratic —
  a 0.99 forecast on a false outcome contributes 0.9801, nearly a full point,
  while a 0.6 on the same outcome contributes only 0.36.
- Jev's Phase 1 Brier of **0.026** sits near "perfectly calibrated at ~97%
  confidence" — that is the intuition to carry into the phases below.
- For the decomposition-minded: Brier = Reliability − Resolution +
  Uncertainty. The reliability term is what the calibration curve shows, and
  the resolution term rewards sharpness (confident correct answers).

---

## Phase 1 — Calibration (complete, 2026-09-30)

**Hypothesis.** Jev's returned probabilities are well-calibrated: among
statements it scores near 0.8, roughly 80% should actually be true. A model
trained with Reinforcement Learning for Calibrated Decisions should land well
below the Brier score of a constant-0.5 predictor (0.25) and trace a reliability
curve near the diagonal.

**Why it matters.** Calibration is Jev's core differentiator — "answers in
probabilities you can act on." An uncalibrated probability is worse than
useless for decision-making: if it says 0.9 but is right 60% of the time, every
threshold policy built on top of it is mispriced. This phase tests whether the
headline claim survives contact with labeled data.

**What the test showed** (200 labeled statements, 200/200 calls succeeded,
mean latency 0.27 s):

- Brier score **0.026** (constant-0.5 scores 0.25) — roughly 10x better than
  the do-nothing baseline.
- Expected calibration error (10 equal-width bins): **0.085**.
- Accuracy at a 0.5 threshold: **98%** (196/200).
- Reliability table is a clean diagonal with slight **underconfidence** on true
  statements (e.g. bin [0.8,0.9): mean predicted 0.852, observed 0.966).
- Negated phrasings handled cleanly: Brier **0.008**, 100% accuracy (n=30).
- Weak spot: near-miss arithmetic got partial credit — "23+19=40" → 0.72,
  "36−14=20" → 0.87, "17+28=43" → 0.67, a clear gradient where closer wrong
  answers score higher. Three of the four total misclassifications were
  near-miss arithmetic, suggesting fuzzy rather than exact verification.

**Impact.** The calibration claim held up on simple factual statements — this
is the strongest evidence so far that Jev is doing something real. The
underconfidence pattern is encouraging for decision use (conservative beats
overconfident when acting on thresholds). The arithmetic fuzziness is a genuine
caveat: do not use Noul as an exact verifier. Scope limit: synthetic true/false
is the easiest possible case for a decision model; real decisions come later.

## Phase 2 — Test-retest stability (complete, 2026-09-30)

**Hypothesis.** Identical inputs produce near-identical probabilities. Even if
the model samples stochastically per call, repeated identical queries should
agree on the yes/no decision.

**Why it matters.** If the same question scores 0.3 one minute and 0.7 the
next, no threshold policy is trustworthy and no result is reproducible.
Stability is a prerequisite for using these scores in any automated pipeline.

**What the test showed** (10 inputs × 20 identical repeats, 200/200 succeeded):

- **Zero decision flips** at the 0.5 threshold across all 200 repeats.
- 9/10 inputs: std ≤ 0.013, range ≤ 0.04 — very tight.
- Outlier: cal-178 ("Light does not travel slower than sound", negated
  comparative) — mean 0.712, std 0.075, range 0.54–0.80, never crossed 0.5.
- The deliberate 0.50 hedge case ("A tomato is a vegetable") was a *stable*
  hedge: 20-run mean 0.475, std 0.011.
- Probabilities look coarsely quantized: only 32 distinct values across
  200 repeats.

**Impact.** Decisions are reproducible — the headline reliability result holds.
The quantization finding matters for usage: fine for thresholding, but don't
expect fine-grained ranking from these scores. The outlier points at convoluted
phrasing (negated comparatives) as where instability lives, which feeds
directly into Phase 3's design.

## Phase 3 — Robustness to rewording (complete, 2026-09-30)

**Hypothesis.** Probabilities should be roughly invariant to
meaning-preserving rewording (paraphrase, padding, synonym swaps) and should
degrade gracefully — not flip — under adversarial phrasing.

**Why it matters.** Real inputs aren't clean lab sentences. If rewording the
same claim moves the score a lot, the probability is measuring the phrasing,
not the belief — and prompt-injection-style score manipulation becomes
possible. Phase 2's outlier (a negated comparative) suggested phrasing
sensitivity is where this model wobbles.

**What the test showed** (48 items × 3 hand-verified variants, 144/144 calls
succeeded, spend $0.0019):

| Variant class | Mean |shift| | p90 |shift| | Flip rate at 0.5 | Brier vs labels |
|---------------|------|------|------|------|------|------|------|
| Paraphrase | 0.065 | 0.120 | 4.2% (2 flips) | 0.040 |
| Padding (irrelevant filler sentences) | 0.325 | 0.483 | 41.7% (20 flips) | 0.188 |
| Adversarial (loaded/emotional framing) | 0.158 | 0.319 | 2.1% (1 flip) | 0.079 |

Phase 1 reference Brier on the original items: 0.026.

- **Paraphrase is fine.** Rewording the claim barely moves the score; 46/48
  decisions unchanged. The two flips are instructive, not damning: one was
  cal-094, the near-miss arithmetic item Phase 1 got wrong (0.87) — its
  paraphrase moved to 0.34, i.e. *toward* the correct answer. The other
  (cal-170, "The Aztec Empire came into existence after Oxford University was
  founded.", 0.88 → 0.13) is a genuine wobble on a convoluted comparison —
  consistent with Phase 2's finding that complex phrasing is the weak spot.
- **Padding is the failure mode.** Appending 2–3 irrelevant filler sentences
  ("I watered the garden this evening...") drags confident probabilities
  toward 0.5 en masse: mean shift 0.325, and 20 of 48 decisions flipped
  (e.g. 0.94 → 0.45, 0.93 → 0.43). The model treats irrelevant context as
  uncertainty, not as noise to ignore.
- **Adversarial framing barely registers.** Confident rhetoric ("Only a fool
  would deny that..."), conspiracy-flavored endorsement, and double negatives
  moved scores modestly (mean shift 0.158) and flipped exactly one decision.
  The model is far more swayed by boring filler than by loaded persuasion.

**Impact.** This inverts the naive threat model: nobody needs clever rhetoric
to move Jev's scores — appending unrelated sentences is far more effective
than emotional manipulation. For anyone building on Jev, the practical
takeaway is to keep the `state` field to the claim and nothing else; any
surrounding context (chat history, retrieved documents, boilerplate) will
systematically dilute confidence toward 0.5 and can flip decisions at scale
(42% flip rate here). Paraphrase-robustness, by contrast, is genuinely good,
so restating a claim in your own words is safe. This also reframes Phase 4:
if bundling multiple questions into one call acts like padding, joint calls
may show the same dilution effect.

## Phase 4 — Joint-question interference (complete, 2026-09-30)

**Hypothesis.** Asking several Noul questions in one `system_one` call should
not materially change each answer versus asking them singly — each question's
probability should reflect that statement alone.

**Why it matters.** The tutorial pattern bundles Noul+Choice+Score in a single
request. If bundled answers drift, batched calls aren't comparable to single
calls: thresholds tuned on single-question scores would misprice bundled ones,
and results wouldn't be reproducible across calling patterns. This is a real
API-design concern for anyone building on Jev.

**What the test showed** (30 items: 20 easy / 5 ambiguous / 5 negated;
30 single calls + 7 bundled calls of 5 = 35 paired measurements; 0 failures;
spend $0.0006). Bundling mechanism: one call whose state is a numbered
statement list, with one Noul per statement in the questions mapping, each
pointing at its statement number (verified by probe: per-statement
probabilities come back cleanly and correctly).

- Mean |p_bundled − p_single| = **0.099**; p90 = 0.25; max = **0.40**.
- **Flip rate at 0.5: 3/35 (8.6%).** Largest: "Antarctica is the smallest
  continent." (false) went 0.42 → 0.82; "Seventeen plus twenty-eight equals
  forty-three." (false) went 0.73 → 0.44.
- Mean signed drift = **+0.040**: bundling nudges scores upward on average.
- Position effect: the last bundle position drifts most — mean |drift| 0.14
  at position 4 vs 0.07–0.11 at positions 0–3. Five anchor items asked at both
  first and last position differed by mean 0.04 (max 0.12).

**Impact.** Bundling is not a free lunch: answers shift by ~0.1 on average,
later-in-bundle questions shift most, and ~9% of decisions flipped. Anyone
building on Jev should either ask questions singly or calibrate thresholds on
bundled scores specifically — never mix single and bundled scores in one
pipeline. Caveat: the bundled instructions necessarily differ slightly from
the single ones (they must point at a numbered statement), so this measures
the practical bundled-calling pattern, not pure "jointness" isolated from
wording.

## Phase 5 — Baselines and cost (complete, 2026-09-30)

**Hypothesis.** Jev beats cheap alternatives — constant predictors, a
conventional LLM constrained to output probabilities, and exact symbolic
checking where it applies — on calibration per dollar and per millisecond. If
a $0.02/M-token LLM prompted for a number matches Jev, there is no reason to
adopt a specialized decision model.

**Why it matters.** "Better than an LLM at decisions" is Jev's implicit claim,
and good absolute numbers don't answer the adoption question. This is the
build-vs-buy test: what do you give up (calibration, latency) and what do you
save (money) by using the cheap thing instead?

**What the test showed.** Same 200 labeled items as Phase 1:

| Baseline | Brier \u2193 | ECE \u2193 | Acc@0.5 | Mean latency | Cost / 1k decisions |
|---|---|---|---|---|---|
| **Jev (Noul)** | **0.026** | 0.085 | 0.98 | 0.27 s | $0.0130 |
| Constrained LLM (mistral-nemo) | 0.227 | 0.187 | 0.735 | 1.38 s | $0.0016 |
| Constant 0.5 | 0.250 | 0.025 | 0.475 | 0 | $0 |
| Constant base-rate (0.475) | 0.249 | 0.000 | 0.525 | 0 | $0 |
| Constant majority-class (0.0) | 0.475 | 0.475 | 0.525 | 0 | $0 |

- **The constrained LLM is barely better than guessing 0.5** (Brier 0.227 vs
  0.250). Its outputs are spiky and overconfident — 86\u00d7 "0.0", 76\u00d7 in
  [0.9, 1.0], 26\u00d7 "0.5" — and miscalibrated at the extremes: when it says
  0.0 the statement is actually true 24% of the time; when it says ~0.93,
  true only 76% of the time. Directionally better than chance (73.5%
  accuracy) but nearly useless *as probabilities*.
- **Model-selection note:** 8 cheap OpenRouter models (\u2264$0.10/M input, prices
  verified 2026-09-30) were probed with the exact task prompt before the run.
  llama-3.1-8b, qwen3-30b, nova-micro and command-r7b collapsed to constant
  "0"/"0.0" (nova-micro even answered 0.99 on a false-labeled item);
  gpt-oss-120b and deepseek-v4.1-flash returned empty strings. mistral-nemo
  ($0.019/M in, $0.030/M out) was the only one producing varied,
  directionally sensible outputs — the fairest "just prompt an LLM"
  representative, and it still fails as a probability machine.
- **Cost:** Jev is ~8\u00d7 pricier per decision ($0.0130 vs $0.0016 per 1k) but
  ~9\u00d7 better on Brier — and both are fractions of a cent per thousand
  decisions. At 1M decisions that's ~$13 (Jev) vs ~$1.60 (LLM). The LLM
  alternative isn't viable regardless of price: you can't buy calibration
  with it at any discount.
- **Latency:** Jev is ~5\u00d7 faster (0.27 s vs 1.38 s mean).
- **Exact symbolic baseline (50 arithmetic items):** Brier **0.0** vs Jev's
  **0.051** on the same subset — perfect where it applies.
- Amusing calibration footnote: the base-rate constant has ECE **0.000**
  (perfectly calibrated) and is still useless — calibration without
  sharpness scores nothing. Brier captures both; ECE alone doesn't.
- Spend: $0.0003 for the 200 LLM calls (OpenRouter reported usage.cost
  directly); the $2 circuit breaker was never approached.

**Impact.** The build-vs-buy question resolves decisively for Jev on this task
class: a naively constrained cheap LLM does not substitute for a calibrated
decision model — its numbers look like probabilities but don't behave like
them. The 8\u00d7 cost premium buys 9\u00d7 better calibration *and* 5\u00d7 lower latency,
at absolute costs (~$13 per million decisions) that are negligible for any
serious use. The symbolic result sharpens the Phase 1 caveat into a rule:
where exact verification is possible (arithmetic, logic, lookups), use the
exact checker (Brier 0.0) — reserve Jev for judgments no symbolic rule can
express. Caveat: this tests the *naive* constrained-LLM approach; fancier
elicitation (reasoning-then-score, logit-based) might do better and is out
of scope here.

## Phase 6 — Decision value via threshold tuning (complete, 2026-09-30)

**Hypothesis.** When false positives and false negatives carry asymmetric
costs, tuning the decision threshold on Jev's scores (chosen on tuning data)
beats a naive 0.5 rule on held-out data. The textbook expectation is that the
optimal threshold tracks t* = c_fp / (c_fp + c_fn).

**Why it matters.** Calibration is only useful if it converts into better
decisions. This is the economic test of Jev's "probabilities you can act on"
claim: do the scores let you set thresholds that minimize expected cost when
mistakes are not symmetric?

**What the test showed.** Pure local analysis on the 200 Phase 1 items — no new
API calls. For each cost scenario (FP:FN ∈ {1:1, 3:1, 10:1, 1:3, 1:10}), 200
repeats of a stratified 100/100 tuning/holdout split (by label × difficulty);
threshold grid-searched 0.01–0.99 on tuning, evaluated on holdout against naive
0.5, always-yes, and always-no. Reference confusion matrix at 0.5: TP=95, FP=4,
FN=0, TN=101 — the model's errors are one-sided; it never misses a true
statement, it only overstates false ones.

- **FP expensive (10:1): tuning pays off.** Holdout expected cost per decision:
  tuned 0.164 vs naive 0.5's 0.215 — about a 23% relative reduction. The tuned
  threshold beat 0.5 in 64% of repeats. Mean chosen threshold 0.68 (theory:
  0.91).
- **Near-symmetric costs (1:1, 3:1): no benefit.** Tuned and naive are
  indistinguishable (1:1: 0.0204 vs 0.0203; 3:1: 0.0578 vs 0.0572); tuning
  beats 0.5 in only 37–47% of repeats — pure noise. 0.5 is already optimal.
- **FN expensive (1:3, 1:10): tuning hurts on holdout.** 1:3: tuned 0.0267 vs
  naive 0.0196 (36% worse); 1:10: tuned 0.0532 vs naive 0.0196, with 5× the
  variance. The tuner raises the threshold (mean 0.57) to shave false positives
  on 100 tuning items, but on holdout that occasionally clips a low-scoring
  true item — and each clip costs c_fn. Small-sample overfitting.
- **Trivial rules are far worse everywhere** (always-yes/always-no cost
  0.47–5.24 per decision), confirming the scores carry real decision value.
- **The empirical optimum disagrees with the textbook t*.** Chosen thresholds
  landed at 0.57–0.68 in *every* scenario, vs. theoretical 0.09–0.91. With a
  near-perfect separator and one-sided errors, the tuner can only cut false
  positives — it has no false negatives to fix — so it always pushes the
  threshold up regardless of the cost ratio.

**Impact.** Tune the threshold when false positives are expensive (10:1 saved
~23% vs. 0.5); don't bother near symmetric costs, where 0.5 is already
optimal; and never let an empirical tuner raise the threshold when misses are
expensive — the model is recall-perfect on true statements, so 0.5 is the safe
choice and tuning just chases noise on small samples. The deeper lesson: with
well-separated scores, the exact threshold matters less than the error
asymmetry — the one-sided error structure, not the cost ratio, drove where the
tuner went. Caveats: 100-item splits are small, and synthetic true/false items
are the easiest case; real deployments need re-tuning on real decision data.

---

## Spend log

| Phase | Calls | Est. spend (USD) |
|-------|-------|------------------|
| 1 — calibration | 200 | 0.0026 |
| 2 — stability | 200 | 0.0026 |
| 3 — robustness | 144 | 0.0019 |
| 4 — joint questions | 38 (+6 probes) | 0.0006 |
| 5 — baselines (cheap LLM) | 200 (+~9 probes) | 0.0003 |
| 6 — decision value | 0 (local analysis) | 0 |
| Smoke tests | 6 | ~0.0001 |
| **Total to date** | **~800** | **~0.008** |

Costs are estimated from input tokens at the public Jev price ($0.042 per
million input tokens; output free) because the Jev API responses carried no
`usage.cost` field; the Phase 5 LLM baseline reported `usage.cost` directly.
A $2.00 circuit breaker was armed and never approached.
Budget provided: $10.00 — all six phases consumed under 0.1% of it.
