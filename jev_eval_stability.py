"""Phase 2 — stability: 20 identical Noul calls for each of 10 inputs (~200 calls).

Selection (from the Phase 1 raw JSONL):
- 3 easy items, most confidently correct (p closest to the true label extreme)
- 4 ambiguous items with p in [0.2, 0.8] (the re-ask region); if fewer than
  4 qualify, fill with the ambiguous items closest to 0.5
- 3 negated items spread across the observed p range

Per input report: mean, sample std, min, max, fraction of runs >= 0.5, and
flip fraction = share of runs on the minority side of the 0.5 threshold.

Usage:
    python jev_eval_stability.py <phase1-raw.jsonl> <out_prefix>

Writes:
    <out_prefix>-raw.jsonl    one record per repeat call
    <out_prefix>-stats.json   per-input summary statistics
"""

from __future__ import annotations

import datetime as dt
import json
import statistics
import sys
import time

from jev_eval_common import MODEL, PAUSE_S, SPEND_CAP_USD, ask_noul, make_client

N_REPEATS = 20


def pick(rows: list[dict]) -> list[dict]:
    ok = [r for r in rows if r.get("p") is not None and not r.get("error")]
    easy = sorted(
        [r for r in ok if r["difficulty"] == "easy"],
        key=lambda r: abs(r["p"] - r["true_label"]),
    )[:3]
    amb = [r for r in ok if r["difficulty"] == "ambiguous"]
    in_band = [r for r in amb if 0.2 <= r["p"] <= 0.8]
    in_band.sort(key=lambda r: r["p"])
    chosen_amb = in_band[:4]
    if len(chosen_amb) < 4:
        rest = sorted(
            [r for r in amb if r not in chosen_amb], key=lambda r: abs(r["p"] - 0.5)
        )
        chosen_amb += rest[: 4 - len(chosen_amb)]
    neg = sorted([r for r in ok if r["difficulty"] == "negated"], key=lambda r: r["p"])
    chosen_neg = [neg[i] for i in (0, len(neg) // 2, len(neg) - 1)] if neg else []
    selected = easy + chosen_amb + chosen_neg
    assert len(selected) == 10, f"expected 10 inputs, got {len(selected)}"
    return selected


def main() -> int:
    raw_path, out_prefix = sys.argv[1], sys.argv[2]
    rows = [json.loads(line) for line in open(raw_path)]
    selected = pick(rows)
    print("selected inputs:")
    for s in selected:
        print(f"  {s['id']} [{s['difficulty']}] p={s['p']:.2f} label={s['true_label']}: {s['text'][:60]}")

    client = make_client()
    out_raw = f"{out_prefix}-raw.jsonl"
    stats: list[dict] = []
    spend_total = 0.0
    n_cost_missing = 0
    stopped_early = None
    completed_inputs = 0
    try:
        with open(out_raw, "w") as out:
            for s in selected:
                ps: list[float] = []
                n_fail = 0
                for rep in range(N_REPEATS):
                    rec = {
                        "id": s["id"],
                        "text": s["text"],
                        "true_label": s["true_label"],
                        "domain": s["domain"],
                        "difficulty": s["difficulty"],
                        "repeat": rep,
                        "model": MODEL,
                        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                        "p": None,
                        "latency_s": None,
                        "error": None,
                    }
                    try:
                        p, _, latency, cost, basis = ask_noul(client, s["text"])
                        rec.update(p=p, latency_s=round(latency, 3))
                        rec["cost_usd"] = cost
                        rec["cost_basis"] = basis
                        if basis == "missing":
                            n_cost_missing += 1
                        spend_total += cost
                        ps.append(p)
                    except Exception as exc:  # noqa: BLE001
                        rec["error"] = f"{type(exc).__name__}: {exc}"
                        n_fail += 1
                    rec["spend_usd_running_total"] = round(spend_total, 6)
                    out.write(json.dumps(rec) + "\n")
                    out.flush()
                    if spend_total > SPEND_CAP_USD:
                        stopped_early = (
                            f"spend cap ${SPEND_CAP_USD:.2f} exceeded during {s['id']} "
                            f"repeat {rep}; stopping all further calls"
                        )
                        print("[spend] " + stopped_early, flush=True)
                        break
                    if rep < N_REPEATS - 1:
                        time.sleep(PAUSE_S)
                frac_ge = sum(1 for p in ps if p >= 0.5) / len(ps) if ps else None
                stats.append(
                    {
                        "id": s["id"],
                        "text": s["text"],
                        "true_label": s["true_label"],
                        "difficulty": s["difficulty"],
                        "phase1_p": s["p"],
                        "n_repeats": N_REPEATS,
                        "n_success": len(ps),
                        "n_failed": n_fail,
                        "mean_p": statistics.fmean(ps) if ps else None,
                        "std_p": statistics.stdev(ps) if len(ps) > 1 else 0.0,
                        "min_p": min(ps) if ps else None,
                        "max_p": max(ps) if ps else None,
                        "frac_ge_0.5": frac_ge,
                        "flip_fraction": min(frac_ge, 1 - frac_ge) if frac_ge is not None else None,
                    }
                )
                completed_inputs += 1
                st = stats[-1]
                fmt = lambda v: "n/a" if v is None else f"{v:.3f}"
                print(f"done {s['id']}: n={len(ps)} mean={fmt(st['mean_p'])} "
                      f"std={fmt(st['std_p'])} flip={fmt(st['flip_fraction'])} "
                      f"spend=${spend_total:.4f}", flush=True)
                if stopped_early:
                    break
                time.sleep(PAUSE_S)
    finally:
        client.close()

    summary = {
        "n_inputs_selected": len(selected),
        "n_inputs_completed": completed_inputs,
        "stopped_early": stopped_early,
        "spend_usd_total": round(spend_total, 6),
        "spend_cap_usd": SPEND_CAP_USD,
        "n_calls_without_any_cost_basis": n_cost_missing,
        "cost_note": "cost estimated from input_tokens at $0.042/M (output free); usage.cost was absent from responses",
        "per_input": stats,
    }
    with open(f"{out_prefix}-stats.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("wrote", f"{out_prefix}-stats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
