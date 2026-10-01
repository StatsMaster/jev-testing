# Jev as an MCP tool: two reliability patterns

A design sketch for calling Jev the way an LLM calls any other tool —
as a calibrated-judgment sidecar. The two patterns below are the ones worth
building first: both make an LLM system more reliable, one constraining what
it may **say**, the other what it may **do**.

Core architectural bet: the LLM *proposes*, Jev *disposes*. The big model does
language — understanding, generating, framing. Jev does one thing it was
trained for: turning a proposition into a calibrated number. This split
exists because LLM verbalized confidence is not trustworthy — our Phase 5
baseline put a constrained cheap LLM at Brier 0.227, barely better than
guessing 0.5; its outputs look like probabilities but don't behave like them.
Jev measured 0.026 on the same items.

As an MCP tool the surface is small:

- `noul(statement) → {probability}` — how likely is this claim true?
- `choice(question, options) → {probabilities}` — which option is best?
- `score(item, rubric) → {probability}` — how strongly does this meet the bar?

The agent's system prompt (or orchestrator code) decides *when* to call; the
evaluation results below dictate *how* to call.

---

## Pattern 1 — Hallucination firewall (constrain what the system may say)

**The loop.** A generator LLM drafts an answer. A splitter reduces the draft
to atomic, self-contained declarative claims. Each claim gets exactly one
`noul` call. Policy on the returned probability p:

- p ≥ τ_accept → keep the claim as stated;
- τ_review ≤ p < τ_accept → hedge it, or re-check it (retrieve more evidence,
  then re-ask);
- p < τ_review → drop the claim.

The generator and the verifier are different systems, so the agent is never
grading its own homework.

**Calling pattern (each rule is bought by a phase result):**

1. **One claim per call, never bundled.** Phase 4: bundling 5 questions in one
   call drifts each answer by ~0.1 on average and flips 8.6% of decisions.
   Parallel single calls are fine; one multi-question call is not.
2. **`state` holds the claim and nothing else.** Phase 3: appending 2–3
   irrelevant sentences drags confident scores toward 0.5 and flips 41.7% of
   decisions. No chat history, no retrieved passages, no boilerplate in the
   Noul state — the claim re-stated cleanly by the system.
3. **Normalize convoluted phrasing in the splitter.** Phase 2 and Phase 3 both
   locate the model's weak spot in complex phrasing (negated comparatives,
   stacked clauses). The splitter should resolve pronouns, unpack double
   negatives, and emit simple declarative sentences. Restating in your own
   words is safe — Phase 3 paraphrase flips were only 4.2%.
4. **Set τ from calibration on your domain.** Phase 1: the scores are
   calibrated, so "drop everything below 0.7" is a real policy with a
   predictable error rate, not a vibe. Re-run the Phase 1 protocol (a few
   hundred labeled claims from your domain) to pick τ empirically.
5. **Exact-checkable claims bypass Jev.** Phase 5: a symbolic checker scored
   Brier 0.0 on arithmetic where Jev scored 0.051. Dates, arithmetic, lookups,
   citations — verify exactly; reserve Jev for judgments no rule can express.

**Budget.** Phase 5: ~$0.013 per 1,000 decisions, ~0.27 s per call. A 10-claim
answer costs roughly a tenth of a cent and ~3 s of sequential calls (less with
parallel singles). The firewall is reproducible run-to-run (Phase 2: zero
decision flips on identical repeats).

---

## Pattern 2 — Triage with real operating points (constrain what the system may do)

**The loop.** The agent processes each item — support ticket, flagged post,
candidate action — and calls `noul` on a routing proposition, e.g.
*"This ticket is routine and safe to resolve without human review."*
Three-way policy:

- p ≥ τ_auto → auto-handle;
- τ_review ≤ p < τ_auto → draft the action, hold for human approval;
- p < τ_review → escalate to the human queue immediately.

**Threshold selection is Phase 6, applied.** Tune τ from the cost ratio of a
bad auto-action vs. reviewer time — that is exactly the expected-cost tuning
Phase 6 ran, and its warnings transfer directly:

1. **Tune only when the expensive errors are false positives.** Phase 6:
   tuning paid off at 10:1 FP cost (~23% cost reduction vs. 0.5) and was noise
   at symmetric costs.
2. **When misses are expensive, hold at 0.5 and don't let the tuner raise the
   threshold.** Phase 6: empirical tuning *hurt* at 1:3/1:10 — it chased noise
   on small tuning samples and clipped true items at 3–10× cost.
3. **Re-tune on your real decision data.** All our thresholds come from
   synthetic true/false; your ticket distribution is the only tuning set that
   counts.
4. **Know your error asymmetry, not just your cost ratio.** Phase 6's surprise:
   the empirical optimum (0.57–0.68) ignored the textbook t* in every scenario
   because the model's errors were one-sided. Measure which side *your*
   errors fall on before trusting the formula.
5. **Three tiers, not five.** Phase 2: outputs look quantized (~32 distinct
   values across 200 repeats). Don't over-slice; auto / review / escalate is
   plenty.

**Why the staffing math is trustworthy.** Because the scores are calibrated
(Phase 1), "auto-handle at τ" converts to a predicted error rate, which
converts to expected escalations per day, which converts to reviewer
headcount. That chain is what makes these *operating points* rather than
hopes.

---

## How they compose

One pipeline, same tool, two gates:

1. Support agent drafts a reply → **firewall** checks each factual claim
   (drop/hedge the weak ones).
2. The surviving reply goes to **triage**: `noul("Sending this reply as-is is
   safe and correct")` → auto-send, hold-for-review, or escalate.

Firewall on the way in (*is this safe to repeat?*), triage on the way out
(*is this safe to do?*).

---

## Open questions (what we'd still need to test)

- **Splitter quality.** The firewall inherits the splitter's failures:
  compound claims and unresolved pronouns re-introduce the phrasing
  sensitivity Phase 3 found. The splitter is part of the system under test.
- **Domain transfer.** Every number here is synthetic true/false. A real
  deployment needs its own labeled calibration set — the Phase 1 protocol,
  run on a few hundred real tickets/claims.
- **Adversarial dilution.** Phase 3's padding finding cuts both ways: a user
  could pad a prompt to drag the firewall's confidence toward 0.5. Keep
  untrusted user text out of the Noul `state`; score the system's restatement,
  not the raw message.
- **Correlated failures.** The LLM and Jev can share blind spots (same web in
  their training data). This is defense in depth, not immunity — the firewall
  catches confabulation, not shared misconceptions.
- **Fancier elicitation.** Phase 5 tested the naive "output a number" LLM
  baseline only. Reasoning-then-score or logit-based extraction might narrow
  the gap; out of scope for now.
