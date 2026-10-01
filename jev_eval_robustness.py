"""Phase 3 — robustness to rewording: 3 variants x 48 items = ~144 Noul calls.

Usage:
    python jev_eval_robustness.py <variants.json> <out_prefix>

Writes:
    <out_prefix>-raw.jsonl      one record per variant call
    <out_prefix>-stats.json      per-variant-class shift metrics, flip rates,
                                Brier vs labels, and the Phase 1 reference.

Variant classes (all hand-verified to preserve the original true/false label):
    paraphrase   meaning-preserving rewrite, different words and structure
    padding      original statement + 2-3 irrelevant filler sentences
    adversarial  loaded/emotional framing (e.g. "Only a fool would deny that X")
                 that endorses the embedded claim, keeping the truth value

The byte-identical Phase 1 Noul question (NOUL_INSTRUCTIONS) is used for every
variant. Politeness: 1.5 s pause between calls; two retries with 5 s / 15 s
backoff, then the variant is recorded as failed and we move on.
"""

from __future__ import annotations

import datetime as dt
import json
import statistics
import sys
import time

from jev_eval_common import (
    JEV_INPUT_USD_PER_MTOKEN,
    MODEL,
    PAUSE_S,
    SPEND_CAP_USD,
    ask_noul,
    make_client,
)

VARIANT_CLASSES = ("paraphrase", "padding", "adversarial")
PHASE1_BRIER_REFERENCE = 0.026  # calibration Brier on the 200 original items


def tokens_from_cost(cost_usd: float, basis: str) -> int | None:
    """Recover input tokens when the cost was estimated from them."""
    if basis == "estimated_from_tokens" and cost_usd > 0:
        return int(round(cost_usd * 1e6 / JEV_INPUT_USD_PER_MTOKEN))
    return None


def quantile(sorted_vals: list[float], q: float) -> float | None:
    if not sorted_vals:
        return None
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def class_stats(rows: list[dict]) -> dict:
    ok = [r for r in rows if r.get("p_new") is not None and r.get("p_original") is not None]
    n = len(ok)
    if n == 0:
        return {"n": 0, "n_success": 0}
    shifts = sorted(abs(r["p_new"] - r["p_original"]) for r in ok)
    flips = sum((r["p_new"] >= 0.5) != (r["p_original"] >= 0.5) for r in ok)
    brier = sum((r["p_new"] - r["label"]) ** 2 for r in ok) / n
    acc = sum((r["p_new"] >= 0.5) == bool(r["label"]) for r in ok) / n
    lat = [r["latency_s"] for r in ok if r["latency_s"] is not None]
    return {
        "n": len(rows),
        "n_success": n,
        "n_failed": len(rows) - n,
        "abs_shift_vs_original": {
            "mean": statistics.fmean(shifts),
            "p50": quantile(shifts, 0.50),
            "p90": quantile(shifts, 0.90),
            "max": max(shifts),
        },
        "flip_rate_at_0.5_vs_original_decision": flips / n,
        "n_flips": flips,
        "brier_score_vs_labels": brier,
        "accuracy_at_0.5_vs_labels": acc,
        "mean_latency_s": statistics.fmean(lat) if lat else None,
    }


def main() -> int:
    variants_path, out_prefix = sys.argv[1], sys.argv[2]
    with open(variants_path) as f:
        items = json.load(f)
    calls = [(item, vc) for item in items for vc in VARIANT_CLASSES]
    print(f"[info] {len(items)} items x {len(VARIANT_CLASSES)} variants = {len(calls)} calls", flush=True)

    client = make_client()
    raw_path = f"{out_prefix}-raw.jsonl"
    n_failed = 0
    spend_total = 0.0
    n_cost_missing = 0
    stopped_early = None
    try:
        with open(raw_path, "w") as out:
            for i, (item, vc) in enumerate(calls):
                text = item[vc]
                rec = {
                    "item_id": item["id"],
                    "variant_class": vc,
                    "variant_text": text,
                    "label": item["label"],
                    "original_text": item["original"],
                    "p_original": item["p_original"],
                    "difficulty": item.get("difficulty"),
                    "domain": item.get("domain"),
                    "model": MODEL,
                    "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "p_new": None,
                    "latency_s": None,
                    "input_tokens": None,
                    "cost_usd": None,
                    "cost_basis": None,
                    "error": None,
                }
                try:
                    p, answers, latency, cost, basis = ask_noul(client, text)
                    rec.update(
                        p_new=p,
                        latency_s=round(latency, 3),
                        input_tokens=tokens_from_cost(cost, basis),
                        cost_usd=cost,
                        cost_basis=basis,
                        raw_answers=answers,
                    )
                    if basis == "missing":
                        n_cost_missing += 1
                    spend_total += cost
                except Exception as exc:  # noqa: BLE001
                    rec["error"] = f"{type(exc).__name__}: {exc}"
                    n_failed += 1
                rec["spend_usd_running_total"] = round(spend_total, 6)
                out.write(json.dumps(rec) + "\n")
                out.flush()
                print(f"[{i + 1}/{len(calls)}] {item['id']}/{vc} p_new={rec['p_new']} "
                      f"p_orig={rec['p_original']} cost={rec.get('cost_usd')} "
                      f"spend=${spend_total:.4f} err={rec['error']}", flush=True)
                if spend_total > SPEND_CAP_USD:
                    stopped_early = (
                        f"spend cap ${SPEND_CAP_USD:.2f} exceeded after call {i + 1}; "
                        "stopping all further calls"
                    )
                    print("[spend] " + stopped_early, flush=True)
                    break
                if i < len(calls) - 1:
                    time.sleep(PAUSE_S)
    finally:
        client.close()

    rows = [json.loads(line) for line in open(raw_path)]
    by_class = {vc: class_stats([r for r in rows if r["variant_class"] == vc]) for vc in VARIANT_CLASSES}
    overall = class_stats(rows)
    by_difficulty: dict[str, dict] = {}
    for diff in ("easy", "ambiguous", "negated"):
        by_difficulty[diff] = class_stats([r for r in rows if r["difficulty"] == diff])
    worst = sorted(
        (r for r in rows if r.get("p_new") is not None),
        key=lambda r: abs(r["p_new"] - r["p_original"]),
        reverse=True,
    )[:10]
    stats = {
        "n_calls_planned": len(calls),
        "n_calls_made": len(rows),
        "n_failed": n_failed,
        "model": MODEL,
        "stopped_early": stopped_early,
        "spend_usd_total": round(spend_total, 6),
        "spend_cap_usd": SPEND_CAP_USD,
        "n_calls_without_any_cost_basis": n_cost_missing,
        "cost_note": "cost estimated from input_tokens at $0.042/M (output free); usage.cost was absent from responses",
        "phase1_brier_reference": PHASE1_BRIER_REFERENCE,
        "phase1_brier_note": "reference only: Brier of the 200 original Phase 1 items (0.026)",
        "by_variant_class": by_class,
        "by_difficulty": by_difficulty,
        "overall": overall,
        "largest_shifts": [
            {
                "item_id": r["item_id"],
                "variant_class": r["variant_class"],
                "label": r["label"],
                "p_original": r["p_original"],
                "p_new": r["p_new"],
                "abs_shift": abs(r["p_new"] - r["p_original"]),
                "flipped": (r["p_new"] >= 0.5) != (r["p_original"] >= 0.5),
                "variant_text": r["variant_text"],
            }
            for r in worst
        ],
    }
    with open(f"{out_prefix}-stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    print(json.dumps({k: v for k, v in stats.items() if k not in ("largest_shifts",)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
