# Phase 3 — Robustness to rewording (fragment for EVALUATION.md)

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
