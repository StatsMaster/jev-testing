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
