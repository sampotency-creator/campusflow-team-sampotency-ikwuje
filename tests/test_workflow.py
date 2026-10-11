"""Tests for CampusFlow workflow, queue, reports, and persistence."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from campusflow.workflow import (
    StorageError,
    assign_ticket,
    change_ticket_status,
    display_report,
    display_work_queue,
    find_ticket,
    generate_report,
    get_work_queue,
    is_valid_ticket,
    load_tickets,
    next_ticket_id,
    reopen_ticket,
    save_tickets,
    validate_ticket_collection,
)


def make_ticket(
    ticket_id="T001",
    priority="critical",
    status="open",
    assigned_to=None,
):
    """Return a sample ticket using the shared project data structure."""

    return {
        "id": ticket_id,
        "title": "Campus internet outage",
        "category": "network",
        "urgency": "high",
        "affected_users": 12,
        "priority": priority,
        "status": status,
        "assigned_to": assigned_to,
    }


# --------------------------------------------------
# TICKET VALIDATION
# --------------------------------------------------

class TestTicketValidation(unittest.TestCase):

    def test_valid_ticket_is_accepted(self):
        self.assertTrue(is_valid_ticket(make_ticket()))

    def test_ticket_missing_a_required_field_is_rejected(self):
        ticket = make_ticket()
        del ticket["priority"]

        self.assertFalse(is_valid_ticket(ticket))

    def test_non_dictionary_is_rejected(self):
        self.assertFalse(is_valid_ticket("not a ticket"))

    def test_invalid_status_is_rejected(self):
        ticket = make_ticket(status="closed")

        self.assertFalse(is_valid_ticket(ticket))

    def test_invalid_priority_is_rejected(self):
        ticket = make_ticket(priority="urgent")

        self.assertFalse(is_valid_ticket(ticket))

    def test_negative_affected_users_is_rejected(self):
        ticket = make_ticket()
        ticket["affected_users"] = -1

        self.assertFalse(is_valid_ticket(ticket))

    def test_boolean_affected_users_is_rejected(self):
        ticket = make_ticket()
        ticket["affected_users"] = True

        self.assertFalse(is_valid_ticket(ticket))

    def test_blank_staff_name_is_not_a_valid_assignment(self):
        ticket = make_ticket(assigned_to="   ")

        self.assertFalse(is_valid_ticket(ticket))

    def test_duplicate_ticket_ids_are_rejected(self):
        tickets = [
            make_ticket("T001"),
            make_ticket("T001"),
        ]

        with self.assertRaises(ValueError):
            validate_ticket_collection(tickets)

    def test_ticket_ids_are_checked_without_case_sensitivity(self):
        tickets = [
            make_ticket("T001"),
            make_ticket("t001"),
        ]

        with self.assertRaises(ValueError):
            validate_ticket_collection(tickets)


# --------------------------------------------------
# FIND TICKET
# --------------------------------------------------

class TestFindTicket(unittest.TestCase):

    def setUp(self):
        self.tickets = [
            make_ticket("T001"),
            make_ticket("T002", priority="high"),
        ]

    def test_existing_ticket_is_found(self):
        ticket = find_ticket(self.tickets, "T001")

        self.assertIsNotNone(ticket)
        self.assertEqual(ticket["id"], "T001")

    def test_ticket_id_lookup_ignores_case(self):
        ticket = find_ticket(self.tickets, "t001")

        self.assertIsNotNone(ticket)
        self.assertEqual(ticket["id"], "T001")

    def test_unknown_ticket_returns_none(self):
        self.assertIsNone(find_ticket(self.tickets, "T999"))

    def test_non_string_id_returns_none(self):
        self.assertIsNone(find_ticket(self.tickets, None))


# --------------------------------------------------
# F3 - ASSIGN TICKET
# --------------------------------------------------

class TestAssignTicket(unittest.TestCase):

    def setUp(self):
        self.tickets = [make_ticket()]

    def test_existing_ticket_can_be_assigned(self):
        result = assign_ticket(
            self.tickets,
            "T001",
            "John Staff",
        )

        self.assertTrue(result)
        self.assertEqual(
            self.tickets[0]["assigned_to"],
            "John Staff",
        )

    def test_staff_name_is_trimmed(self):
        result = assign_ticket(
            self.tickets,
            "T001",
            "  John Staff  ",
        )

        self.assertTrue(result)
        self.assertEqual(
            self.tickets[0]["assigned_to"],
            "John Staff",
        )

    def test_empty_staff_name_is_rejected(self):
        result = assign_ticket(
            self.tickets,
            "T001",
            "",
        )

        self.assertFalse(result)
        self.assertIsNone(self.tickets[0]["assigned_to"])

    def test_whitespace_staff_name_is_rejected(self):
        result = assign_ticket(
            self.tickets,
            "T001",
            "   ",
        )

        self.assertFalse(result)
        self.assertIsNone(self.tickets[0]["assigned_to"])

    def test_non_string_staff_name_is_rejected(self):
        result = assign_ticket(
            self.tickets,
            "T001",
            None,
        )

        self.assertFalse(result)
        self.assertIsNone(self.tickets[0]["assigned_to"])

    def test_unknown_ticket_cannot_be_assigned(self):
        result = assign_ticket(
            self.tickets,
            "T999",
            "John Staff",
        )

        self.assertFalse(result)
        self.assertIsNone(self.tickets[0]["assigned_to"])

    def test_assignment_preserves_other_ticket_fields(self):
        original = self.tickets[0].copy()

        assign_ticket(
            self.tickets,
            "T001",
            "John Staff",
        )

        for field in (
            "id",
            "title",
            "category",
            "urgency",
            "affected_users",
            "priority",
            "status",
        ):
            self.assertEqual(
                self.tickets[0][field],
                original[field],
            )


# --------------------------------------------------
# F4 - WORKFLOW
# --------------------------------------------------

class TestWorkflow(unittest.TestCase):

    def test_unassigned_ticket_cannot_start_work(self):
        tickets = [make_ticket()]

        result = change_ticket_status(
            tickets,
            "T001",
            "in_progress",
        )

        self.assertFalse(result)
        self.assertEqual(tickets[0]["status"], "open")

    def test_assigned_ticket_can_start_work(self):
        tickets = [
            make_ticket(assigned_to="John Staff")
        ]

        result = change_ticket_status(
            tickets,
            "T001",
            "in_progress",
        )

        self.assertTrue(result)
        self.assertEqual(
            tickets[0]["status"],
            "in_progress",
        )

    def test_in_progress_ticket_can_be_resolved(self):
        tickets = [
            make_ticket(
                status="in_progress",
                assigned_to="John Staff",
            )
        ]

        result = change_ticket_status(
            tickets,
            "T001",
            "resolved",
        )

        self.assertTrue(result)
        self.assertEqual(
            tickets[0]["status"],
            "resolved",
        )

    def test_open_ticket_cannot_skip_to_resolved(self):
        tickets = [
            make_ticket(
                status="open",
                assigned_to="John Staff",
            )
        ]

        result = change_ticket_status(
            tickets,
            "T001",
            "resolved",
        )

        self.assertFalse(result)
        self.assertEqual(
            tickets[0]["status"],
            "open",
        )

    def test_resolved_ticket_cannot_directly_restart(self):
        tickets = [
            make_ticket(
                status="resolved",
                assigned_to="John Staff",
            )
        ]

        result = change_ticket_status(
            tickets,
            "T001",
            "in_progress",
        )

        self.assertFalse(result)
        self.assertEqual(
            tickets[0]["status"],
            "resolved",
        )

    def test_resolved_ticket_can_be_reopened(self):
        tickets = [
            make_ticket(
                status="resolved",
                assigned_to="John Staff",
            )
        ]

        result = reopen_ticket(tickets, "T001")

        self.assertTrue(result)
        self.assertEqual(tickets[0]["status"], "open")

    def test_open_ticket_cannot_be_reopened(self):
        tickets = [make_ticket(status="open")]

        result = reopen_ticket(tickets, "T001")

        self.assertFalse(result)
        self.assertEqual(tickets[0]["status"], "open")

    def test_in_progress_ticket_cannot_be_reopened(self):
        tickets = [
            make_ticket(
                status="in_progress",
                assigned_to="John Staff",
            )
        ]

        result = reopen_ticket(tickets, "T001")

        self.assertFalse(result)
        self.assertEqual(
            tickets[0]["status"],
            "in_progress",
        )

    def test_reopened_ticket_can_start_work_again(self):
        tickets = [
            make_ticket(
                status="resolved",
                assigned_to="John Staff",
            )
        ]

        self.assertTrue(reopen_ticket(tickets, "T001"))
        self.assertEqual(tickets[0]["status"], "open")

        self.assertTrue(
            change_ticket_status(
                tickets,
                "T001",
                "in_progress",
            )
        )

        self.assertEqual(
            tickets[0]["status"],
            "in_progress",
        )

    def test_unknown_ticket_status_change_is_rejected(self):
        tickets = [make_ticket()]

        result = change_ticket_status(
            tickets,
            "T999",
            "in_progress",
        )

        self.assertFalse(result)

    def test_invalid_status_is_rejected(self):
        tickets = [
            make_ticket(
                status="open",
                assigned_to="John Staff",
            )
        ]

        result = change_ticket_status(
            tickets,
            "T001",
            "closed",
        )

        self.assertFalse(result)
        self.assertEqual(tickets[0]["status"], "open")


# --------------------------------------------------
# F5 - WORK QUEUE
# --------------------------------------------------

class TestWorkQueue(unittest.TestCase):

    def test_queue_contains_only_unresolved_tickets(self):
        tickets = [
            make_ticket("T001", status="open"),
            make_ticket(
                "T002",
                priority="high",
                status="in_progress",
                assigned_to="John Staff",
            ),
            make_ticket(
                "T003",
                status="resolved",
            ),
        ]

        queue = get_work_queue(tickets)

        self.assertEqual(
            [ticket["id"] for ticket in queue],
            ["T001", "T002"],
        )

    def test_queue_orders_by_priority(self):
        tickets = [
            make_ticket("T001", priority="low"),
            make_ticket("T002", priority="critical"),
            make_ticket("T003", priority="medium"),
            make_ticket("T004", priority="high"),
        ]

        queue = get_work_queue(tickets)

        self.assertEqual(
            [ticket["id"] for ticket in queue],
            ["T002", "T004", "T003", "T001"],
        )

    def test_equal_priorities_use_numeric_ticket_id(self):
        tickets = [
            make_ticket("T10", priority="high"),
            make_ticket("T2", priority="high"),
            make_ticket("T1", priority="high"),
            make_ticket("T3", priority="critical"),
        ]

        queue = get_work_queue(tickets)

        self.assertEqual(
            [ticket["id"] for ticket in queue],
            ["T3", "T1", "T2", "T10"],
        )

    def test_empty_queue_returns_empty_list(self):
        self.assertEqual(get_work_queue([]), [])

    def test_display_work_queue_handles_empty_queue(self):
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            display_work_queue([])

        self.assertIn(
            "No open or in-progress tickets.",
            output.getvalue(),
        )


# --------------------------------------------------
# F6 - REPORTS
# --------------------------------------------------

class TestReports(unittest.TestCase):

    def test_report_total_ticket_count(self):
        tickets = [
            make_ticket("T001"),
            make_ticket("T002", priority="high"),
            make_ticket("T003", priority="low"),
        ]

        report = generate_report(tickets)

        self.assertEqual(report["total_tickets"], 3)

    def test_report_status_counts(self):
        tickets = [
            make_ticket("T001", status="open"),
            make_ticket(
                "T002",
                status="in_progress",
                assigned_to="John",
            ),
            make_ticket("T003", status="resolved"),
            make_ticket("T004", status="open"),
        ]

        report = generate_report(tickets)

        self.assertEqual(
            report["status_counts"],
            {
                "open": 2,
                "in_progress": 1,
                "resolved": 1,
            },
        )

    def test_report_priority_counts(self):
        tickets = [
            make_ticket("T001", priority="critical"),
            make_ticket("T002", priority="critical"),
            make_ticket("T003", priority="high"),
            make_ticket("T004", priority="medium"),
            make_ticket("T005", priority="low"),
        ]

        report = generate_report(tickets)

        self.assertEqual(
            report["priority_counts"],
            {
                "critical": 2,
                "high": 1,
                "medium": 1,
                "low": 1,
            },
        )

    def test_report_assignment_counts(self):
        tickets = [
            make_ticket("T001", assigned_to="John"),
            make_ticket("T002", assigned_to=None),
            make_ticket("T003", assigned_to="Mary"),
        ]

        report = generate_report(tickets)

        self.assertEqual(report["assigned_tickets"], 2)
        self.assertEqual(report["unassigned_tickets"], 1)

    def test_empty_report_contains_zero_counts(self):
        report = generate_report([])

        self.assertEqual(report["total_tickets"], 0)

        self.assertEqual(
            report["status_counts"],
            {
                "open": 0,
                "in_progress": 0,
                "resolved": 0,
            },
        )

        self.assertEqual(
            report["priority_counts"],
            {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            },
        )

        self.assertEqual(report["assigned_tickets"], 0)
        self.assertEqual(report["unassigned_tickets"], 0)

    def test_display_report_handles_empty_collection(self):
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            display_report([])

        self.assertIn("Total tickets: 0", output.getvalue())


# --------------------------------------------------
# F7 - JSON PERSISTENCE
# --------------------------------------------------

class TestPersistence(unittest.TestCase):

    def test_missing_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tickets.json"

            self.assertEqual(load_tickets(path), [])

    def test_save_and_reload_tickets(self):
        tickets = [
            make_ticket(
                "T001",
                priority="critical",
                status="open",
                assigned_to="John",
            ),
            make_ticket(
                "T002",
                priority="high",
                status="in_progress",
                assigned_to="Mary",
            ),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tickets.json"

            save_tickets(tickets, path)
            loaded = load_tickets(path)

            self.assertEqual(loaded, tickets)

    def test_saved_file_contains_valid_json(self):
        tickets = [make_ticket("T001")]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tickets.json"

            save_tickets(tickets, path)

            with path.open("r", encoding="utf-8") as file:
                loaded = json.load(file)

            self.assertEqual(loaded, tickets)

    def test_malformed_json_raises_storage_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tickets.json"

            bad_content = '{"broken": '
            path.write_text(bad_content, encoding="utf-8")

            with self.assertRaises(StorageError) as context:
                load_tickets(path)

            self.assertIn(
                "Malformed JSON",
                str(context.exception),
            )

            # The malformed file must not be silently erased.
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                bad_content,
            )

    def test_duplicate_ids_are_rejected_when_saving(self):
        tickets = [
            make_ticket("T001"),
            make_ticket("T001"),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tickets.json"

            with self.assertRaises(StorageError):
                save_tickets(tickets, path)

    def test_duplicate_ids_are_rejected_when_loading(self):
        tickets = [
            make_ticket("T001"),
            make_ticket("T001"),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tickets.json"

            path.write_text(
                json.dumps(tickets),
                encoding="utf-8",
            )

            with self.assertRaises(StorageError):
                load_tickets(path)

    def test_invalid_ticket_data_is_rejected_when_loading(self):
        tickets = [
            make_ticket(
                "T001",
                status="not_a_valid_status",
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tickets.json"

            path.write_text(
                json.dumps(tickets),
                encoding="utf-8",
            )

            with self.assertRaises(StorageError):
                load_tickets(path)

    def test_non_list_json_data_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tickets.json"

            path.write_text(
                json.dumps({"ticket": make_ticket()}),
                encoding="utf-8",
            )

            with self.assertRaises(StorageError):
                load_tickets(path)

    def test_next_ticket_id_uses_highest_existing_id(self):
        tickets = [
            make_ticket("T001"),
            make_ticket("T002"),
            make_ticket("T007"),
        ]

        self.assertEqual(next_ticket_id(tickets), "T008")

    def test_next_ticket_id_works_after_reload(self):
        tickets = [
            make_ticket("T001"),
            make_ticket("T007"),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tickets.json"

            save_tickets(tickets, path)
            loaded = load_tickets(path)

            self.assertEqual(next_ticket_id(loaded), "T008")

    def test_next_ticket_id_for_empty_collection(self):
        self.assertEqual(next_ticket_id([]), "T001")


if __name__ == "__main__":
    unittest.main()