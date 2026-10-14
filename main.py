"""Main entry point for the CampusFlow Help Desk application."""

import re
from datetime import datetime, timezone
from pathlib import Path

from campusflow.cli_input import ask_choice, confirm
from campusflow.duplicates import detect_duplicates
from campusflow.history import (
    HistoryError,
    display_ticket_history,
    load_events,
    record_event,
    save_events,
)
from campusflow.knowledge_lab import run_lab
from campusflow.sla import display_sla_queue
from campusflow.tickets import get_ticket_input
from campusflow.workflow import (
    DEFAULT_STORAGE_FILE,
    PROJECT_ROOT,
    StorageError,
    assign_ticket,
    change_ticket_status,
    display_all_tickets,
    display_one_ticket,
    display_report,
    display_work_queue,
    load_tickets,
    next_ticket_id,
    reopen_ticket,
    save_tickets,
)

HISTORY_FILE = PROJECT_ROOT / "events.json"
DEFAULT_ACTOR = "cli-user"


def get_ticket_number(tickets):
    """Get the next ticket number as an integer.

    Supports next_ticket_id() returning either an integer,
    such as 1, or a formatted ID, such as T001.
    """

    next_id = next_ticket_id(tickets)

    if isinstance(next_id, int) and not isinstance(next_id, bool):
        if next_id <= 0:
            raise ValueError("The next ticket number must be positive.")

        return next_id

    if isinstance(next_id, str):
        match = re.fullmatch(r"T(\d+)", next_id.strip(), re.IGNORECASE)

        if match:
            number = int(match.group(1))

            if number > 0:
                return number

    raise ValueError(
        f"Invalid ticket number returned by workflow: {next_id!r}"
    )


def persist(tickets, events, tickets_path=DEFAULT_STORAGE_FILE, events_path=HISTORY_FILE):
    """Save tickets and history together."""

    save_tickets(tickets, tickets_path)
    save_events(events, events_path)


def create_new_ticket(
    tickets,
    events,
    input_fn=input,
    tickets_path=DEFAULT_STORAGE_FILE,
    events_path=HISTORY_FILE,
):
    """Create a ticket, warn on duplicates, record history, then save."""

    print("\n--- CREATE NEW TICKET ---")

    try:
        ticket_number = get_ticket_number(tickets)
    except ValueError as error:
        print(f"Could not generate ticket ID: {error}")
        return False

    ticket = get_ticket_input(ticket_number)

    if ticket is None:
        return False

    duplicates = detect_duplicates(ticket["category"], ticket["title"], tickets)

    if duplicates:
        print("\nWARNING: this looks like an unresolved ticket already in the system:")

        for match in duplicates:
            print(f"  {match['id']}: {match['title']} [{match['status']}]")

        if not confirm("Create this ticket anyway?", input_fn):
            print("Ticket not created.")
            return False

    ticket.setdefault("created_at", datetime.now(timezone.utc).isoformat())

    tickets.append(ticket)
    event_count = len(events)

    try:
        record_event(
            events,
            ticket["id"],
            "TICKET_CREATED",
            DEFAULT_ACTOR,
            {"status": ticket["status"]},
        )
        persist(tickets, events, tickets_path, events_path)

    except (StorageError, HistoryError, ValueError) as error:
        tickets.pop()
        del events[event_count:]

        print(f"Could not save ticket: {error}")
        print("The new ticket was removed from memory.")
        return False

    print("\nTicket saved successfully.")
    print(f"Generated ticket ID: {ticket['id']}")
    return True


def run_ticket_operation(
    operation,
    tickets,
    events,
    args,
    success_message,
    failure_message,
    tickets_path=DEFAULT_STORAGE_FILE,
    events_path=HISTORY_FILE,
):
    """Run a workflow operation and only report success if it succeeded."""

    if not operation(tickets, *args, events=events, actor=DEFAULT_ACTOR):
        print(failure_message)
        return False

    try:
        persist(tickets, events, tickets_path, events_path)
    except (StorageError, HistoryError) as error:
        print(f"ERROR saving: {error}")
        return False

    print(success_message)
    return True


def assign_existing_ticket(tickets, events, input_fn=input, **paths):
    ticket_id = input_fn("Enter ticket ID: ").strip()
    staff_name = input_fn("Enter staff name: ").strip()

    return run_ticket_operation(
        assign_ticket, tickets, events, (ticket_id, staff_name),
        "Ticket assigned and saved successfully.",
        "Assignment failed. Check the ticket ID and staff name.",
        **paths,
    )


def update_ticket_status(tickets, events, input_fn=input, **paths):
    ticket_id = input_fn("Enter ticket ID: ").strip()
    new_status = input_fn(
        "Enter new status (in_progress/resolved): "
    ).strip().lower()

    return run_ticket_operation(
        change_ticket_status, tickets, events, (ticket_id, new_status),
        "Ticket status updated and saved successfully.",
        "Status change rejected. Check the ticket ID, assignment, "
        "and allowed workflow transitions.",
        **paths,
    )


def reopen_existing_ticket(tickets, events, input_fn=input, **paths):
    ticket_id = input_fn("Enter ticket ID to reopen: ").strip()

    return run_ticket_operation(
        reopen_ticket, tickets, events, (ticket_id,),
        "Ticket reopened and saved successfully.",
        "Reopening failed. The ticket must exist and be resolved.",
        **paths,
    )


def view_one_ticket(tickets, input_fn=input):
    display_one_ticket(tickets, input_fn("Enter ticket ID: ").strip())


def view_ticket_history(events, input_fn=input):
    display_ticket_history(events, input_fn("Enter ticket ID: ").strip())


MENU = [
    ("1", "Create ticket"),
    ("2", "Assign ticket"),
    ("3", "Change ticket status"),
    ("4", "Reopen resolved ticket"),
    ("5", "Display work queue"),
    ("6", "Display SLA attention queue"),
    ("7", "Display report"),
    ("8", "List all tickets"),
    ("9", "View one ticket"),
    ("10", "View ticket history"),
    ("11", "Engineering Knowledge Lab"),
    ("12", "Exit"),
]


def display_menu():
    print("\n" + "=" * 42)
    print("          CAMPUSFLOW HELP DESK")
    print("=" * 42)

    for number, label in MENU:
        print(f"{number}. {label}")

    print("=" * 42)


def main(
    input_fn=input,
    tickets_path=DEFAULT_STORAGE_FILE,
    events_path=HISTORY_FILE,
):
    """Load saved data and run the application menu."""

    try:
        tickets = load_tickets(tickets_path)
        events = load_events(events_path) if Path(events_path).exists() else []

    except (StorageError, HistoryError) as error:
        print(f"ERROR: {error}")
        print("CampusFlow stopped to protect saved data.")
        return

    print(f"Welcome to CampusFlow! Loaded {len(tickets)} ticket(s).")

    paths = {"tickets_path": tickets_path, "events_path": events_path}
    valid_choices = {number for number, _ in MENU}

    while True:
        display_menu()

        choice = ask_choice(
            "Choose an option (1-12): ", valid_choices, input_fn,
            hint="a number from 1 to 12",
        )

        if choice == "1":
            create_new_ticket(tickets, events, input_fn, **paths)
        elif choice == "2":
            assign_existing_ticket(tickets, events, input_fn, **paths)
        elif choice == "3":
            update_ticket_status(tickets, events, input_fn, **paths)
        elif choice == "4":
            reopen_existing_ticket(tickets, events, input_fn, **paths)
        elif choice == "5":
            display_work_queue(tickets)
        elif choice == "6":
            display_sla_queue(tickets)
        elif choice == "7":
            display_report(tickets)
        elif choice == "8":
            display_all_tickets(tickets)
        elif choice == "9":
            view_one_ticket(tickets, input_fn)
        elif choice == "10":
            view_ticket_history(events, input_fn)
        elif choice == "11":
            run_lab(input_fn)
        elif choice == "12":
            print("Thank you for using CampusFlow. Goodbye!")
            break


if __name__ == "__main__":
    main()