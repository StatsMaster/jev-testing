"""Phase 1 — calibration: one Noul call per labeled statement (~200 calls).

Usage:
    python jev_eval_calibration.py <dataset.json> <out_prefix>

Writes:
    <out_prefix>-raw.jsonl       one record per item (probability, latency, ...)
    <out_prefix>-metrics.json    Brier, ECE (10 equal-width bins), reliability
                                 table, accuracy, per-difficulty breakdown.

Politeness: 1.5 s pause between calls; two retries with 5 s / 15 s backoff,
then the item is recorded as failed and we move on.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time

from jev_eval_common import (
    MODEL,
    PAUSE_S,
    SPEND_CAP_USD,
    ask_noul,
    make_client,
)

N_BINS = 10


def reliability(rows: list[dict]) -> tuple[float, float, list[dict]]:
    """Return (brier, ece, table) over successful rows with p and true_label."""
    ok = [r for r in rows if r.get("p") is not None]
    n = len(ok)
    if n == 0:
        return float("nan"), float("nan"), []
    brier = sum((r["p"] - r["true_label"]) ** 2 for r in ok) / n
    table = []
    ece = 0.0
    for b in range(N_BINS):
        lo, hi = b / N_BINS, (b + 1) / N_BINS
        in_bin = [r for r in ok if (lo <= r["p"] < hi) or (b == N_BINS - 1 and r["p"] == 1.0)]
        if not in_bin:
            table.append({"bin": [lo, hi], "n": 0, "mean_p": None, "obs_freq": None})
            continue
        mean_p = sum(r["p"] for r in in_bin) / len(in_bin)
        obs = sum(r["true_label"] for r in in_bin) / len(in_bin)
        ece += (len(in_bin) / n) * abs(obs - mean_p)
        table.append({"bin": [lo, hi], "n": len(in_bin), "mean_p": mean_p, "obs_freq": obs})
    return brier, ece, table


def main() -> int:
    dataset_path, out_prefix = sys.argv[1], sys.argv[2]
    with open(dataset_path) as f:
        items = json.load(f)
    if len(items) != 200:
        print(f"[warn] expected 200 items, got {len(items)}", flush=True)

    client = make_client()
    raw_path = f"{out_prefix}-raw.jsonl"
    n_failed = 0
    spend_total = 0.0
    n_cost_missing = 0
    stopped_early = None
    try:
        with open(raw_path, "w") as out:
            for i, item in enumerate(items):
                rec = {
                    "id": item["id"],
                    "text": item["text"],
                    "true_label": item["true_label"],
                    "domain": item["domain"],
                    "difficulty": item["difficulty"],
                    "model": MODEL,
                    "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "p": None,
                    "latency_s": None,
                    "error": None,
                }
                try:
                    p, answers, latency, cost, basis = ask_noul(client, item["text"])
                    rec.update(p=p, latency_s=round(latency, 3), raw_answers=answers)
                    rec["cost_usd"] = cost
                    rec["cost_basis"] = basis
                    if basis == "missing":
                        n_cost_missing += 1
                    spend_total += cost
                except Exception as exc:  # noqa: BLE001
                    rec["error"] = f"{type(exc).__name__}: {exc}"
                    n_failed += 1
                rec["spend_usd_running_total"] = round(spend_total, 6)
                out.write(json.dumps(rec) + "\n")
                out.flush()
                print(f"[{i + 1}/{len(items)}] {item['id']} p={rec['p']} "
                      f"cost={rec.get('cost_usd')} spend=${spend_total:.4f} err={rec['error']}", flush=True)
                if spend_total > SPEND_CAP_USD:
                    stopped_early = (
                        f"spend cap ${SPEND_CAP_USD:.2f} exceeded after item {i + 1}; "
                        "stopping all further calls"
                    )
                    print("[spend] " + stopped_early, flush=True)
                    break
                if i < len(items) - 1:
                    time.sleep(PAUSE_S)
    finally:
        client.close()

    rows = [json.loads(line) for line in open(raw_path)]
    brier, ece, table = reliability(rows)
    ok = [r for r in rows if r.get("p") is not None]
    acc = sum((r["p"] >= 0.5) == bool(r["true_label"]) for r in ok) / len(ok)
    by_diff: dict[str, dict] = {}
    for diff in ("easy", "ambiguous", "negated"):
        sub = [r for r in ok if r["difficulty"] == diff]
        if not sub:
            by_diff[diff] = {"n": 0, "brier": None, "accuracy": None}
            continue
        b, _, _ = reliability(sub)
        by_diff[diff] = {
            "n": len(sub),
            "brier": b,
            "accuracy": sum((r["p"] >= 0.5) == bool(r["true_label"]) for r in sub) / len(sub),
        }
    lat = [r["latency_s"] for r in ok if r["latency_s"] is not None]
    metrics = {
        "n_items": len(rows),
        "n_success": len(ok),
        "n_failed": n_failed,
        "model": MODEL,
        "stopped_early": stopped_early,
        "spend_usd_total": round(spend_total, 6),
        "spend_cap_usd": SPEND_CAP_USD,
        "n_calls_without_any_cost_basis": n_cost_missing,
        "cost_note": "cost estimated from input_tokens at $0.042/M (output free); usage.cost was absent from responses",
        "brier_score": brier,
        "expected_calibration_error_10bin": ece,
        "accuracy_at_0.5": acc,
        "reliability_table": table,
        "by_difficulty": by_diff,
        "mean_latency_s": sum(lat) / len(lat) if lat else None,
    }
    with open(f"{out_prefix}-metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    print(json.dumps({k: v for k, v in metrics.items() if k != "reliability_table"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
