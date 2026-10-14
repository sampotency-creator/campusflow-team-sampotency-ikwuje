import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
from campusflow.cli_input import ask_choice, confirm
from campusflow.workflow import load_tickets
from helpers import make_ticket


def scripted(values):
    it = iter(values)
    return lambda prompt="": next(it)


class TestAskChoice(unittest.TestCase):

    def test_reprompts_until_exact_valid_input(self):
        prompts, messages = [], []
        values = iter(["x", "", "a", " A", "AB", "A"])

        def fake_input(prompt):
            prompts.append(prompt)
            return next(values)

        result = ask_choice("Choose: ", {"A", "B"}, fake_input, messages.append, strip=False)

        self.assertEqual(result, "A")
        self.assertEqual(len(prompts), 6)
        self.assertEqual(len(messages), 5)

    def test_menu_input_tolerates_surrounding_spaces_but_not_garbage(self):
        valid = {str(n) for n in range(1, 13)}
        messages = []
        result = ask_choice("> ", valid, scripted(["0", "13", "abc", "1.5", " 7 "]),
                            messages.append)

        self.assertEqual(result, "7")
        self.assertEqual(len(messages), 4)


class TestConfirm(unittest.TestCase):

    def test_accepts_y_and_n_only(self):
        messages = []
        self.assertTrue(confirm("ok?", scripted(["maybe", "", "Y"]), messages.append))
        self.assertEqual(len(messages), 2)
        self.assertFalse(confirm("ok?", scripted(["N"]), messages.append))


class TestDuplicateConfirmationFlow(unittest.TestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.paths = {
            "tickets_path": Path(folder.name) / "tickets.json",
            "events_path": Path(folder.name) / "events.json",
        }
        self.tickets = [make_ticket("T001", " Wi-Fi   Down ")]
        self.events = []

    def create(self, new_ticket, answers):
        with patch("main.get_ticket_input", return_value=new_ticket):
            return main.create_new_ticket(
                self.tickets, self.events, scripted(answers), **self.paths)

    def test_declining_creates_nothing(self):
        result = self.create(make_ticket("T002", "wi-fi down"), ["n"])

        self.assertFalse(result)
        self.assertEqual(len(self.tickets), 1)
        self.assertEqual(self.events, [])
        self.assertFalse(self.paths["tickets_path"].exists())

    def test_confirming_creates_ticket_event_and_saves(self):
        result = self.create(make_ticket("T002", "wi-fi down"), ["maybe", "y"])

        self.assertTrue(result)
        self.assertEqual([t["id"] for t in self.tickets], ["T001", "T002"])
        self.assertEqual([e["action"] for e in self.events], ["TICKET_CREATED"])
        self.assertIn("created_at", self.tickets[1])
        self.assertEqual(len(load_tickets(self.paths["tickets_path"])), 2)

    def test_non_duplicate_creates_without_asking(self):
        # scripted([]) raises StopIteration if any prompt appears.
        result = self.create(make_ticket("T002", "Printer jam", category="Hardware"), [])

        self.assertTrue(result)
        self.assertEqual(len(self.tickets), 2)

    def test_resolved_match_does_not_trigger_warning(self):
        self.tickets[0]["status"] = "resolved"
        self.assertTrue(self.create(make_ticket("T002", "wi-fi down"), []))


class TestRejectedOperationsReportFailure(unittest.TestCase):

    def test_rejected_status_change_does_not_claim_success_or_save(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = {"tickets_path": Path(folder) / "t.json",
                     "events_path": Path(folder) / "e.json"}
            tickets, events = [make_ticket("T001")], []

            result = main.update_ticket_status(
                tickets, events, scripted(["T001", "resolved"]), **paths)

            self.assertFalse(result)
            self.assertEqual(events, [])
            self.assertFalse(paths["tickets_path"].exists())


if __name__ == "__main__":
    unittest.main()