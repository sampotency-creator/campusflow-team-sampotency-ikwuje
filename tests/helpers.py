"""Shared test helpers."""


def make_ticket(ticket_id="T001", title="Wi-Fi is down", category="Network",
                status="open", priority="high", assigned_to=None, created_at=None):
    ticket = {
        "id": ticket_id,
        "title": title,
        "category": category,
        "urgency": "high",
        "affected_users": 5,
        "priority": priority,
        "status": status,
        "assigned_to": assigned_to,
    }

    if created_at is not None:
        ticket["created_at"] = created_at

    return ticket
