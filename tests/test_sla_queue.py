import copy
import unittest
from datetime import datetime, timedelta, timezone

from campusflow.sla import get_sla_attention_queue, sla_metrics
from helpers import make_ticket

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


def made(ticket_id, priority, hours_ago, status="open", **kwargs):
    created = (NOW - timedelta(hours=hours_ago)).isoformat()
    return make_ticket(ticket_id, priority=priority, status=status,
                       created_at=created, **kwargs)


def fixture():
    # SLA hours: critical 4, high 8, medium 24, low 72
    return [
        made("T006", "critical", 3),            # due in 60 min  -> due soon
        made("T001", "high", 10),               # due 2 h ago    -> overdue
        made("T004", "low", 1),                 # due in 71 h    -> outside window
        made("T003", "medium", 23.5),           # due in 30 min  -> due soon
        made("T002", "critical", 5),            # due 1 h ago    -> overdue
        made("T005", "critical", 50, status="resolved"),  # resolved -> never shown
    ]


class TestSlaAttentionQueue(unittest.TestCase):

    def ids(self, tickets):
        return [row["id"] for row in get_sla_attention_queue(tickets, NOW)]

    def test_overdue_first_then_soonest_due(self):
        self.assertEqual(self.ids(fixture()), ["T001", "T002", "T003", "T006"])

    def test_overdue_flags(self):
        rows = {r["id"]: r for r in get_sla_attention_queue(fixture(), NOW)}
        self.assertTrue(rows["T001"]["overdue"])
        self.assertTrue(rows["T002"]["overdue"])
        self.assertFalse(rows["T003"]["overdue"])
        self.assertEqual(rows["T003"]["minutes_remaining"], 30)

    def test_more_overdue_ticket_comes_first(self):
        self.assertLess(self.ids(fixture()).index("T001"),
                        self.ids(fixture()).index("T002"))

    def test_resolved_and_far_future_tickets_excluded(self):
        result = self.ids(fixture())
        self.assertNotIn("T005", result)
        self.assertNotIn("T004", result)

    def test_equal_due_time_falls_back_to_priority(self):
        # Both due at NOW + 1h. critical created 3h ago, high created 7h ago.
        tickets = [made("T001", "high", 7), made("T009", "critical", 3)]
        self.assertEqual(self.ids(tickets), ["T009", "T001"])

    def test_equal_due_and_priority_falls_back_to_numeric_id(self):
        # String sort would put T010 before T002.
        tickets = [made("T010", "critical", 3), made("T002", "critical", 3)]
        self.assertEqual(self.ids(tickets), ["T002", "T010"])

    def test_input_order_does_not_change_result(self):
        forward = fixture()
        backward = list(reversed(fixture()))
        self.assertEqual(self.ids(forward), self.ids(backward))

    def test_ticket_without_created_at_is_excluded(self):
        tickets = [make_ticket("T001"), made("T002", "critical", 5)]
        self.assertEqual(self.ids(tickets), ["T002"])

    def test_exactly_due_now_is_not_overdue(self):
        tickets = [made("T001", "critical", 4)]
        row = get_sla_attention_queue(tickets, NOW)[0]
        self.assertFalse(row["overdue"])

    def test_queue_is_read_only(self):
        tickets = fixture()
        snapshot = copy.deepcopy(tickets)
        get_sla_attention_queue(tickets, NOW)
        sla_metrics(tickets, NOW)
        self.assertEqual(tickets, snapshot)


class TestSlaMetrics(unittest.TestCase):

    def test_metrics_on_fixed_clock(self):
        metrics = sla_metrics(fixture(), NOW)
        self.assertEqual(metrics["unresolved"], 5)
        self.assertEqual(metrics["overdue"], 2)
        self.assertEqual(metrics["due_soon"], 2)
        self.assertEqual(metrics["untracked"], 0)
        # ages: 10 + 5 + 23.5 + 1 + 3 = 42.5 h over 5 tickets = 8.5 h
        self.assertEqual(metrics["avg_age_minutes"], 510.0)

    def test_untracked_tickets_are_counted_not_averaged(self):
        metrics = sla_metrics([make_ticket("T001"), made("T002", "high", 2)], NOW)
        self.assertEqual(metrics["untracked"], 1)
        self.assertEqual(metrics["avg_age_minutes"], 120.0)

    def test_empty_input(self):
        metrics = sla_metrics([], NOW)
        self.assertEqual(metrics["unresolved"], 0)
        self.assertIsNone(metrics["avg_age_minutes"])


if __name__ == "__main__":
    unittest.main()