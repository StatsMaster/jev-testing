"""Phase 4 — joint-question interference: do bundled questions change each answer?

Scientific question: does asking several Noul questions in ONE system_one call
change each answer versus asking them singly? (The tutorial pattern bundles
Noul+Choice+Score per request, so this is a real API-design concern.)

Bundling mechanism (verified by --probe): a single system_one call whose
``state`` is one string holding a numbered list of statements, with one Noul
question per statement in the ``questions`` mapping. Each Noul's instructions
point at exactly one numbered statement. This is the smallest mechanism that
yields clean per-statement probabilities -- one call, N answers.

Usage:
    python jev_eval_joint.py --probe        # <= a few calls; prints full answers dump
    python jev_eval_joint.py --run         # full experiment (~37 calls)

Writes (under results/):
    joint-2026-09-30-raw.jsonl    one record per measurement
    joint-2026-09-30-stats.json   drift / flip / position-effect metrics
    phase4-summary.md             Hypothesis / Why it matters / What it showed / Impact

Auth, retries, pacing, and the $2 spend circuit breaker follow jev_eval_common.
"""

from __future__ import annotations

import datetime as dt
import json
import random
import sys
import time

from jev_eval_common import (
    MODEL,
    NOUL_INSTRUCTIONS,
    PAUSE_S,
    SPEND_CAP_USD,
    TIMEOUT,
    extract_cost,
    extract_noul,
    make_client,
)

DATE = "2026-09-30"
N_ITEMS = 30
N_ANCHORS = 5
BUNDLE_SIZE = 5
SEED = 4


def bundled_instructions(k: int) -> str:
    """Per-question instructions for statement number k in a bundled call.

    Kept as close as possible to the byte-identical Phase 1 Noul wording;
    only the statement pointer differs (required to disambiguate).
    """
    return (
        f"Consider statement {k} in the numbered list above, and only that "
        f"statement. Decide whether statement {k} is TRUE (yes-like) or FALSE "
        "(no-like). Give a high probability when the statement is true and a "
        "low probability when it is false."
    )


def bundle_state(texts: list[str]) -> str:
    lines = [
        "Here is a numbered list of statements. Each question refers to "
        "exactly one numbered statement."
    ]
    for i, t in enumerate(texts, start=1):
        lines.append(f"{i}. {t}")
    return "\n".join(lines)


def extract_tokens(dump: dict) -> tuple[int | None, int | None]:
    """Pull input/output token counts out of a response dump, if present."""
    usage = dump.get("usage")
    if isinstance(usage, dict):
        it = usage.get("input_tokens")
        ot = usage.get("output_tokens")
        return (
            int(it) if isinstance(it, (int, float)) else None,
            int(ot) if isinstance(ot, (int, float)) else None,
        )
    return None, None


def ask_bundled(client, items: list[dict]) -> tuple[list[float], dict, float, float, str, int | None, int | None]:
    """One call with one Noul per item.

    Returns (ps, raw_answers, latency, cost, basis, input_tokens, output_tokens).
    """
    from typesafe_sdk import Noul

    questions = {f"q{i}": Noul(instructions=bundled_instructions(i + 1)) for i in range(len(items))}
    last_exc = None
    for sleep_s in (0.0, 5.0, 15.0):
        if sleep_s:
            time.sleep(sleep_s)
        try:
            t0 = time.monotonic()
            r = client.system_one(
                state=bundle_state([it["text"] for it in items]),
                model=MODEL,
                timeout=TIMEOUT,
                questions=questions,
            )
            latency = time.monotonic() - t0
            dump = r.model_dump()
            answers = dump.get("answers", {})
            ps = [extract_noul(answers, f"q{i}") for i in range(len(items))]
            cost, basis = extract_cost(dump)
            itok, otok = extract_tokens(dump)
            return ps, answers, latency, cost, basis, itok, otok
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    raise last_exc


def ask_noul_with_tokens(client, state: str, key: str = "q"):
    """Local variant of common.ask_noul that also returns token counts.

    (common.ask_noul's 5-tuple signature is shared with the calibration and
    stability scripts, so it stays untouched.)
    """
    from typesafe_sdk import Noul

    last_exc = None
    for sleep_s in (0.0, 5.0, 15.0):
        if sleep_s:
            time.sleep(sleep_s)
        try:
            t0 = time.monotonic()
            r = client.system_one(
                state=state,
                model=MODEL,
                timeout=TIMEOUT,
                questions={key: Noul(instructions=NOUL_INSTRUCTIONS)},
            )
            latency = time.monotonic() - t0
            dump = r.model_dump()
            answers = dump.get("answers", {})
            cost, basis = extract_cost(dump)
            itok, otok = extract_tokens(dump)
            return extract_noul(answers, key), answers, latency, cost, basis, itok, otok
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    raise last_exc


def probe() -> int:
    """One bundled call on 5 mixed-label items; dump the raw answers."""
    with open("results/calibration-dataset-2026-09-30.json") as f:
        dataset = json.load(f)
    by_id = {d["id"]: d for d in dataset}
    # 3 true / 2 false, easy, from different domains
    picks = ["cal-001", "cal-051", "cal-101", "cal-026", "cal-076"]
    items = [by_id[p] for p in picks]
    for it in items:
        print(f"  {it['id']} label={it['true_label']} :: {it['text']}", flush=True)
    client = make_client()
    try:
        ps, answers, latency, cost, basis, itok, otok = ask_bundled(client, items)
        print(f"[probe] latency={latency:.2f}s cost={cost} basis={basis} "
              f"input_tokens={itok} output_tokens={otok}", flush=True)
        print("[probe] full answers dump:", flush=True)
        print(json.dumps(answers, indent=2, default=str), flush=True)
        print("[probe] extracted per-statement probabilities:", flush=True)
        for it, p in zip(items, ps):
            print(f"  {it['id']} label={it['true_label']} p={p}", flush=True)
    finally:
        client.close()
    return 0


def select_items(dataset: list[dict], phase1_p: dict[str, float]) -> tuple[list[dict], list[str]]:
    """Stratified pick of 30 items (20 easy / 5 ambiguous / 5 negated),
    true/false balanced, seeded. Returns (items, anchor_ids)."""
    rng = random.Random(SEED)
    chosen: list[dict] = []
    for diff, n in (("easy", 20), ("ambiguous", 5), ("negated", 5)):
        pool = [d for d in dataset if d["difficulty"] == diff]
        trues = [d for d in pool if d["true_label"] == 1]
        falses = [d for d in pool if d["true_label"] == 0]
        half = n // 2
        chosen += rng.sample(trues, half) + rng.sample(falses, n - half)
    # Prefer items near the 0.5 decision boundary for flip sensitivity:
    # swap in the two most boundary-adjacent items if not already picked.
    have = {d["id"] for d in chosen}
    near = sorted(phase1_p, key=lambda i: abs(phase1_p[i] - 0.5))[:6]
    for nid in near:
        if nid not in have:
            d = next(x for x in dataset if x["id"] == nid)
            # replace a same-difficulty, same-label item to keep balance
            victim = next(
                x for x in chosen
                if x["difficulty"] == d["difficulty"] and x["true_label"] == d["true_label"]
            )
            chosen.remove(victim)
            chosen.append(d)
            have.discard(victim["id"])
            have.add(nid)
    rng.shuffle(chosen)
    anchors = [d["id"] for d in rng.sample(chosen, N_ANCHORS)]
    return chosen, anchors


def build_bundles(items: list[dict], anchors: list[str]) -> list[list[dict]]:
    """7 bundles x 5 slots. Each anchor appears twice: once at position 0 of
    one bundle and once at position 4 of another. Non-anchors appear once."""
    rng = random.Random(SEED + 1)
    by_id = {d["id"]: d for d in items}
    anchor_items = [by_id[a] for a in anchors]
    singles = [d for d in items if d["id"] not in set(anchors)]
    rng.shuffle(singles)
    bundles: list[list[dict | None]] = [[None] * BUNDLE_SIZE for _ in range(7)]
    # anchor position-0 appearances -> bundles 0..4; position-4 -> bundles 2..6
    for b, a in enumerate(anchor_items):
        bundles[b][0] = a
    for b, a in enumerate(anchor_items, start=2):
        bundles[b][4] = a
    # fill remaining slots with the 25 single-appearance items
    it = iter(singles)
    for b in bundles:
        for pos in range(BUNDLE_SIZE):
            if b[pos] is None:
                b[pos] = next(it)
    # sanity: every item accounted for
    flat = [d["id"] for b in bundles for d in b]
    assert sorted(flat) == sorted([d["id"] for d in items] + anchors), "slot accounting mismatch"
    return bundles  # type: ignore[return-value]


def run() -> int:
    with open("results/calibration-dataset-2026-09-30.json") as f:
        dataset = json.load(f)
    phase1_p: dict[str, float] = {}
    try:
        with open("results/calibration-2026-09-30-raw.jsonl") as f:
            for line in f:
                r = json.loads(line)
                if r.get("p") is not None:
                    phase1_p[r["id"]] = r["p"]
    except FileNotFoundError:
        print("[warn] phase 1 raw file not found; boundary swap-ins skipped", flush=True)

    items, anchors = select_items(dataset, phase1_p)
    bundles = build_bundles(items, anchors)
    print(f"[run] {len(items)} items, {len(anchors)} anchors, {len(bundles)} bundles", flush=True)

    client = make_client()
    raw_path = f"results/joint-{DATE}-raw.jsonl"
    spend_total = 0.0
    n_failed = 0
    stopped_early = None

    def spend_guard() -> bool:
        return spend_total <= SPEND_CAP_USD

    def rec_base(item: dict, mode: str) -> dict:
        return {
            "id": item["id"],
            "text": item["text"],
            "true_label": item["true_label"],
            "difficulty": item["difficulty"],
            "mode": mode,
            "model": MODEL,
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "phase1_p": phase1_p.get(item["id"]),
            "p": None,
            "latency_s": None,
            "error": None,
        }

    try:
        with open(raw_path, "w") as out:
            # (a) single mode: byte-identical Phase 1 procedure per item
            for i, item in enumerate(items):
                rec = rec_base(item, "single")
                try:
                    p, answers, latency, cost, basis, itok, otok = ask_noul_with_tokens(client, item["text"])
                    rec.update(p=p, latency_s=round(latency, 3), raw_answers=answers,
                               input_tokens=itok, output_tokens=otok)
                    rec["cost_usd"], rec["cost_basis"] = cost, basis
                    nonlocal_spend = cost
                    spend_total += nonlocal_spend
                except Exception as exc:  # noqa: BLE001
                    rec["error"] = f"{type(exc).__name__}: {exc}"
                    n_failed += 1
                rec["spend_usd_running_total"] = round(spend_total, 6)
                out.write(json.dumps(rec) + "\n")
                out.flush()
                print(f"[single {i + 1}/{len(items)}] {item['id']} p={rec['p']} spend=${spend_total:.4f}", flush=True)
                if not spend_guard():
                    stopped_early = "spend cap exceeded during single mode"
                    break
                time.sleep(PAUSE_S)
            # (b) bundled mode
            if stopped_early is None:
                for bi, bundle in enumerate(bundles):
                    recs = [rec_base(it, "bundled") for it in bundle]
                    for pos, r_ in enumerate(recs):
                        r_["bundle_id"] = bi
                        r_["bundle_position"] = pos
                        r_["bundle_size"] = len(bundle)
                    try:
                        ps, answers, latency, cost, basis, itok, otok = ask_bundled(client, bundle)
                        for r_, p in zip(recs, ps):
                            r_.update(p=p, latency_s=round(latency, 3),
                                      raw_answers=answers,
                                      input_tokens=itok, output_tokens=otok)
                            r_["cost_usd"], r_["cost_basis"] = cost / len(bundle), basis
                        spend_total += cost
                    except Exception as exc:  # noqa: BLE001
                        for r_ in recs:
                            r_["error"] = f"{type(exc).__name__}: {exc}"
                        n_failed += len(recs)
                    for r_ in recs:
                        r_["spend_usd_running_total"] = round(spend_total, 6)
                        out.write(json.dumps(r_) + "\n")
                    out.flush()
                    got = [r_["p"] for r_ in recs]
                    print(f"[bundle {bi + 1}/{len(bundles)}] ps={got} spend=${spend_total:.4f}", flush=True)
                    if not spend_guard():
                        stopped_early = "spend cap exceeded during bundled mode"
                        break
                    time.sleep(PAUSE_S)
    finally:
        client.close()

    # ---- metrics ----
    rows = [json.loads(line) for line in open(raw_path)]
    single = {r["id"]: r["p"] for r in rows if r["mode"] == "single" and r.get("p") is not None}
    bundled_rows = [r for r in rows if r["mode"] == "bundled" and r.get("p") is not None]
    paired = [(r["id"], r["p"], single[r["id"]]) for r in bundled_rows if r["id"] in single]

    abs_drifts = [abs(pb - ps) for _, pb, ps in paired]
    signed = [(pb - ps) for _, pb, ps in paired]
    flips = sum(((pb >= 0.5) != (ps >= 0.5)) for _, pb, ps in paired)
    abs_drifts_sorted = sorted(abs_drifts)
    p90 = abs_drifts_sorted[int(0.9 * (len(abs_drifts_sorted) - 1))] if abs_drifts_sorted else None

    # position effect: anchors at pos 0 vs pos 4
    anchor_pos: dict[str, dict[int, float]] = {}
    for r in bundled_rows:
        if r["id"] in anchors:
            anchor_pos.setdefault(r["id"], {})[r["bundle_position"]] = r["p"]
    pos_pairs = [(v[0], v[4]) for v in anchor_pos.values() if 0 in v and 4 in v]
    pos_drifts = [abs(a - b) for a, b in pos_pairs]

    # drift by bundle position (all items)
    by_pos: dict[int, list[float]] = {}
    for r in bundled_rows:
        if r["id"] in single:
            by_pos.setdefault(r["bundle_position"], []).append(abs(r["p"] - single[r["id"]]))

    stats = {
        "date": DATE,
        "model": MODEL,
        "n_items": len(items),
        "n_anchors": len(anchors),
        "anchor_ids": anchors,
        "n_single_calls": sum(1 for r in rows if r["mode"] == "single"),
        "n_bundled_calls": len({(r["bundle_id"]) for r in bundled_rows}),
        "n_paired_measurements": len(paired),
        "n_failed": n_failed,
        "stopped_early": stopped_early,
        "spend_usd_total": round(spend_total, 6),
        "spend_cap_usd": SPEND_CAP_USD,
        "bundling_mechanism": (
            "one system_one call; state = numbered statement list string; "
            "one Noul per statement in the questions mapping, instructions "
            "pointing at that statement number"
        ),
        "mean_abs_drift": sum(abs_drifts) / len(abs_drifts) if abs_drifts else None,
        "p90_abs_drift": p90,
        "max_abs_drift": max(abs_drifts) if abs_drifts else None,
        "mean_signed_drift_bundled_minus_single": sum(signed) / len(signed) if signed else None,
        "flip_rate_at_0.5": flips / len(paired) if paired else None,
        "n_flips": flips,
        "anchor_first_vs_last_position": {
            "n_anchor_pairs": len(pos_pairs),
            "mean_abs_diff": sum(pos_drifts) / len(pos_drifts) if pos_drifts else None,
            "max_abs_diff": max(pos_drifts) if pos_drifts else None,
            "pairs": [{"id": a, "p_pos0": p0, "p_pos4": p4} for (a, (p0, p4)) in
                      zip([k for k in anchor_pos if 0 in anchor_pos[k] and 4 in anchor_pos[k]], pos_pairs)],
        },
        "mean_abs_drift_by_position": {
            str(pos): sum(v) / len(v) for pos, v in sorted(by_pos.items())
        },
        "per_item": [
            {"id": i, "p_single": ps, "p_bundled": pb, "abs_drift": abs(pb - ps),
             "signed_drift": pb - ps, "flipped": (pb >= 0.5) != (ps >= 0.5)}
            for i, pb, ps in sorted(paired)
        ],
    }
    with open(f"results/joint-{DATE}-stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    print(json.dumps({k: v for k, v in stats.items() if k != "per_item"}, indent=2))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("--probe", "--run"):
        raise SystemExit("usage: python jev_eval_joint.py --probe | --run")
    raise SystemExit(probe() if sys.argv[1] == "--probe" else run())
