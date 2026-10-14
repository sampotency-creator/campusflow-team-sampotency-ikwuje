
import tempfile
import unittest
from pathlib import Path

from campusflow.history import (
    load_events,
    record_event,
    save_events,
)

from campusflow.tickets import create_ticket

from campusflow.workflow import (
    assign_ticket,
    change_ticket_status,
    get_work_queue,
    reopen_ticket,
)


class TestEventHistory(unittest.TestCase):

    def setUp(self):
        self.events = []

        self.ticket = create_ticket(
            title="Wi-Fi is down",
            category="Network",
            urgency="high",
            affected_users=12,
            ticket_number=1,
        )

        self.tickets = [self.ticket]

    def test_successful_operations_record_exact_sequence(self):

        # Record ticket creation.

        record_event(
            self.events,
            "T001",
            "TICKET_CREATED",
            "Engineer B",
            {"status": "open"},
        )

        # Assign the ticket.

        self.assertTrue(
            assign_ticket(
                self.tickets,
                "T001",
                "Network Team",
                events=self.events,
                actor="Engineer B",
            )
        )

        # Start work.

        self.assertTrue(
            change_ticket_status(
                self.tickets,
                "T001",
                "in_progress",
                events=self.events,
                actor="Engineer B",
            )
        )

        # Resolve the ticket.

        self.assertTrue(
            change_ticket_status(
                self.tickets,
                "T001",
                "resolved",
                events=self.events,
                actor="Engineer B",
            )
        )

        # Reopen the ticket.
        
        self.assertTrue(
            reopen_ticket(
                self.tickets,
                "T001",
                events=self.events,
                actor="Engineer B",
            )
        )

        actual_actions = [
            event["action"]
            for event in self.events
        ]

        expected_actions = [
            "TICKET_CREATED",
            "TICKET_ASSIGNED",
            "STATUS_CHANGED",
            "STATUS_CHANGED",
            "TICKET_REOPENED",
        ]

        self.assertEqual(actual_actions, expected_actions)

        self.assertEqual(
            self.events[2]["details"],
            {"from": "open", "to": "in_progress"},
        )

        self.assertEqual(
            self.events[3]["details"],
            {"from": "in_progress", "to": "resolved"},
        )

        self.assertEqual(self.ticket["status"], "open")

    def test_illegal_transition_does_not_append_event(self):

        # This ticket is open and has not been assigned.

        record_event(
            self.events,
            "T001",
            "TICKET_CREATED",
            "Engineer B",
            {"status": "open"},
        )

        original_events = list(self.events)

        result = change_ticket_status(
            self.tickets,
            "T001",
            "resolved",
            events=self.events,
            actor="Engineer B",
        )

        self.assertFalse(result)
        self.assertEqual(self.ticket["status"], "open")
        self.assertEqual(self.events, original_events)

    def test_unassigned_ticket_cannot_start_work_or_create_event(self):
        original_events = list(self.events)

        result = change_ticket_status(
            self.tickets,
            "T001",
            "in_progress",
            events=self.events,
            actor="Engineer B",
        )

        self.assertFalse(result)
        self.assertEqual(self.ticket["status"], "open")
        self.assertEqual(self.events, original_events)

    def test_event_history_survives_save_and_reload(self):
        record_event(
            self.events,
            "T001",
            "TICKET_CREATED",
            "Engineer B",
            {"status": "open"},
        )

        with tempfile.TemporaryDirectory() as directory:
            history_path = Path(directory) / "events.json"

            save_events(self.events, history_path)

            loaded_events = load_events(history_path)

        self.assertEqual(loaded_events, self.events)

    def test_original_work_queue_rules_are_preserved(self):
        # The new history feature must not change the existing queue.
        self.assertEqual(
            [ticket["id"] for ticket in get_work_queue(self.tickets)],
            ["T001"],
        )


if __name__ == "__main__":
    unittest.main()