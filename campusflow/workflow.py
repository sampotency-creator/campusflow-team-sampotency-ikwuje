"""CampusFlow ticket workflow, reporting, and JSON persistence."""

import json
import re
from pathlib import Path

from campusflow.history import (
    HistoryError,
    create_event,
    load_events,
    save_events,
    display_ticket_history,
)

# --------------------------------------------------
# FILE LOCATION AND CONSTANTS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STORAGE_FILE = PROJECT_ROOT / "tickets.json"

REQUIRED_FIELDS = {
    "id",
    "title",
    "category",
    "urgency",
    "affected_users",
    "priority",
    "status",
    "assigned_to",
}

VALID_STATUSES = {"open", "in_progress", "resolved"}

VALID_PRIORITIES = {"critical", "high", "medium", "low"}

PRIORITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


class StorageError(Exception):
    """Raised when ticket data cannot safely be loaded or saved."""



def _prepare_operation_event(
    events,
    ticket_id,
    action,
    actor,
    details,
):

    """Prepare an event before mutating a ticket."""

    if events is None:
        return None

    if not isinstance(events, list):
        raise ValueError("Event history must be a list.")

    return create_event(
        ticket_id=ticket_id,
        action=action,
        actor=actor,
        details=details,
    )


def _append_operation_event(events, event):
    """Append an already-prepared event after an operation succeeds."""

    if events is not None and event is not None:
        events.append(event)


# --------------------------------------------------
# TICKET VALIDATION
# --------------------------------------------------

def is_valid_ticket(ticket):
    """Return True if a ticket has all required fields and valid values."""

    if not isinstance(ticket, dict):
        return False

    if not REQUIRED_FIELDS.issubset(ticket.keys()):
        return False

    # These fields must contain non-empty strings.
    string_fields = (
        "id",
        "title",
        "category",
        "urgency",
        "priority",
        "status",
    )

    for field in string_fields:
        value = ticket[field]

        if not isinstance(value, str) or not value.strip():
            return False

    # Ticket IDs must look like T001, T002, T10, etc.
    if re.fullmatch(r"T\d+", ticket["id"], flags=re.IGNORECASE) is None:
        return False

    # bool is a subclass of int in Python, so reject it explicitly.
    affected_users = ticket["affected_users"]

    if (
        not isinstance(affected_users, int)
        or isinstance(affected_users, bool)
        or affected_users < 0
    ):
        return False

    if ticket["status"] not in VALID_STATUSES:
        return False

    if ticket["priority"] not in VALID_PRIORITIES:
        return False

    assigned_to = ticket["assigned_to"]

    if assigned_to is not None:
        if not isinstance(assigned_to, str) or not assigned_to.strip():
            return False

    return True


def validate_ticket_collection(tickets):
    """Validate a list of tickets and reject duplicate IDs."""

    if not isinstance(tickets, list):
        raise ValueError("Ticket data must be a list.")

    seen_ids = set()

    for ticket in tickets:
        if not is_valid_ticket(ticket):
            raise ValueError(
                f"Invalid ticket data: {ticket!r}"
            )

        ticket_id = ticket["id"].upper()

        if ticket_id in seen_ids:
            raise ValueError(
                f"Duplicate ticket ID found: {ticket['id']}"
            )

        seen_ids.add(ticket_id)

    return True


# --------------------------------------------------
# FINDING TICKETS
# --------------------------------------------------

def find_ticket(tickets, ticket_id):
    """Find a ticket by ID, ignoring the ID's letter case."""

    if not isinstance(ticket_id, str):
        return None

    wanted_id = ticket_id.strip().upper()

    for ticket in tickets:
        if ticket["id"].upper() == wanted_id:
            return ticket

    return None


# --------------------------------------------------
# F3 - ASSIGN TICKETS
# --------------------------------------------------

def assign_ticket(
    tickets,
    ticket_id,
    staff_name,
    events=None,
    actor="system",
):
    """
    Assign a ticket to a staff member.

    Return True on success and False on failure.

    When events is provided, record the successful assignment.
    """

    ticket = find_ticket(tickets, ticket_id)

    if ticket is None:
        return False

    if not is_valid_ticket(ticket):
        return False

    if not isinstance(staff_name, str) or not staff_name.strip():
        return False

    new_assignee = staff_name.strip()

    event = _prepare_operation_event(
        events=events,
        ticket_id=ticket["id"],
        action="TICKET_ASSIGNED",
        actor=actor,
        details={
            "previous_assignee": ticket["assigned_to"],
            "assigned_to": new_assignee,
        },
    )

    ticket["assigned_to"] = new_assignee

    _append_operation_event(events, event)

    return True


# --------------------------------------------------
# F4 - CHANGE TICKET STATUS
# --------------------------------------------------

def change_ticket_status(
    tickets,
    ticket_id,
    new_status,
    events=None,
    actor="system",
):

    """
    Change status only when the transition is permitted.

    Allowed transitions:
        open -> in_progress, when assigned
        in_progress -> resolved

    A resolved ticket must be reopened before work starts again.
    """

    ticket = find_ticket(tickets, ticket_id)

    if ticket is None:
        return False

    if not is_valid_ticket(ticket):
        return False

    if not isinstance(new_status, str):
        return False

    new_status = new_status.strip()

    if new_status not in VALID_STATUSES:
        return False

    current_status = ticket["status"]


    # An open ticket can start work only if it is assigned.


    if current_status == "open" and new_status == "in_progress":
        assigned_to = ticket["assigned_to"]

        if not isinstance(assigned_to, str) or not assigned_to.strip():
            return False

        event = _prepare_operation_event(
            events=events,
            ticket_id=ticket["id"],
            action="STATUS_CHANGED",
            actor=actor,
            details={
                "from": current_status,
                "to": new_status,
            },
        )

        ticket["status"] = new_status

        _append_operation_event(events, event)

        return True

    # Only an in-progress ticket can be resolved.

    if current_status == "in_progress" and new_status == "resolved":
        event = _prepare_operation_event(
            events=events,
            ticket_id=ticket["id"],
            action="STATUS_CHANGED",
            actor=actor,
            details={
                "from": current_status,
                "to": new_status,
            },
        )

        ticket["status"] = new_status

        _append_operation_event(events, event)

        return True

    # Reject every other transition.

    return False


def reopen_ticket(
    tickets,
    ticket_id,
    events=None,
    actor="system",
):
    """Reopen a resolved ticket and record the successful operation."""

    ticket = find_ticket(tickets, ticket_id)

    if ticket is None:
        return False

    if not is_valid_ticket(ticket):
        return False

    if ticket["status"] != "resolved":
        return False

    event = _prepare_operation_event(
        events=events,
        ticket_id=ticket["id"],
        action="TICKET_REOPENED",
        actor=actor,
        details={
            "from": "resolved",
            "to": "open",
        },
    )

    ticket["status"] = "open"

    _append_operation_event(events, event)

    return True

# --------------------------------------------------
# F5 - WORK QUEUE
# --------------------------------------------------

def _numeric_ticket_id(ticket):
    """Return the numeric part of a ticket ID for sorting."""

    match = re.fullmatch(
        r"T(\d+)",
        ticket["id"],
        flags=re.IGNORECASE,
    )

    return int(match.group(1))


def get_work_queue(tickets):
    """
    Return unresolved tickets sorted by priority and numeric ticket ID.

    Priority order:
        critical -> high -> medium -> low

    Tickets with the same priority are ordered by their numeric IDs.
    Only open and in-progress tickets appear in the queue.
    """

    queue = [
        ticket
        for ticket in tickets
        if (
            ticket.get("status") in {"open", "in_progress"}
            and is_valid_ticket(ticket)
        )
    ]

    queue.sort(
        key=lambda ticket: (
            PRIORITY_ORDER[ticket["priority"]],
            _numeric_ticket_id(ticket),
        )
    )

    return queue


def display_work_queue(tickets):
    """Print the work queue."""

    queue = get_work_queue(tickets)

    print("\n========== CAMPUSFLOW WORK QUEUE ==========")

    if not queue:
        print("No open or in-progress tickets.")
        return

    for ticket in queue:
        print(
            f"\nID: {ticket['id']}"
            f"\nTitle: {ticket['title']}"
            f"\nPriority: {ticket['priority']}"
            f"\nStatus: {ticket['status']}"
            f"\nAssigned to: {ticket['assigned_to'] or 'Unassigned'}"
        )

    print("\n===========================================")


# --------------------------------------------------
# F6 - REPORTS
# --------------------------------------------------

def generate_report(tickets):
    """
    Generate ticket totals and status/priority breakdowns.

    Empty ticket collections produce zero counts.
    """

    report = {
        "total_tickets": len(tickets),
        "status_counts": {
            "open": 0,
            "in_progress": 0,
            "resolved": 0,
        },
        "priority_counts": {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        },
        "assigned_tickets": 0,
        "unassigned_tickets": 0,
    }

    for ticket in tickets:
        if not is_valid_ticket(ticket):
            continue

        report["status_counts"][ticket["status"]] += 1
        report["priority_counts"][ticket["priority"]] += 1

        if ticket["assigned_to"] is None:
            report["unassigned_tickets"] += 1
        else:
            report["assigned_tickets"] += 1

    return report


def display_report(tickets):
    """Print the ticket report."""

    report = generate_report(tickets)

    print("\n========== CAMPUSFLOW REPORT ==========")

    print(f"Total tickets: {report['total_tickets']}")

    print("\nTickets by status:")
    for status, count in report["status_counts"].items():
        print(f"  {status}: {count}")

    print("\nTickets by priority:")
    for priority, count in report["priority_counts"].items():
        print(f"  {priority}: {count}")

    print("\nAssignment:")
    print(f"  Assigned: {report['assigned_tickets']}")
    print(f"  Unassigned: {report['unassigned_tickets']}")

    print("=======================================")


# --------------------------------------------------
# F7 - LOAD TICKETS FROM JSON
# --------------------------------------------------

def load_tickets(path=DEFAULT_STORAGE_FILE):
    """
    Load tickets from a JSON file.

    If the file does not exist, return an empty list.
    If the JSON or ticket data is invalid, raise StorageError.
    """

    path = Path(path)

    if not path.exists():
        return []

    try:
        with path.open("r", encoding="utf-8") as file:
            tickets = json.load(file)

    except json.JSONDecodeError as error:
        raise StorageError(
            f"Malformed JSON in '{path}': {error}"
        ) from error

    except OSError as error:
        raise StorageError(
            f"Could not read '{path}': {error}"
        ) from error

    try:
        validate_ticket_collection(tickets)

    except ValueError as error:
        raise StorageError(
            f"Invalid ticket data in '{path}': {error}"
        ) from error

    return tickets


# --------------------------------------------------
# F7 - SAVE TICKETS TO JSON
# --------------------------------------------------

def save_tickets(tickets, path=DEFAULT_STORAGE_FILE):
    """
    Save tickets to JSON after validating the collection.

    A temporary file is written first so an incomplete write is less
    likely to replace the existing saved data.
    """

    path = Path(path)

    try:
        validate_ticket_collection(tickets)

    except ValueError as error:
        raise StorageError(
            f"Cannot save tickets: {error}"
        ) from error

    temporary_path = path.with_name(path.name + ".tmp")

    try:
        # Ensure the destination directory exists.
        path.parent.mkdir(parents=True, exist_ok=True)

        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(tickets, file, indent=4)
            file.write("\n")

        # Replace the old file only after writing the temporary file.
        temporary_path.replace(path)

    except (OSError, TypeError, ValueError) as error:
        # Clean up a temporary file if the write or replacement fails.
        try:
            if temporary_path.exists():
                temporary_path.unlink()
        except OSError:
            pass

        raise StorageError(
            f"Could not save tickets to '{path}': {error}"
        ) from error


# --------------------------------------------------
# GENERATE THE NEXT TICKET ID
# --------------------------------------------------

def next_ticket_id(tickets):
    """
    Generate the next ID from the highest existing numeric ticket ID.

    Examples:
        [] -> T001
        [T001, T002, T007] -> T008
    """

    highest_number = 0

    for ticket in tickets:
        ticket_id = ticket.get("id", "")

        if not isinstance(ticket_id, str):
            continue

        match = re.fullmatch(
            r"T(\d+)",
            ticket_id,
            flags=re.IGNORECASE,
        )

        if match:
            highest_number = max(
                highest_number,
                int(match.group(1)),
            )

    return f"T{highest_number + 1:03d}"


# --------------------------------------------------
# DISPLAY ALL TICKETS
# --------------------------------------------------

def display_all_tickets(tickets):
    """Print every ticket and its details."""

    print("\n========== ALL CAMPUSFLOW TICKETS ==========")

    if not tickets:
        print("No tickets have been created.")
        return

    for ticket in tickets:
        print(
            f"\nID: {ticket['id']}"
            f"\nTitle: {ticket['title']}"
            f"\nCategory: {ticket['category']}"
            f"\nUrgency: {ticket['urgency']}"
            f"\nAffected users: {ticket['affected_users']}"
            f"\nPriority: {ticket['priority']}"
            f"\nStatus: {ticket['status']}"
            f"\nAssigned to: {ticket['assigned_to'] or 'Unassigned'}"
        )

    print("\n============================================")


def display_one_ticket(tickets, ticket_id):
    """Print the details of one ticket. Return True if found."""

    ticket = find_ticket(tickets, ticket_id)

    if ticket is None:
        print("Ticket not found.")
        return False

    display_all_tickets([ticket])
    return True


# --------------------------------------------------
# INTERACTIVE WORKFLOW MENU
# --------------------------------------------------

def run_workflow():
    """Start the interactive CampusFlow workflow menu."""

    try:
        tickets = load_tickets()
    except StorageError as error:
        print(f"ERROR: {error}")
        print("CampusFlow stopped to protect the saved ticket data.")
        return

    print(f"Loaded {len(tickets)} ticket(s).")

    while True:
        print("\n========== CAMPUSFLOW WORKFLOW ==========")
        print("1. Assign ticket")
        print("2. Change ticket status")
        print("3. Reopen resolved ticket")
        print("4. Display work queue")
        print("5. Display report")
        print("6. List all tickets")
        print("7. View one ticket")
        print("8. Exit")
        print("=========================================")

        choice = input("Choose an option (1-8): ").strip()

        if choice == "1":
            ticket_id = input("Enter ticket ID: ").strip()
            staff_name = input("Enter staff member name: ")

            if assign_ticket(tickets, ticket_id, staff_name):
                try:
                    save_tickets(tickets)
                    print("Ticket assigned and saved successfully.")
                except StorageError as error:
                    print(f"ERROR saving tickets: {error}")
            else:
                print("Assignment failed. Check the ticket ID and staff name.")

        elif choice == "2":
            ticket_id = input("Enter ticket ID: ").strip()
            new_status = input(
                "Enter new status (in_progress/resolved): "
            ).strip()

            if change_ticket_status(tickets, ticket_id, new_status):
                try:
                    save_tickets(tickets)
                    print("Ticket status changed and saved successfully.")
                except StorageError as error:
                    print(f"ERROR saving tickets: {error}")
            else:
                print(
                    "Status change rejected. Check the ticket ID, "
                    "assignment, and allowed workflow transitions."
                )

        elif choice == "3":
            ticket_id = input(
                "Enter the resolved ticket ID to reopen: "
            ).strip()

            if reopen_ticket(tickets, ticket_id):
                try:
                    save_tickets(tickets)
                    print("Ticket reopened and saved successfully.")
                except StorageError as error:
                    print(f"ERROR saving tickets: {error}")
            else:
                print("Reopening failed. The ticket must exist and be resolved.")

        elif choice == "4":
            display_work_queue(tickets)

        elif choice == "5":
            display_report(tickets)

        elif choice == "6":
            display_all_tickets(tickets)

        elif choice == "7":
            ticket_id = input("Enter ticket ID to view: ").strip()
            display_one_ticket(tickets, ticket_id)

        elif choice == "8":
            try:
                save_tickets(tickets)
                print("Tickets saved. Goodbye!")
            except StorageError as error:
                print(f"ERROR saving tickets: {error}")
                print("Please resolve the storage problem before exiting.")
                continue

            break

        else:
            print("Invalid option. Please enter a number from 1 to 8.")


if __name__ == "__main__":
    run_workflow()