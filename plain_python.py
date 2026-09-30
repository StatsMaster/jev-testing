"""Step 1 of the Real Python Jev tutorial: no AI at all.

A train-station script that only accepts an uppercase Y or N when asking
a visitor if they lost something.
"""


def ask(question: str) -> bool:
    while True:
        answer = input(f"{question} (Y/N) ")
        if answer == "Y":
            return True
        if answer == "N":
            return False
        print("Please answer with an uppercase Y or N.")


def main() -> None:
    lost = ask("Did you lose something?")
    if lost:
        print("Please head to the lost and found counter.")
    else:
        print("Enjoy your trip!")


if __name__ == "__main__":
    main()
