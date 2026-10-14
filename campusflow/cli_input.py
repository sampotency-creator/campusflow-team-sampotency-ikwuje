
"""Small, testable input helpers for the CampusFlow CLI.

Every prompt takes an injectable input_fn / print_fn so tests can feed
scripted input instead of using the keyboard.
"""


def ask_choice(
    prompt,
    valid,
    input_fn=input,
    print_fn=print,
    strip=True,
    hint=None,
):
    """Re-prompt until the input is exactly one of the valid values.

    With strip=False, even a stray space (' A') is rejected.
    """

    valid = set(valid)
    hint = hint or ", ".join(sorted(valid))

    while True:
        raw = input_fn(prompt)
        value = raw.strip() if strip else raw

        if value in valid:
            return value

        print_fn(f"Invalid input. Please enter exactly: {hint}.")


def confirm(prompt, input_fn=input, print_fn=print):
    """Ask a y/n question. Return True for y, False for n."""

    while True:
        answer = input_fn(f"{prompt} (y/n): ").strip().lower()

        if answer in ("y", "n"):
            return answer == "y"

        print_fn("Invalid input. Please enter y or n.")