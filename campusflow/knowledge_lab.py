
"""Engineering Knowledge Lab: a 10-question quiz with mentor-readable records.

This module never imports the ticket store, so running the lab cannot
modify ticket records.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from campusflow.cli_input import ask_choice

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SESSION_DIR = PROJECT_ROOT / "lab_sessions"

VALID_CHOICES = ("A", "B", "C", "D")
VALID_PARTICIPANTS = ("A", "B")
MIN_EXPLANATIONS = 3

# Explanation FORMAT rules. These check shape only; content is never graded.
MAX_SENTENCES = 2
MIN_WORDS = 5
MAX_WORDS = 60

EXPLANATION_GUIDE = (
    f"For at least {MIN_EXPLANATIONS} answers you must explain WHY you chose it, "
    f"in one or two sentences ({MIN_WORDS}-{MAX_WORDS} words).\n"
    "Explanations are not auto-graded; a mentor reads them."
)


def _q(qid, topic, prompt, options, correct, rationale):
    return {
        "id": qid,
        "topic": topic,
        "prompt": prompt,
        "options": dict(zip(VALID_CHOICES, options)),
        "correct": correct,
        "rationale": rationale,
    }


QUESTIONS = [
    _q("Q1", "Status and history",
       "A manager asks 'is T004 resolved right now?' and 'who reopened it last week?'. "
       "Why keep BOTH a status field and an event log?",
       ["JSON requires every value to be stored twice.",
        "History is always faster to read than status.",
        "Status answers 'now' quickly; history is the audit trail of how it got there.",
        "Status can be rebuilt, so the history is optional."],
       "C",
       "Current status gives fast reads. The event log explains who did what and when. "
       "Each answers a question the other cannot answer cheaply."),
    _q("Q2", "Failed actions",
       "assign_ticket fails because the staff name is blank. What should happen to the event history?",
       ["Nothing is appended: history records only what actually happened.",
        "Append an ASSIGN_FAILED event so nothing is lost.",
        "Append a normal assignment event, then delete it later.",
        "Append the event only if the actor is an admin."],
       "A",
       "An event says 'this change happened'. If nothing changed, a recorded event would be a false statement "
       "and would make replay and audits unreliable."),
    _q("Q3", "Atomic events",
       "The workflow prepares the event BEFORE changing the ticket and appends it AFTER. What does this prevent?",
       ["Slow saves.",
        "Two users editing at once.",
        "Duplicate tickets.",
        "A failure while building the event leaving a changed ticket with no matching event."],
       "D",
       "If event creation raises, the ticket has not been touched yet, so state and history cannot drift apart."),
    _q("Q4", "Duplicate detection",
       "' Wi-Fi   Down ' exists unresolved in Network. A user enters 'wi-fi down' in Network. "
       "Which comparison is best?",
       ["Compare the raw strings.",
        "Trim, case-fold and collapse whitespace, then compare within the same category.",
        "Delete every space and punctuation mark, ignoring category.",
        "Compare only the first word."],
       "B",
       "Normalizing whitespace and case catches harmless typing differences. Over-aggressive rules or ignoring "
       "category create false matches."),
    _q("Q5", "Warn vs block",
       "A new ticket matches an unresolved ticket. What should the CLI do?",
       ["Warn, show the match and ask for confirmation.",
        "Block it permanently.",
        "Silently allow it.",
        "Delete the older ticket."],
       "A",
       "The system cannot be sure it is the same fault; the reporter may have new information. "
       "Warn and let a human decide. Blocking suits only exact repeats from the same reporter."),
    _q("Q6", "Queue design",
       "Why are the open-work queue and the SLA-attention queue separate?",
       ["They are the same list sorted by name.",
        "The SLA queue includes resolved tickets.",
        "The work queue answers 'what do I do next?' (priority); the SLA queue answers 'what is about to breach?' (deadline).",
        "The SLA queue is only for critical tickets."],
       "C",
       "Different questions need different filters and sort orders. Priority and deadline risk are not the same thing."),
    _q("Q7", "Deterministic sorting",
       "Two tickets share the same due time and priority, and a queue test sometimes fails because the order changes. Best fix?",
       ["Run the test several times.",
        "Add a final deterministic tie-break such as the numeric ticket ID.",
        "Sort randomly.",
        "Delete the assertion."],
       "B",
       "Every sort key needs a last tie-break so output is repeatable. Use the numeric ID, "
       "because the string 'T10' sorts before 'T2'."),
    _q("Q8", "Testable time",
       "Why pass 'now' into SLA functions instead of calling datetime.now() inside them?",
       ["datetime.now() is slow.",
        "Python requires it.",
        "It hides time zones.",
        "Tests can fix the clock and get repeatable overdue results."],
       "D",
       "Hidden clocks make tests flaky. An injected 'now' makes behaviour a pure function of its inputs."),
    _q("Q9", "Testing pure functions",
       "Why must a pure function like score_answers have tests?",
       ["Pure functions cannot contain bugs.",
        "The score is what mentors trust; a wrong key or off-by-one would go unnoticed.",
        "Tests make code run faster.",
        "Only to satisfy a coverage number."],
       "B",
       "Pure functions are the easiest code to test and the costliest to get silently wrong, "
       "because everything downstream trusts their output."),
    _q("Q10", "Quiz integrity",
       "A student could pass multiple choice by elimination without understanding. Which design mitigates this?",
       ["Add a fifth option.",
        "Add a countdown timer.",
        "Require short written explanations that a mentor reads instead of auto-grading.",
        "Show the answer key first."],
       "C",
       "Explanations expose reasoning that a letter cannot. Free text is not auto-graded because a human must judge understanding."),
]


# --------------------------------------------------
# PURE LOGIC
# --------------------------------------------------

def is_valid_choice(value):
    """Exact A/B/C/D only: 'a', ' A', '' and 'AB' are all rejected."""

    return isinstance(value, str) and value in VALID_CHOICES


def score_answers(answers, questions=QUESTIONS):
    """Return the number of correct answers. Missing/invalid answers score 0."""

    return sum(
        1 for q in questions
        if is_valid_choice(answers.get(q["id"])) and answers[q["id"]] == q["correct"]
    )


def topics_to_revise(answers, questions=QUESTIONS):
    """Topics of wrong or unanswered questions, de-duplicated, in order."""

    topics = []

    for q in questions:
        if answers.get(q["id"]) != q["correct"] and q["topic"] not in topics:
            topics.append(q["topic"])

    return topics


def split_sentences(text):
    """Split on . ! ? followed by whitespace, so '3.12' is not split."""

    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def normalize_explanation(text):
    """Trim and collapse all internal whitespace, including newlines."""

    return " ".join(text.split())


def validate_explanation(text):
    """Check the FORMAT of an explanation. Return (ok, message).

    Rules: not blank, MIN_WORDS to MAX_WORDS words, at most MAX_SENTENCES
    sentences. Whether the reasoning is correct is deliberately NOT checked.
    """

    if not isinstance(text, str) or not text.strip():
        return False, "The explanation cannot be blank."

    words = [w for w in text.split() if any(c.isalnum() for c in w)]
    sentences = split_sentences(text)

    if len(words) < MIN_WORDS:
        return False, (
            f"Too short ({len(words)} word(s)). "
            f"Use at least {MIN_WORDS} words."
        )

    if len(sentences) > MAX_SENTENCES:
        return False, (
            f"Too long ({len(sentences)} sentences). "
            "Use one or two sentences."
        )

    if len(words) > MAX_WORDS:
        return False, (
            f"Too long ({len(words)} words). "
            f"Keep it to {MAX_WORDS} words or fewer."
        )

    return True, ""


def build_session_record(participant, answers, explanations, questions=QUESTIONS, now=None):
    """Build the JSON-serialisable record a mentor inspects."""

    if participant not in VALID_PARTICIPANTS:
        raise ValueError("Participant must be exactly 'A' or 'B'.")

    valid_ids = {q["id"] for q in questions}
    clean = {}

    for qid, text in explanations.items():
        if qid not in valid_ids:
            raise ValueError(f"Explanation for unknown question: {qid}")
        ok, problem = validate_explanation(text)
        if not ok:
            raise ValueError(f"Explanation for {qid}: {problem}")
        clean[qid] = normalize_explanation(text)

    if len(clean) < MIN_EXPLANATIONS:
        raise ValueError(f"At least {MIN_EXPLANATIONS} explanations are required.")

    now = now or datetime.now(timezone.utc)

    return {
        "participant": participant,
        "timestamp_utc": now.astimezone(timezone.utc).isoformat(),
        "choices": dict(answers),
        "score": score_answers(answers, questions),
        "max_score": len(questions),
        "topics_to_revise": topics_to_revise(answers, questions),
        "explanations": clean,
    }


def save_session(record, directory=DEFAULT_SESSION_DIR):
    """Write the record as JSON and return the file path."""

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    stamp = datetime.fromisoformat(record["timestamp_utc"]).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"lab_{record['participant']}_{stamp}.json"

    with path.open("w", encoding="utf-8") as file:
        json.dump(record, file, indent=4)
        file.write("\n")

    return path


def load_session(path):
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


# --------------------------------------------------
# INTERACTIVE PART
# --------------------------------------------------

def _ask_explanation(input_fn, print_fn, allow_skip=False):
    """Prompt until the explanation passes the format check.

    With allow_skip=True, pressing Enter on an empty line returns None.
    """

    if allow_skip:
        prompt = "Explain your answer in 1-2 sentences (Enter to skip): "
    else:
        prompt = "Explain your answer in 1-2 sentences: "

    while True:
        raw = input_fn(prompt)

        if allow_skip and not raw.strip():
            return None

        ok, problem = validate_explanation(raw)

        if ok:
            return normalize_explanation(raw)

        print_fn(problem)
        print_fn(
            f"Tip: write {MIN_WORDS}-{MAX_WORDS} words in one or two "
            "sentences saying why you chose that answer."
        )


def show_results(record, questions, print_fn=print):
    print_fn("\n========== LAB RESULTS ==========")
    print_fn(f"Participant: {record['participant']}")
    print_fn(f"Score: {record['score']}/{record['max_score']}")

    revise = record["topics_to_revise"]
    print_fn("Topics to revise: " + (", ".join(revise) if revise else "none"))

    for number, q in enumerate(questions, start=1):
        given = record["choices"][q["id"]]
        verdict = "correct" if given == q["correct"] else f"wrong (correct: {q['correct']})"

        print_fn(f"\n{number}. [{q['topic']}] You chose {given} - {verdict}")
        print_fn(f"   Why: {q['rationale']}")

        if q["id"] in record["explanations"]:
            print_fn(f"   Your explanation: {record['explanations'][q['id']]}")

    print_fn("=================================")


def run_lab(input_fn=input, print_fn=print, directory=DEFAULT_SESSION_DIR,
            questions=QUESTIONS, now=None):
    """Run the interactive lab, save the session and return the record."""

    print_fn("\n========== ENGINEERING KNOWLEDGE LAB ==========")
    print_fn(EXPLANATION_GUIDE)

    participant = ask_choice(
        "Participant - enter A or B: ", VALID_PARTICIPANTS,
        input_fn, print_fn, strip=False,
    )

    answers, explanations = {}, {}

    for number, q in enumerate(questions, start=1):
        print_fn(f"\nQuestion {number}/{len(questions)} [{q['topic']}]")
        print_fn(q["prompt"])

        for letter in VALID_CHOICES:
            print_fn(f"  {letter}) {q['options'][letter]}")

        answers[q["id"]] = ask_choice(
            "Your answer (A/B/C/D): ", VALID_CHOICES,
            input_fn, print_fn, strip=False,
        )

        text = _ask_explanation(input_fn, print_fn, allow_skip=True)

        if text:
            explanations[q["id"]] = text

    while len(explanations) < MIN_EXPLANATIONS:
        remaining = {
            str(n): q["id"] for n, q in enumerate(questions, start=1)
            if q["id"] not in explanations
        }

        print_fn(
            f"\nAt least {MIN_EXPLANATIONS} explanations are required "
            f"({len(explanations)} so far)."
        )

        number = ask_choice(
            "Which question number do you want to explain? ", remaining,
            input_fn, print_fn, hint="a question number you have not explained yet",
        )
        explanations[remaining[number]] = _ask_explanation(input_fn, print_fn)

    record = build_session_record(participant, answers, explanations, questions, now)
    show_results(record, questions, print_fn)

    path = save_session(record, directory)
    print_fn(f"\nSession record saved to: {path}")

    return record