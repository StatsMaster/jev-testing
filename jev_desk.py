"""Step 3 of the Real Python Jev tutorial: three questions, one request.

A Choice (which desk), a Score (how urgent), and a Noul (needs assistance)
answered together about a single visitor request.

Needs OPENROUTER_API_KEY in the environment (an OpenRouter key with a few
dollars of credit).
"""

import os
from pprint import pprint

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

try:
    api_key = os.environ["OPENROUTER_API_KEY"]
except KeyError:
    raise SystemExit("Set OPENROUTER_API_KEY first (see README).")

client = TypeSafeClient(
    api_key=api_key,
    # NOTE: this SDK version appends /v1/systemone itself, so the base URL
    # must NOT include /v1 (the tutorial's /api/v1 value 404s).
    base_url="https://openrouter.ai/api",
    model="jev-latest",
    timeout=180.0,
)

QUESTIONS = {
    "desk": Choice(
        # NOTE: this SDK version requires instructions on Choice/Score too.
        instructions="Decide which service desk should handle the visitor's request.",
        criteria={
            "lost_and_found": "The visitor lost an item or is asking about lost property.",
            "tickets": "The visitor asks about tickets, platforms, or departures.",
            "general_info": "Anything else, including restrooms or directions.",
        },
    ),
    "urgency": Score(
        instructions="Rate how urgently the visitor needs help.",
        criteria=[
            "No rush at all; whenever is fine.",
            "Should be helped within the hour.",
            "Should be helped within the next few minutes.",
            "Needs help right now.",
        ],
    ),
    "needs_assistance": Noul(
        instructions=(
            "Decide whether the visitor needs staff assistance. Examples of "
            "needing assistance: asking for help carrying luggage, reporting a "
            "medical issue, or being unable to find their way. Examples of not "
            "needing assistance: greeting the desk or asking for the time."
        )
    ),
}


def main() -> None:
    visitor_words = input("How can I help you? ")
    state = {"visitor_words": visitor_words}
    r = client.system_one(state=state, questions=QUESTIONS)
    pprint(r.model_dump()["answers"])


if __name__ == "__main__":
    main()
