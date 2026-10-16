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
    """Check that the ticket title is meaningful text."""

    if not isinstance(title, str):
        raise ValueError("Title must be text.")

    title = title.strip()

    if not title:
        raise ValueError("Title cannot be empty.")

    if not any(character.isalpha() for character in title):
        raise ValueError(
            "Title must contain at least one letter, "
            "for example 'WiFi down in Block B'."
        )

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


def ask_until_valid(prompt, validator, converter=None):
    """Keep asking until the validator accepts the answer."""

    while True:

        answer = input(prompt)

        try:
            if converter is not None:
                answer = converter(answer)

            return validator(answer)

        except ValueError as error:
            print(f"Invalid input: {error} Please try again.\n")


def to_whole_number(text):

    """Convert typed text to an int, with a friendly error."""

    try:
        return int(text.strip())
    except ValueError:
        raise ValueError("Enter a whole number such as 5.") from None



def get_ticket_input(ticket_number):
    """Collect ticket details from the user and create a ticket."""

    title = ask_until_valid(
        "Enter ticket title: ",
        validate_title,
    )
    category = ask_until_valid(
        "Enter category (Network/Hardware/Software/Other): ",
        validate_category,
    )
    urgency = ask_until_valid(
        "Enter urgency (low/medium/high): ",
        validate_urgency,
    )
    affected_users = ask_until_valid(
        "Enter number of affected users: ",
        validate_affected_users,
        converter=to_whole_number,
    )

    ticket = create_ticket(
        title=title,
        category=category,
        urgency=urgency,
        affected_users=affected_users,
        ticket_number=ticket_number,
    )

    print("\nTicket created successfully!")

    for key, value in ticket.items():
        print(f"{key.replace('_', ' ').title()}: {value}")

    return ticket


def create_multiple_tickets():
    """Allow the user to create multiple tickets in one session."""

    tickets = []
    next_ticket_number = 1

    while True:
        ticket = get_ticket_input(next_ticket_number)

        if ticket is not None:
            tickets.append(ticket)
            next_ticket_number += 1

        while True:
            answer = input(
                "\nCreate another ticket? (yes/no): "
            ).strip().lower()

            if answer in {"yes", "no"}:
                break

            print("Please enter yes or no.")

        if answer == "no":
            break

    print("\n--- SESSION SUMMARY ---")
    print(f"Tickets created in this session: {len(tickets)}")

    for ticket in tickets:
        print(
            f"{ticket['id']} | "
            f"{ticket['title']} | "
            f"{ticket['priority']}"
        )

    return tickets


if __name__ == "__main__":
    print("=" * 40)
    print("CAMPUSFLOW HELP DESK")
    print("=" * 40)

    create_multiple_tickets()