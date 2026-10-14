
"""Duplicate ticket detection."""

UNRESOLVED_STATUSES = {"open", "in_progress"}


def normalize_text(text):
    """Trim, case-fold and collapse internal whitespace.

    ' Wi-Fi   Down ' -> 'wi-fi down'
    """

    if not isinstance(text, str):
        return ""

    return " ".join(text.casefold().split())


def detect_duplicates(category, title, tickets):
    """Return unresolved tickets with the same category and title.

    Both values are normalized first. Resolved tickets are ignored,
    because the same fault can legitimately come back later.
    Blank input never matches anything.
    """

    wanted_category = normalize_text(category)
    wanted_title = normalize_text(title)

    if not wanted_category or not wanted_title:
        return []

    return [
        ticket
        for ticket in tickets
        if ticket.get("status") in UNRESOLVED_STATUSES
        and normalize_text(ticket.get("category")) == wanted_category
        and normalize_text(ticket.get("title")) == wanted_title
    ]