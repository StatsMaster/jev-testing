#!/usr/bin/env python3
"""Phase 6 — Decision value via threshold tuning (pure local analysis).

Question: does tuning the decision threshold on Jev's Phase 1 scores beat a
naive 0.5 rule when false positives and false negatives carry asymmetric costs?

Method (no API calls; everything below runs on the Phase 1 raw results):
  - For each cost scenario (FP:FN in {1:1, 3:1, 10:1, 1:3, 1:10}):
    - Repeat 200 times:
      - Stratified 100/100 split (by label x difficulty class).
      - On the tuning half, grid-search threshold t in [0.01, 0.99] (step
        0.01) minimizing expected cost per decision. Ties are broken by taking
        the median of the cost-minimizing thresholds.
      - On the holdout half, score four policies by expected cost per decision:
        tuned threshold, naive 0.5, always-yes, always-no.
    - Aggregate: mean +/- sample std of holdout expected cost per policy,
      mean +/- std of the chosen threshold, and the share of repeats where
      the tuned threshold strictly beats naive 0.5 on holdout.
  - Reference: the full-data confusion matrix at 0.5, and the theoretical
    cost-minimizing threshold t* = c_fp / (c_fp + c_fn) that a perfectly
    calibrated model would use.

Expected cost per decision for a policy: mean over items of
    c_fp  if predicted yes (p >= t) and label is 0,
    c_fn  if predicted no  (p <  t) and label is 1,
    0     otherwise.
"""

from __future__ import annotations

import json
import math
import random
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parent
RAW_PATH = REPO / "results" / "calibration-2026-09-30-raw.jsonl"
OUT_PATH = REPO / "results" / "decision-value-2026-09-30-stats.json"

SCENARIOS = [(1, 1), (3, 1), (10, 1), (1, 3), (1, 10)]  # (c_fp, c_fn)
N_REPEATS = 200
GRID = [i / 100.0 for i in range(1, 100)]  # 0.01 .. 0.99
SEED = 20260930


def load_items() -> list[dict]:
    items = []
    for line in RAW_PATH.read_text().splitlines():
        rec = json.loads(line)
        if rec.get("error"):
            continue
        items.append(
            {
                "id": rec["id"],
                "p": float(rec["p"]),
                "y": int(rec["true_label"]),
                "difficulty": rec["difficulty"],
            }
        )
    return items


def expected_cost(items: list[dict], threshold: float, c_fp: float, c_fn: float) -> float:
    """Mean cost per decision for threshold rule 'predict yes iff p >= t'."""
    total = 0.0
    for it in items:
        pred_yes = it["p"] >= threshold
        if pred_yes and it["y"] == 0:
            total += c_fp
        elif not pred_yes and it["y"] == 1:
            total += c_fn
    return total / len(items)


def tune_threshold(tuning: list[dict], c_fp: float, c_fn: float) -> float:
    costs = [(t, expected_cost(tuning, t, c_fp, c_fn)) for t in GRID]
    best = min(c for _, c in costs)
    winners = [t for t, c in costs if c == best]
    # Tie-break: median of the cost-minimizing thresholds (deterministic).
    winners.sort()
    return winners[len(winners) // 2]


def stratified_split(rng: random.Random, items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Stratified 100/100 split by (label, difficulty class), half per stratum."""
    strata: dict[tuple[int, str], list[dict]] = {}
    for it in items:
        strata.setdefault((it["y"], it["difficulty"]), []).append(it)
    tuning, holdout = [], []
    for key in sorted(strata):
        members = strata[key][:]
        rng.shuffle(members)
        half = len(members) // 2
        tuning.extend(members[:half])
        holdout.extend(members[half:])
    rng.shuffle(tuning)
    rng.shuffle(holdout)
    return tuning, holdout


def run() -> dict:
    items = load_items()
    assert len(items) == 200, f"expected 200 usable items, got {len(items)}"
    rng = random.Random(SEED)

    # Reference confusion matrix at naive 0.5 on the full 200.
    cm = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for it in items:
        pred_yes = it["p"] >= 0.5
        if pred_yes and it["y"] == 1:
            cm["tp"] += 1
        elif pred_yes and it["y"] == 0:
            cm["fp"] += 1
        elif not pred_yes and it["y"] == 1:
            cm["fn"] += 1
        else:
            cm["tn"] += 1

    scenarios_out = []
    for c_fp, c_fn in SCENARIOS:
        t_star = c_fp / (c_fp + c_fn)  # theoretical optimum for a calibrated model
        cost_tuned, cost_naive, cost_yes, cost_no = [], [], [], []
        thresholds, beats = [], []
        for _ in range(N_REPEATS):
            tuning, holdout = stratified_split(rng, items)
            t = tune_threshold(tuning, c_fp, c_fn)
            c_t = expected_cost(holdout, t, c_fp, c_fn)
            c_n = expected_cost(holdout, 0.5, c_fp, c_fn)
            c_y = expected_cost(holdout, 0.0, c_fp, c_fn)   # always-yes
            c_x = expected_cost(holdout, 2.0, c_fp, c_fn)   # always-no (t above all p)
            cost_tuned.append(c_t)
            cost_naive.append(c_n)
            cost_yes.append(c_y)
            cost_no.append(c_x)
            thresholds.append(t)
            beats.append(c_t < c_n)

        def ms(xs: list[float]) -> dict:
            return {
                "mean": statistics.fmean(xs),
                "std": statistics.stdev(xs) if len(xs) > 1 else 0.0,
            }

        scenarios_out.append(
            {
                "cost_ratio_fp_fn": f"{c_fp}:{c_fn}",
                "c_fp": c_fp,
                "c_fn": c_fn,
                "theoretical_threshold": round(t_star, 4),
                "n_repeats": N_REPEATS,
                "holdout_expected_cost_per_decision": {
                    "tuned_threshold": ms(cost_tuned),
                    "naive_0.5": ms(cost_naive),
                    "always_yes": ms(cost_yes),
                    "always_no": ms(cost_no),
                },
                "chosen_threshold": ms(thresholds),
                "fraction_tuned_beats_naive": statistics.fmean(beats),
                "fraction_tuned_leq_naive": statistics.fmean(
                    [c_t <= c_n for c_t, c_n in zip(cost_tuned, cost_naive)]
                ),
            }
        )

    stats = {
        "phase": 6,
        "name": "decision value via threshold tuning",
        "date": "2026-09-30",
        "seed": SEED,
        "n_items": len(items),
        "n_repeats_per_scenario": N_REPEATS,
        "split": "stratified 100 tuning / 100 holdout by (label, difficulty)",
        "threshold_grid": {"min": 0.01, "max": 0.99, "step": 0.01},
        "cost_basis": "expected cost per decision in cost units (FP cost = c_fp, FN cost = c_fn)",
        "confusion_matrix_at_0.5_full_data": cm,
        "accuracy_at_0.5_full_data": (cm["tp"] + cm["tn"]) / len(items),
        "scenarios": scenarios_out,
    }
    OUT_PATH.write_text(json.dumps(stats, indent=2) + "\n")
    return stats


def main() -> None:
    stats = run()
    print(f"Wrote {OUT_PATH}")
    for s in stats["scenarios"]:
        hc = s["holdout_expected_cost_per_decision"]
        t, n = hc["tuned_threshold"]["mean"], hc["naive_0.5"]["mean"]
        rel = (n - t) / n if n else 0.0
        print(
            f"FP:FN {s['cost_ratio_fp_fn']:>5} | tuned {t:.4f}±{hc['tuned_threshold']['std']:.4f} "
            f"| naive {n:.4f}±{hc['naive_0.5']['std']:.4f} "
            f"| always-yes {hc['always_yes']['mean']:.4f} | always-no {hc['always_no']['mean']:.4f} "
            f"| rel. gain {100*rel:5.1f}% "
            f"| mean t {s['chosen_threshold']['mean']:.3f}±{s['chosen_threshold']['std']:.3f} "
            f"(t*={s['theoretical_threshold']}) "
            f"| beats 0.5: {100*s['fraction_tuned_beats_naive']:.1f}%"
        )
    cm = stats["confusion_matrix_at_0.5_full_data"]
    print(f"Confusion matrix @0.5 (n=200): TP={cm['tp']} FP={cm['fp']} FN={cm['fn']} TN={cm['tn']}")


if __name__ == "__main__":
    main()
