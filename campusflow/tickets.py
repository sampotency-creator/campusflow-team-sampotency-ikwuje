VALID_CATEGORIES = {
    "network",
    "hardware",
    "software",
    "other",
}

VALID_URGENCIES = {
    "low",
    "medium",
    "high",
}


def validate_title(title):
    """Check that the ticket title is not empty."""

    if not isinstance(title, str):
        raise ValueError("Title must be text.")

    title = title.strip()

    if not title:
        raise ValueError("Title cannot be empty.")

    return title


def validate_category(category):
    """Check that the category is supported."""

    if not isinstance(category, str):
        raise ValueError("Category must be text.")

    category = category.strip().lower()

    if category not in VALID_CATEGORIES:
        raise ValueError(
            "Category must be Network, Hardware, Software, or Other."
        )

    return category


def validate_urgency(urgency):
    """Check that the urgency is supported."""

    if not isinstance(urgency, str):
        raise ValueError("Urgency must be text.")

    urgency = urgency.strip().lower()

    if urgency not in VALID_URGENCIES:
        raise ValueError("Urgency must be low, medium, or high.")

    return urgency


def validate_affected_users(affected_users):
    """Check that the number of affected users is a positive integer."""

    if isinstance(affected_users, bool):
        raise ValueError("Affected users must be a positive integer.")

    if not isinstance(affected_users, int):
        raise ValueError("Affected users must be a whole number.")

    if affected_users <= 0:
        raise ValueError("Affected users must be greater than zero.")

    return affected_users

def calculate_priority(urgency, affected_users):
    """Calculate a ticket's priority using the agreed rules."""

    urgency = validate_urgency(urgency)
    affected_users = validate_affected_users(affected_users)

    if urgency == "high" and affected_users >= 10:
        return "critical"

    if urgency == "high" or affected_users >= 10:
        return "high"

    if urgency == "medium" or affected_users >= 3:
        return "medium"

    return "low"

def generate_ticket_id(number):
    """Generate a ticket ID from a ticket number."""

    if not isinstance(number, int) or isinstance(number, bool):
        raise ValueError("Ticket number must be an integer.")

    if number <= 0:
        raise ValueError("Ticket number must be greater than zero.")

    return f"T{number:03d}"

def create_ticket(title, category, urgency, affected_users, ticket_number):
    """Validate information and create a complete helpdesk ticket."""

    title = validate_title(title)
    category = validate_category(category)
    urgency = validate_urgency(urgency)
    affected_users = validate_affected_users(affected_users)

    priority = calculate_priority(urgency, affected_users)
    ticket_id = generate_ticket_id(ticket_number)

    ticket = {
        "id": ticket_id,
        "title": title,
        "category": category,
        "urgency": urgency,
        "affected_users": affected_users,
        "priority": priority,
        "status": "open",
        "assigned_to": None,
    }

    return ticket