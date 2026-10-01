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
