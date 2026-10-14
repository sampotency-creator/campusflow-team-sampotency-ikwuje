
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from campusflow.knowledge_lab import (
    MAX_WORDS,
    QUESTIONS,
    build_session_record,
    is_valid_choice,
    load_session,
    run_lab,
    save_session,
    score_answers,
    split_sentences,
    topics_to_revise,
    validate_explanation,
)
from helpers import make_ticket

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
GOOD = "I chose this because it keeps the audit trail trustworthy."


def correct_answers():
    return {q["id"]: q["correct"] for q in QUESTIONS}


def wrong_answers():
    return {q["id"]: next(c for c in "ABCD" if c != q["correct"]) for q in QUESTIONS}


def scripted(values, log=None):
    it = iter(values)

    def fake_input(prompt=""):
        if log is not None:
            log.append(prompt)
        return next(it)

    return fake_input


def full_script(participant="A", explain_first=3, first_question_noise=()):
    """Inputs for a perfect run, explaining the first N answers."""

    values = [participant]

    for index, q in enumerate(QUESTIONS):
        if index == 0:
            values.extend(first_question_noise)   # invalid answers to be rejected
        values.append(q["correct"])
        values.append(f"I picked this because it relates to {q['topic']}." if index < explain_first else "")

    return values


class TestQuestionBank(unittest.TestCase):

    def test_exactly_ten_well_formed_questions(self):
        self.assertEqual(len(QUESTIONS), 10)
        self.assertEqual(len({q["id"] for q in QUESTIONS}), 10)

        for q in QUESTIONS:
            self.assertEqual(set(q["options"]), set("ABCD"))
            self.assertIn(q["correct"], "ABCD")
            self.assertTrue(q["topic"] and q["rationale"] and q["prompt"])

    def test_answer_key_is_not_a_single_letter(self):
        self.assertGreater(len({q["correct"] for q in QUESTIONS}), 1)


class TestScoring(unittest.TestCase):

    def test_all_correct_is_ten(self):
        self.assertEqual(score_answers(correct_answers()), 10)

    def test_all_wrong_is_zero(self):
        self.assertEqual(score_answers(wrong_answers()), 0)

    def test_mixed_score(self):
        answers = wrong_answers()
        for q in QUESTIONS[:4]:
            answers[q["id"]] = q["correct"]
        self.assertEqual(score_answers(answers), 4)

    def test_missing_and_invalid_answers_score_zero(self):
        self.assertEqual(score_answers({}), 0)
        self.assertEqual(score_answers({"Q1": "a", "Q2": None, "Q3": 3}), 0)

    def test_topics_to_revise_are_wrong_ones_in_order_without_duplicates(self):
        answers = correct_answers()
        answers["Q3"] = next(c for c in "ABCD" if c != QUESTIONS[2]["correct"])
        answers["Q1"] = next(c for c in "ABCD" if c != QUESTIONS[0]["correct"])
        self.assertEqual(topics_to_revise(answers),
                         [QUESTIONS[0]["topic"], QUESTIONS[2]["topic"]])
        self.assertEqual(topics_to_revise(correct_answers()), [])


class TestChoiceValidation(unittest.TestCase):

    def test_only_exact_uppercase_letters_valid(self):
        for good in "ABCD":
            self.assertTrue(is_valid_choice(good))
        for bad in ["a", " A", "A ", "", "AB", "E", "1", None, 5]:
            self.assertFalse(is_valid_choice(bad), repr(bad))


class TestSessionRecord(unittest.TestCase):

    explanations = {"Q1": GOOD, "Q2": GOOD, "Q3": GOOD}

    def test_record_has_every_required_field(self):
        record = build_session_record("B", correct_answers(), self.explanations, now=NOW)
        for field in ("participant", "timestamp_utc", "choices", "score", "explanations"):
            self.assertIn(field, record)
        self.assertEqual(record["participant"], "B")
        self.assertEqual(record["score"], 10)
        self.assertTrue(record["timestamp_utc"].endswith("+00:00"))

    def test_fewer_than_three_explanations_rejected(self):
        with self.assertRaises(ValueError):
            build_session_record("A", correct_answers(), {"Q1": GOOD, "Q2": GOOD})

    def test_blank_explanation_rejected(self):
        with self.assertRaises(ValueError):
            build_session_record("A", correct_answers(),
                                 {"Q1": GOOD, "Q2": GOOD, "Q3": "   "})

    def test_bad_participant_rejected(self):
        with self.assertRaises(ValueError):
            build_session_record("C", correct_answers(), self.explanations)

    def test_saved_json_round_trips(self):
        record = build_session_record("A", wrong_answers(), self.explanations, now=NOW)

        with tempfile.TemporaryDirectory() as directory:
            path = save_session(record, directory)
            self.assertEqual(load_session(path), record)
            self.assertEqual(json.loads(Path(path).read_text()), record)


class TestExplanationFormat(unittest.TestCase):

    def ok(self, text):
        return validate_explanation(text)[0]

    def test_one_and_two_sentences_accepted(self):
        self.assertTrue(self.ok("I chose C because status is a fast read."))
        self.assertTrue(self.ok("I chose C. Status is fast and history explains the changes."))

    def test_three_sentences_rejected_with_guidance(self):
        ok, message = validate_explanation("First point here. Second point here. Third point here.")
        self.assertFalse(ok)
        self.assertIn("one or two sentences", message)

    def test_too_few_words_rejected(self):
        for text in ["idk", "Because.", "It is right", "yes. no."]:
            ok, message = validate_explanation(text)
            self.assertFalse(ok, text)
            self.assertIn("Too short", message)

    def test_blank_and_non_string_rejected(self):
        for value in ["", "   ", "\n", None, 7]:
            self.assertFalse(self.ok(value), repr(value))

    def test_punctuation_only_words_do_not_count(self):
        self.assertFalse(self.ok("... --- ??? !!! ###"))

    def test_too_many_words_rejected(self):
        long_text = " ".join(["word"] * (MAX_WORDS + 1)) + "."
        ok, message = validate_explanation(long_text)
        self.assertFalse(ok)
        self.assertIn("words or fewer", message)

    def test_decimals_and_versions_do_not_split_sentences(self):
        text = "Python 3.12 sorts T10 before T2 as text, so use numeric IDs."
        self.assertEqual(len(split_sentences(text)), 1)
        self.assertTrue(self.ok(text))

    def test_content_is_not_graded(self):
        # Well-formed but wrong reasoning is accepted: only a mentor judges it.
        self.assertTrue(self.ok("Bananas are blue because I like them."))

    def test_record_rejects_badly_formatted_explanation(self):
        bad = {"Q1": GOOD, "Q2": GOOD, "Q3": "One. Two. Three. Four. Five."}
        with self.assertRaises(ValueError):
            build_session_record("A", correct_answers(), bad)

    def test_record_stores_whitespace_normalized_text(self):
        messy = {"Q1": "  I chose this   because\nit is clear.  ", "Q2": GOOD, "Q3": GOOD}
        record = build_session_record("A", correct_answers(), messy)
        self.assertEqual(record["explanations"]["Q1"], "I chose this because it is clear.")


class TestInteractiveLab(unittest.TestCase):

    def test_inline_invalid_explanation_reprompts_and_enter_still_skips(self):
        messages = []
        values = ["A"]

        for index, q in enumerate(QUESTIONS):
            values.append(q["correct"])
            if index == 0:
                values += ["idk", "One. Two. Three. Four. Five.", GOOD]   # 2 rejections
            elif index < 3:
                values.append(GOOD)
            else:
                values.append("")                                          # skip

        with tempfile.TemporaryDirectory() as directory:
            record = run_lab(scripted(values), messages.append, directory, now=NOW)

        self.assertEqual(set(record["explanations"]), {"Q1", "Q2", "Q3"})
        self.assertTrue(any("Too short" in m for m in messages))
        self.assertTrue(any("Too long" in m for m in messages))

    def test_lab_shows_explanation_rules_up_front(self):
        messages = []

        with tempfile.TemporaryDirectory() as directory:
            run_lab(scripted(full_script()), messages.append, directory, now=NOW)

        self.assertTrue(any("one or two sentences" in m for m in messages))

    def run_lab_with(self, values, directory, log=None, messages=None):
        sink = messages.append if messages is not None else (lambda _m: None)
        return run_lab(scripted(values, log), sink, directory, now=NOW)

    def test_perfect_run_scores_ten_and_saves_record(self):
        with tempfile.TemporaryDirectory() as directory:
            record = self.run_lab_with(full_script("B"), directory)
            files = list(Path(directory).glob("lab_B_*.json"))

            self.assertEqual(record["score"], 10)
            self.assertEqual(len(record["explanations"]), 3)
            self.assertEqual(len(files), 1)
            self.assertEqual(load_session(files[0]), record)

    def test_invalid_answers_reprompt(self):
        messages = []

        with tempfile.TemporaryDirectory() as directory:
            record = self.run_lab_with(
                full_script(first_question_noise=["a", "", " A", "AB", "E"]),
                directory, messages=messages)

        self.assertEqual(record["score"], 10)
        self.assertEqual(sum("Invalid input" in m for m in messages), 5)

    def test_invalid_participant_reprompts(self):
        with tempfile.TemporaryDirectory() as directory:
            values = ["a", "C", ""] + full_script("A")
            record = self.run_lab_with(values, directory)

        self.assertEqual(record["participant"], "A")

    def test_lab_forces_three_explanations_when_user_skips_them(self):
        values = full_script(explain_first=0) + ["4", GOOD, "4", "7", GOOD, "9", GOOD]
        # '4' again is rejected once it has been explained.

        with tempfile.TemporaryDirectory() as directory:
            record = self.run_lab_with(values, directory)

        self.assertEqual(set(record["explanations"]), {"Q4", "Q7", "Q9"})

    def test_blank_forced_explanation_reprompts(self):
        values = full_script(explain_first=0) + ["1", "", "  ", "ok", GOOD, "2", GOOD, "3", GOOD]

        with tempfile.TemporaryDirectory() as directory:
            record = self.run_lab_with(values, directory)

        self.assertEqual(record["explanations"]["Q1"], GOOD)

    def test_running_lab_leaves_ticket_data_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            tickets_file = Path(directory) / "tickets.json"
            tickets_file.write_text(json.dumps([make_ticket()], indent=4))
            before = hashlib.sha256(tickets_file.read_bytes()).hexdigest()

            self.run_lab_with(full_script(), Path(directory) / "sessions")

            after = hashlib.sha256(tickets_file.read_bytes()).hexdigest()

        self.assertEqual(before, after)

    def test_results_show_score_topics_and_explanations(self):
        messages = []
        values = ["A"]

        for index, q in enumerate(QUESTIONS):
            wrong = next(c for c in "ABCD" if c != q["correct"])
            values += [wrong, f"I chose this answer because reason number {index} applies." if index < 3 else ""]

        with tempfile.TemporaryDirectory() as directory:
            self.run_lab_with(values, directory, messages=messages)

        output = "\n".join(messages)
        self.assertIn("Score: 0/10", output)
        self.assertIn("Topics to revise:", output)
        self.assertIn("Your explanation: I chose this answer because reason number 0 applies.", output)


if __name__ == "__main__":
    unittest.main()