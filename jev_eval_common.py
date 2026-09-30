"""Shared helpers for the independent Jev evaluation (calibration + stability).

Auth: on the Hatch VM, uses the stored ``custom.openrouter`` credential via the
skill's surrogate exchange (never persisted, never printed). Anywhere else,
falls back to the ``OPENROUTER_API_KEY`` environment variable.

Endpoint notes (verified 2026-09-30):
- base_url="https://openrouter.ai/api"; the SDK appends /v1/systemone itself.
- /systemone requires model="jev-latest".
- Noul answers expose the yes-like probability as ``.noul``.
- Scrub bracketed IPv6 literals out of NO_PROXY: the SDK's vendored httpx
  cannot parse them as proxy-bypass patterns.
"""

from __future__ import annotations

import os
import sys
import time
import json

BASE_URL = "https://openrouter.ai/api"  # SDK appends /v1/systemone itself
ALLOWED_HOSTS = ["openrouter.ai"]
MODEL = "jev-latest"  # TypeSafe-side model name; the systemone endpoint maps it
TIMEOUT = 180.0  # egress from this machine is slow; SDK default is 10s
PAUSE_S = 1.5  # politeness pause between API calls
RETRY_SLEEPS = (5.0, 15.0)  # backoff before retry 1 and retry 2, then give up

NOUL_INSTRUCTIONS = (
    "Decide whether the following statement is TRUE (yes-like) or FALSE "
    "(no-like). Give a high probability when the statement is true and a "
    "low probability when the statement is false."
)

SPEND_CAP_USD = 2.00  # circuit breaker: stop all calls if exceeded


class SpendCapExceeded(Exception):
    """Raised when the accumulated reported spend passes SPEND_CAP_USD."""


_DEBUG_DUMP_KEYS = True  # one-time print of response shape on first success


def _scrub_no_proxy() -> None:
    import os

    for var in ("no_proxy", "NO_PROXY"):
        raw = os.environ.get(var)
        if not raw:
            continue
        kept = [p for p in raw.split(",") if ":" not in p and "[" not in p]
        os.environ[var] = ",".join(kept)


def get_api_key() -> str:
    """Surrogate credential on the Hatch VM, else OPENROUTER_API_KEY."""
    try:
        sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
        from dynamic_credentials import (  # noqa: E402
            dynamic_credential_entry,
            ensure_allowed_url,
        )

        ensure_allowed_url(BASE_URL, ALLOWED_HOSTS)
        entry = dynamic_credential_entry("custom.openrouter")
        return str(entry["surrogate"]).strip()
    except Exception:
        key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise SystemExit(
                "No credential: run on the Hatch VM with the openrouter skill, "
                "or set OPENROUTER_API_KEY."
            )
        return key


def make_client():
    from typesafe_sdk import TypeSafeClient

    _scrub_no_proxy()
    return TypeSafeClient(api_key=get_api_key(), base_url=BASE_URL)


def extract_noul(answers: dict, key: str = "q") -> float:
    """Pull the yes-like probability out of a system_one answers mapping."""
    ans = answers[key]
    if isinstance(ans, dict):
        for field in ("noul", "probability", "score", "value"):
            if isinstance(ans.get(field), (int, float)):
                return float(ans[field])
        raise KeyError(f"no probability field in {ans!r}")
    for field in ("noul", "probability", "score", "value"):
        v = getattr(ans, field, None)
        if isinstance(v, (int, float)):
            return float(v)
    raise KeyError(f"no probability field in {ans!r}")


JEV_INPUT_USD_PER_MTOKEN = 0.042  # input pricing; output is free
# (public Jev pricing used only to *estimate* spend when the response carries
# no cost field; never presented as a finding about the model itself)


def extract_cost(dump: dict) -> tuple[float, str]:
    """Estimate the per-request cost (USD) from a response dump.

    Returns (cost_usd, basis) where basis is "reported" if usage.cost was
    present, "estimated_from_tokens" if derived from input_tokens at the
    public input price (output is free), or "missing" if neither exists.
    """
    usage = dump.get("usage")
    if isinstance(usage, dict):
        if isinstance(usage.get("cost"), (int, float)):
            return float(usage["cost"]), "reported"
        if isinstance(usage.get("input_tokens"), (int, float)):
            return (
                float(usage["input_tokens"]) * JEV_INPUT_USD_PER_MTOKEN / 1e6,
                "estimated_from_tokens",
            )
    if isinstance(dump.get("cost"), (int, float)):
        return float(dump["cost"]), "reported"
    return 0.0, "missing"


def ask_noul(client, state: str, key: str = "q") -> tuple[float, dict, float, float, str]:
    """One Noul call with up to two retries.

    Returns (p, raw_answers, latency_s, cost_usd, cost_basis).

    Raises the last exception if all attempts fail; the caller records the
    item as failed and moves on.
    """
    from typesafe_sdk import Noul

    global _DEBUG_DUMP_KEYS
    last_exc: Exception | None = None
    for attempt, sleep_s in enumerate([0.0, *RETRY_SLEEPS]):
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
            if _DEBUG_DUMP_KEYS:
                _DEBUG_DUMP_KEYS = False
                print("[debug] response top-level keys:", sorted(dump.keys()), flush=True)
                print("[debug] usage field:", json.dumps(dump.get("usage"), default=str)[:300], flush=True)
            answers = dump.get("answers", {})
            cost, basis = extract_cost(dump)
            return extract_noul(answers, key), answers, latency, cost, basis
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed silently
            last_exc = exc
    assert last_exc is not None
    raise last_exc
