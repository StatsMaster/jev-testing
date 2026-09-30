"""Step 2 of the Real Python Jev tutorial: replace the Y/N check with a Noul.

Asks Jev a yes-or-no question about the visitor's free-text reply and gets
back a float between 0 (clear no) and 1 (clear yes).

Needs OPENROUTER_API_KEY in the environment (an OpenRouter key with a few
dollars of credit).
"""

import os

from typesafe_sdk import Noul, TypeSafeClient

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


def ask(question: str) -> bool:
    while True:
        state = input(f"{question} ")
        r = client.system_one(
            state=state,
            questions={
                "lost_something": Noul(
                    instructions=(
                        "Decide whether the visitor's reply is an affirmative "
                        "answer (yes-like) or a negative answer (no-like)."
                    )
                ),
            },
        )
        score = r.answers["lost_something"].noul
        print(f"[debug] noul score: {score:.2f}")
        if score > 0.8:
            return True
        if score < 0.2:
            return False
        print("Sorry, I didn't catch that. Could you say it differently?")


def main() -> None:
    lost = ask("Did you lose something?")
    if lost:
        print("Please head to the lost and found counter.")
    else:
        print("Enjoy your trip!")


if __name__ == "__main__":
    main()
