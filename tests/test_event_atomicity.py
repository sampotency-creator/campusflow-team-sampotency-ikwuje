import unittest
from unittest.mock import patch

from campusflow.workflow import (
    assign_ticket,
    change_ticket_status,
    reopen_ticket,
)
from helpers import make_ticket


class TestEventAtomicity(unittest.TestCase):

    def test_bad_events_container_leaves_ticket_unchanged(self):
        tickets = [make_ticket()]

        with self.assertRaises(ValueError):
            assign_ticket(tickets, "T001", "Network Team", events="not a list")

        self.assertIsNone(tickets[0]["assigned_to"])

    def test_event_creation_failure_leaves_ticket_and_history_unchanged(self):
        tickets = [make_ticket(assigned_to="Network Team")]
        events = []

        with patch("campusflow.workflow.create_event", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                change_ticket_status(tickets, "T001", "in_progress", events=events)

        self.assertEqual(tickets[0]["status"], "open")
        self.assertEqual(events, [])

    def test_each_success_appends_exactly_one_event(self):
        tickets = [make_ticket()]
        events = []

        assign_ticket(tickets, "T001", "Network Team", events=events)
        self.assertEqual(len(events), 1)

        change_ticket_status(tickets, "T001", "in_progress", events=events)
        self.assertEqual(len(events), 2)

    def test_every_rejected_operation_appends_nothing(self):
        tickets = [make_ticket()]
        events = []

        self.assertFalse(change_ticket_status(tickets, "T001", "resolved", events=events))
        self.assertFalse(change_ticket_status(tickets, "T001", "in_progress", events=events))
        self.assertFalse(change_ticket_status(tickets, "T001", "banana", events=events))
        self.assertFalse(change_ticket_status(tickets, "T999", "resolved", events=events))
        self.assertFalse(assign_ticket(tickets, "T001", "   ", events=events))
        self.assertFalse(assign_ticket(tickets, "T999", "Bob", events=events))
        self.assertFalse(reopen_ticket(tickets, "T001", events=events))

        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()