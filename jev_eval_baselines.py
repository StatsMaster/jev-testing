"""Phase 5 -- baselines and cost: cheap alternatives on the same 200 items.

Three baselines, evaluated on the Phase 1 calibration dataset:
1. Constants (exact, no API calls): always-0.5, base-rate, majority-class.
2. Constrained LLM: one OpenRouter chat-completions call per item, prompted
   to output ONLY a number in [0,1]. Robust regex parse; unparseable outputs
   are recorded as failures and never imputed.
3. Exact symbolic baseline for the 50 arithmetic items: an English
   word-number parser with exact rational arithmetic; p in {0.0, 1.0}.

Usage:
    python jev_eval_baselines.py <dataset.json> <jev_raw.jsonl> <out_prefix> [--max-items N]

Writes:
    <out_prefix>-raw.jsonl     per-call records for the LLM baseline
    <out_prefix>-stats.json    all baseline metrics + comparison table
    (results/phase5-summary.md is written separately after the run)

Auth: surrogated custom.openrouter credential via dynamic_credentials
(never persisted, never printed). Only openrouter.ai is contacted.

Politeness: 1.5 s pause between LLM calls; two retries with 5 s / 15 s
backoff, then the item is recorded as failed and we move on. $2 circuit
breaker on total LLM spend.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
import sys
import time
import urllib.request
from fractions import Fraction

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request  # noqa: E402

import jev_eval_common  # noqa: E402
from jev_eval_calibration import reliability  # noqa: E402

CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
ALLOWED_HOSTS = ["openrouter.ai"]

# Verified 2026-09-30 via unauthenticated GET /api/v1/models
# (pricing.prompt / pricing.completion, USD per token).
# Model selection note: several cheap models were probed on 2-4 items with the
# exact task prompt before the run. meta-llama/llama-3.1-8b-instruct,
# qwen/qwen3-30b-a3b-instruct-2507, amazon/nova-micro-v1 and
# cohere/command-r7b-12-2024 collapsed to constant "0"/"0.0" (or gave
# anti-correlated answers); openai/gpt-oss-120b and deepseek/deepseek-v4.1-flash
# returned empty strings (reasoning budget consumed, nothing parseable).
# mistral-nemo was the only cheap model producing varied, directionally
# sensible outputs, so it is the fairest "just prompt an LLM" representative.
LLM_MODEL = "mistralai/mistral-nemo"
LLM_INPUT_USD_PER_MTOKEN = 0.019
LLM_OUTPUT_USD_PER_MTOKEN = 0.030
PRICE_CAP_USD_PER_MTOKEN = 0.10  # task constraint on the input price
LLM_MAX_TOKENS = 64  # headroom against truncation; typical output is 1-4 tokens

PAUSE_S = 1.5  # politeness pause between LLM calls
RETRY_SLEEPS = (5.0, 15.0)  # backoff before retry 1 and retry 2, then give up
SPEND_CAP_USD = 2.00  # circuit breaker: stop all calls if exceeded
TIMEOUT_S = 60.0

PROMPT = (
    "Decide whether the following statement is TRUE or FALSE.\n"
    "Reply with ONLY a single decimal number between 0 and 1: your probability "
    "that the statement is TRUE.\n"
    "Output the number and nothing else -- no words, no explanation, "
    "no punctuation around it.\n\n"
    "Statement: {text}"
)

FLOAT_RE = re.compile(r"(?:\d+(?:\.\d+)?|\.\d+)")


def parse_prob(text: str) -> float | None:
    """First float in [0,1] found in the output, else None (never imputed)."""
    for m in FLOAT_RE.finditer(text):
        try:
            v = float(m.group(0))
        except ValueError:
            continue
        if 0.0 <= v <= 1.0:
            return v
    return None


def ask_llm(text: str) -> tuple:
    """One constrained-LLM call with up to two retries.

    Returns (p, raw_text, latency_s, in_tokens, out_tokens, cost_usd,
    cost_basis). p is None when the output could not be parsed as a
    probability in [0,1]. Raises the last exception if all attempts fail.
    """
    body = json.dumps(
        {
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": PROMPT.format(text=text)}],
            "temperature": 0,
            "max_tokens": LLM_MAX_TOKENS,
        }
    ).encode()
    last_exc: Exception | None = None
    for sleep_s in (0.0, *RETRY_SLEEPS):
        if sleep_s:
            time.sleep(sleep_s)
        req = urllib.request.Request(CHAT_URL, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Title", "jev-testing-phase5")
        add_surrogate_to_request(req, "custom.openrouter", allowed_hosts=ALLOWED_HOSTS)
        try:
            t0 = time.monotonic()
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                payload = json.loads(resp.read().decode())
            latency = time.monotonic() - t0
        except Exception as exc:  # noqa: BLE001 - retried, then raised
            last_exc = exc
            continue
        try:
            content = payload["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            last_exc = exc
            continue
        usage = payload.get("usage") or {}
        in_tok = int(usage.get("prompt_tokens") or 0)
        out_tok = int(usage.get("completion_tokens") or 0)
        if isinstance(usage.get("cost"), (int, float)):
            cost, basis = float(usage["cost"]), "reported"
        elif in_tok or out_tok:
            cost = (
                in_tok * LLM_INPUT_USD_PER_MTOKEN + out_tok * LLM_OUTPUT_USD_PER_MTOKEN
            ) / 1e6
            basis = "estimated_from_tokens"
        else:
            cost, basis = 0.0, "missing"
        return parse_prob(content), content, latency, in_tok, out_tok, cost, basis
    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# Exact symbolic baseline: English word-number arithmetic (no API calls).
# ---------------------------------------------------------------------------

_SMALL = {
    w: i
    for i, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve "
        "thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
    )
}
_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def words_to_int(words: list[str]) -> int:
    total, current = 0, 0
    for w in words:
        if w in _SMALL:
            current += _SMALL[w]
        elif w in _TENS:
            current += _TENS[w]
        elif w == "hundred":
            current *= 100
        elif w == "thousand":
            total += current * 1000
            current = 0
        else:
            raise ValueError(f"unknown number word: {w!r}")
    return total + current


def parse_expr(s: str):
    toks = s.split()
    if toks[-1] == "factorial":
        return math.factorial(words_to_int(toks[:-1]))
    if toks[-1] == "squared":
        n = words_to_int(toks[:-1])
        return n * n
    if toks[-1] == "cubed":
        n = words_to_int(toks[:-1])
        return n**3
    if " to the power of " in s:
        a, b = s.split(" to the power of ", 1)
        return words_to_int(a.split()) ** words_to_int(b.split())
    for op in (" divided by ", " plus ", " minus ", " times "):
        if op in s:
            a, b = s.split(op, 1)
            x, y = words_to_int(a.split()), words_to_int(b.split())
            if op == " divided by ":
                return Fraction(x, y)
            if op == " plus ":
                return x + y
            if op == " minus ":
                return x - y
            return x * y
    return words_to_int(toks)


def symbolic_probability(statement: str) -> float:
    """1.0 if the arithmetic statement is exactly true, else 0.0."""
    s = statement.strip().lower().replace("-", " ").rstrip(".")
    if " equals " in s:
        left, right = s.split(" equals ", 1)
        computed, stated = parse_expr(left), words_to_int(right.split())
    elif " is " in s:
        left, right = s.split(" is ", 1)
        stated, computed = words_to_int(left.split()), parse_expr(right)
    else:
        raise ValueError(f"no comparator in {statement!r}")
    return 1.0 if computed == stated else 0.0


def main() -> int:
    args = sys.argv[1:]
    max_items = None
    if "--max-items" in args:
        i = args.index("--max-items")
        max_items = int(args[i + 1])
        del args[i : i + 2]
    dataset_path, jev_raw_path, out_prefix = args

    jev_eval_common._scrub_no_proxy()  # noqa: SLF001 - same egress fix as phases 1-2
    assert LLM_INPUT_USD_PER_MTOKEN <= PRICE_CAP_USD_PER_MTOKEN, "price cap violated"

    items = json.load(open(dataset_path))
    labels = [it["true_label"] for it in items]
    n = len(items)
    base_rate = sum(labels) / n
    majority = 1 if base_rate >= 0.5 else 0

    # --- baseline 1: constants (exact, no API calls) ---
    constants: dict[str, dict] = {}
    for name, p in [
        ("always_0.5", 0.5),
        ("base_rate", base_rate),
        ("majority_class", float(majority)),
    ]:
        rows = [{"p": p, "true_label": y} for y in labels]
        brier, ece, _ = reliability(rows)
        acc = sum((p >= 0.5) == bool(y) for y in labels) / n
        constants[name] = {
            "p": p,
            "n": n,
            "brier": brier,
            "ece_10bin": ece,
            "accuracy_at_0.5": acc,
            "mean_latency_s": 0.0,
            "cost_per_1k_decisions_usd": 0.0,
        }

    # --- baseline 3: exact symbolic arithmetic (no API calls) ---
    arith = [it for it in items if it["domain"] == "arithmetic"]
    sym_rows, sym_failed = [], []
    for it in arith:
        try:
            sym_rows.append(
                {
                    "id": it["id"],
                    "p": symbolic_probability(it["text"]),
                    "true_label": it["true_label"],
                }
            )
        except Exception as exc:  # noqa: BLE001 - recorded, never imputed
            sym_failed.append({"id": it["id"], "error": str(exc)})
    sym_brier, _, _ = reliability(sym_rows) if sym_rows else (float("nan"), 0.0, [])
    symbolic = {
        "n_arithmetic": len(arith),
        "n_parsed": len(sym_rows),
        "n_failed_parse": len(sym_failed),
        "failed": sym_failed,
        "brier_on_arithmetic_subset": sym_brier,
        "note": "exact rational arithmetic on parsed English word-numbers; "
        "p in {0.0, 1.0}; failures would be excluded, not imputed",
    }

    # --- Jev reference numbers, recomputed from its raw records ---
    jev_rows = [json.loads(line) for line in open(jev_raw_path)]
    jev_ok = [r for r in jev_rows if r.get("p") is not None]
    jev_brier, jev_ece, _ = reliability(jev_ok)
    jev_arith = [r for r in jev_ok if r["domain"] == "arithmetic"]
    jev_arith_brier, _, _ = reliability(jev_arith)
    symbolic["jev_brier_on_arithmetic_subset"] = jev_arith_brier
    symbolic["jev_n_arithmetic"] = len(jev_arith)
    jev_lat = [r["latency_s"] for r in jev_ok if r.get("latency_s") is not None]
    jev_spend = sum(r.get("cost_usd", 0.0) or 0.0 for r in jev_ok)
    jev = {
        "model": "jev-latest",
        "n": len(jev_ok),
        "brier": jev_brier,
        "ece_10bin": jev_ece,
        "accuracy_at_0.5": sum((r["p"] >= 0.5) == bool(r["true_label"]) for r in jev_ok)
        / len(jev_ok),
        "mean_latency_s": sum(jev_lat) / len(jev_lat),
        "spend_usd_total": round(jev_spend, 6),
        "cost_per_1k_decisions_usd": jev_spend / len(jev_ok) * 1000,
    }

    # --- baseline 2: constrained LLM, one call per item ---
    run_items = items[:max_items] if max_items else items
    raw_path = f"{out_prefix}-raw.jsonl"
    spend_total, n_failed, n_unparseable = 0.0, 0, 0
    stopped_early = None
    with open(raw_path, "w") as out:
        for i, it in enumerate(run_items):
            rec = {
                "id": it["id"],
                "text": it["text"],
                "true_label": it["true_label"],
                "domain": it["domain"],
                "difficulty": it["difficulty"],
                "model": LLM_MODEL,
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                "p": None,
                "raw_text": None,
                "latency_s": None,
                "input_tokens": None,
                "output_tokens": None,
                "cost_usd": None,
                "cost_basis": None,
                "error": None,
            }
            try:
                p, raw_text, lat, itok, otok, cost, basis = ask_llm(it["text"])
                rec.update(
                    p=p,
                    raw_text=raw_text,
                    latency_s=round(lat, 3),
                    input_tokens=itok,
                    output_tokens=otok,
                    cost_usd=cost,
                    cost_basis=basis,
                )
                if p is None:
                    n_unparseable += 1
                spend_total += cost
            except Exception as exc:  # noqa: BLE001 - recorded, move on
                rec["error"] = f"{type(exc).__name__}: {exc}"
                n_failed += 1
            rec["spend_usd_running_total"] = round(spend_total, 6)
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(
                f"[{i + 1}/{len(run_items)}] {it['id']} p={rec['p']} "
                f"raw={rec['raw_text']!r} spend=${spend_total:.5f} err={rec['error']}",
                flush=True,
            )
            if spend_total > SPEND_CAP_USD:
                stopped_early = (
                    f"spend cap ${SPEND_CAP_USD:.2f} exceeded after item {i + 1}; "
                    "stopping all further calls"
                )
                print("[spend] " + stopped_early, flush=True)
                break
            if i < len(run_items) - 1:
                time.sleep(PAUSE_S)

    rows = [json.loads(line) for line in open(raw_path)]
    llm_ok = [r for r in rows if r.get("p") is not None]
    llm_brier, llm_ece, llm_table = reliability(llm_ok)
    llm_lat = [r["latency_s"] for r in llm_ok if r.get("latency_s") is not None]
    llm = {
        "model": LLM_MODEL,
        "price_note": (
            f"verified 2026-09-30 via GET /api/v1/models: "
            f"${LLM_INPUT_USD_PER_MTOKEN}/M input, ${LLM_OUTPUT_USD_PER_MTOKEN}/M output"
        ),
        "prompt": PROMPT,
        "n_items": len(rows),
        "n_success": len(llm_ok),
        "n_failed": n_failed,
        "n_unparseable": n_unparseable,
        "stopped_early": stopped_early,
        "brier": llm_brier,
        "ece_10bin": llm_ece,
        "reliability_table": llm_table,
        "accuracy_at_0.5": (
            sum((r["p"] >= 0.5) == bool(r["true_label"]) for r in llm_ok) / len(llm_ok)
            if llm_ok
            else None
        ),
        "mean_latency_s": sum(llm_lat) / len(llm_lat) if llm_lat else None,
        "spend_usd_total": round(spend_total, 6),
        "spend_cap_usd": SPEND_CAP_USD,
        "cost_per_1k_decisions_usd": (
            spend_total / len(llm_ok) * 1000 if llm_ok else None
        ),
        "parse_note": "first float in [0,1] via regex; unparseable outputs are "
        "failures, never imputed",
    }

    comparison_table = [
        {
            "baseline": "jev (Noul)",
            "brier": jev["brier"],
            "ece_10bin": jev["ece_10bin"],
            "accuracy_at_0.5": jev["accuracy_at_0.5"],
            "mean_latency_s": jev["mean_latency_s"],
            "cost_per_1k_decisions_usd": jev["cost_per_1k_decisions_usd"],
        },
        {
            "baseline": f"constrained LLM ({LLM_MODEL})",
            "brier": llm["brier"],
            "ece_10bin": llm["ece_10bin"],
            "accuracy_at_0.5": llm["accuracy_at_0.5"],
            "mean_latency_s": llm["mean_latency_s"],
            "cost_per_1k_decisions_usd": llm["cost_per_1k_decisions_usd"],
        },
    ]
    for name in ("always_0.5", "base_rate", "majority_class"):
        c = constants[name]
        comparison_table.append(
            {
                "baseline": f"constant {name} (p={c['p']})",
                "brier": c["brier"],
                "ece_10bin": c["ece_10bin"],
                "accuracy_at_0.5": c["accuracy_at_0.5"],
                "mean_latency_s": c["mean_latency_s"],
                "cost_per_1k_decisions_usd": c["cost_per_1k_decisions_usd"],
            }
        )

    stats = {
        "date": "2026-09-30",
        "n_items": n,
        "label_balance": {"n_true": sum(labels), "n_false": n - sum(labels)},
        "jev": jev,
        "constrained_llm": llm,
        "constants": constants,
        "symbolic_arithmetic": symbolic,
        "comparison_table": comparison_table,
    }
    with open(f"{out_prefix}-stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    print(
        json.dumps(
            {k: v for k, v in stats.items() if k != "constrained_llm"}, indent=2
        )
    )
    print("[llm]", json.dumps({k: v for k, v in llm.items() if k != "reliability_table"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
