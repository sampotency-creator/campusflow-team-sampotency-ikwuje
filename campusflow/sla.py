
"""SLA attention queue and metrics.

Tickets get an OPTIONAL 'created_at' ISO timestamp. The due time is
created_at + the SLA window for the ticket's priority. Tickets without
created_at are 'untracked' and never appear in the attention queue.
'now' is always passed in, so tests control the clock.
"""

from datetime import datetime, timedelta, timezone

from campusflow.workflow import (
    PRIORITY_ORDER,
    _numeric_ticket_id,
    is_valid_ticket,
)

SLA_HOURS = {
    "critical": 4,
    "high": 8,
    "medium": 24,
    "low": 72,
}

UNRESOLVED = {"open", "in_progress"}
DEFAULT_WARN_MINUTES = 240


def parse_created_at(ticket):
    """Return created_at as an aware UTC datetime, or None."""

    value = ticket.get("created_at")

    if not isinstance(value, str):
        return None

    try:
        created = datetime.fromisoformat(value)
    except ValueError:
        return None

    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    return created


def due_at(ticket):
    created = parse_created_at(ticket)

    if created is None:
        return None

    return created + timedelta(hours=SLA_HOURS[ticket["priority"]])


def _unresolved(tickets):
    return [
        t for t in tickets
        if is_valid_ticket(t) and t["status"] in UNRESOLVED
    ]


def get_sla_attention_queue(tickets, now, warn_minutes=DEFAULT_WARN_MINUTES):
    """Return overdue tickets and tickets due within warn_minutes.

    Sort order (fully deterministic):
        1. overdue before not-overdue
        2. earliest due time first (= most overdue first)
        3. priority (critical first)
        4. numeric ticket ID
    The input list is never modified and no events are created.
    """

    window = timedelta(minutes=warn_minutes)
    rows = []

    for ticket in _unresolved(tickets):
        due = due_at(ticket)

        if due is None or due > now + window:
            continue

        rows.append(
            {
                "ticket": ticket,
                "id": ticket["id"],
                "due_at": due,
                "overdue": due < now,
                "minutes_remaining": round((due - now).total_seconds() / 60),
            }
        )

    rows.sort(
        key=lambda row: (
            not row["overdue"],
            row["due_at"],
            PRIORITY_ORDER[row["ticket"]["priority"]],
            _numeric_ticket_id(row["ticket"]),
        )
    )

    return rows


def sla_metrics(tickets, now, warn_minutes=DEFAULT_WARN_MINUTES):
    """Summarise SLA health of unresolved tickets."""

    window = timedelta(minutes=warn_minutes)
    unresolved = _unresolved(tickets)
    overdue = due_soon = untracked = 0
    ages = []

    for ticket in unresolved:
        due = due_at(ticket)

        if due is None:
            untracked += 1
            continue

        ages.append((now - parse_created_at(ticket)).total_seconds() / 60)

        if due < now:
            overdue += 1
        elif due <= now + window:
            due_soon += 1

    return {
        "unresolved": len(unresolved),
        "overdue": overdue,
        "due_soon": due_soon,
        "untracked": untracked,
        "avg_age_minutes": round(sum(ages) / len(ages), 1) if ages else None,
    }


def display_sla_queue(tickets, now=None, print_fn=print):
    now = now or datetime.now(timezone.utc)
    queue = get_sla_attention_queue(tickets, now)
    metrics = sla_metrics(tickets, now)

    print_fn("\n========== SLA ATTENTION QUEUE ==========")

    if not queue:
        print_fn("No tickets need SLA attention.")

    for row in queue:
        ticket = row["ticket"]
        mins = row["minutes_remaining"]
        timing = f"OVERDUE by {-mins} min" if row["overdue"] else f"due in {mins} min"

        print_fn(
            f"\n{ticket['id']} [{ticket['priority']}] {ticket['title']}"
            f"\n  Status: {ticket['status']} | {timing}"
        )

    print_fn(
        f"\nUnresolved: {metrics['unresolved']} | Overdue: {metrics['overdue']}"
        f" | Due soon: {metrics['due_soon']} | No SLA data: {metrics['untracked']}"
        f" | Avg age: {metrics['avg_age_minutes']} min"
    )
    print_fn("=========================================")