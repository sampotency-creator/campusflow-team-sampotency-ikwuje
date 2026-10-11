"""Main entry point for the CampusFlow Help Desk application."""

import re

from campusflow.tickets import get_ticket_input
from campusflow.workflow import (
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


def get_ticket_number(tickets):
    """Get the next ticket number as an integer.

    Supports next_ticket_id() returning either an integer,
    such as 1, or a formatted ID, such as T001.
    """

    next_id = next_ticket_id(tickets)

    # Case 1: The workflow returns an integer.
    if isinstance(next_id, int) and not isinstance(next_id, bool):
        if next_id <= 0:
            raise ValueError("The next ticket number must be positive.")

        return next_id

    # Case 2: The workflow returns a formatted ticket ID, such as T001.
    if isinstance(next_id, str):
        match = re.fullmatch(r"T(\d+)", next_id.strip(), re.IGNORECASE)

        if match:
            number = int(match.group(1))

            if number > 0:
                return number

    raise ValueError(
        f"Invalid ticket number returned by workflow: {next_id!r}"
    )


def create_new_ticket(tickets):
    """Create a ticket and save it to the shared ticket collection."""

    print("\n--- CREATE NEW TICKET ---")

    # Obtain the numeric ticket number expected by tickets.py.
    try:
        ticket_number = get_ticket_number(tickets)

    except ValueError as error:
        print(f"Could not generate ticket ID: {error}")
        return

    # Collect the ticket details and create the ticket.
    ticket = get_ticket_input(ticket_number)

    # If validation fails, get_ticket_input returns None.
    if ticket is None:
        return

    # Add the new ticket to the shared collection.
    tickets.append(ticket)

    # Save the updated collection.
    try:
        save_tickets(tickets)

        print("\nTicket saved successfully.")
        print(f"Generated ticket ID: {ticket['id']}")

    except StorageError as error:
        # Remove the ticket from memory if saving fails.
        tickets.pop()

        print(f"Could not save ticket: {error}")
        print("The new ticket was removed from memory.")


def assign_existing_ticket(tickets):
    """Assign an existing ticket to a staff member."""

    ticket_id = input("Enter ticket ID: ").strip()
    staff_name = input("Enter staff name: ").strip()

    try:
        assign_ticket(tickets, ticket_id, staff_name)
        save_tickets(tickets)

        print("Ticket assigned and saved successfully.")

    except (StorageError, ValueError) as error:
        print(f"Could not save the assignment: {error}")


def update_ticket_status(tickets):
    """Change the status of an existing ticket."""

    ticket_id = input("Enter ticket ID: ").strip()

    new_status = input(
        "Enter new status (open/in_progress/resolved): "
    ).strip().lower()

    try:
        change_ticket_status(tickets, ticket_id, new_status)
        save_tickets(tickets)

        print("Ticket status updated and saved successfully.")

    except (StorageError, ValueError) as error:
        print(f"Could not save the status change: {error}")


def reopen_existing_ticket(tickets):
    """Reopen a resolved ticket."""

    ticket_id = input("Enter ticket ID to reopen: ").strip()

    try:
        reopen_ticket(tickets, ticket_id)
        save_tickets(tickets)

        print("Ticket reopened and saved successfully.")

    except (StorageError, ValueError) as error:
        print(f"Could not save the reopening: {error}")


def view_one_ticket(tickets):
    """Display one ticket selected by its ID."""

    ticket_id = input("Enter ticket ID: ").strip()

    display_one_ticket(tickets, ticket_id)


def display_menu():
    """Display the main CampusFlow menu."""

    print("\n" + "=" * 42)
    print("          CAMPUSFLOW HELP DESK")
    print("=" * 42)

    print("1. Create ticket")
    print("2. Assign ticket")
    print("3. Change ticket status")
    print("4. Reopen resolved ticket")
    print("5. Display work queue")
    print("6. Display report")
    print("7. List all tickets")
    print("8. View one ticket")
    print("9. Exit")

    print("=" * 42)


def main():
    """Load saved tickets and run the application menu."""

    # Load existing tickets before displaying the menu.
    try:
        tickets = load_tickets()

    except StorageError as error:
        print(f"ERROR: {error}")
        print("CampusFlow stopped to protect saved ticket data.")
        return

    print(
        f"Welcome to CampusFlow! Loaded {len(tickets)} ticket(s)."
    )

    # Keep running until the user chooses Exit.
    while True:
        display_menu()

        choice = input("Choose an option (1-9): ").strip()

        if choice == "1":
            create_new_ticket(tickets)

        elif choice == "2":
            assign_existing_ticket(tickets)

        elif choice == "3":
            update_ticket_status(tickets)

        elif choice == "4":
            reopen_existing_ticket(tickets)

        elif choice == "5":
            display_work_queue(tickets)

        elif choice == "6":
            display_report(tickets)

        elif choice == "7":
            display_all_tickets(tickets)

        elif choice == "8":
            view_one_ticket(tickets)

        elif choice == "9":
            print("Thank you for using CampusFlow. Goodbye!")
            break

        else:
            print("Invalid option. Please choose a number from 1 to 9.")


if __name__ == "__main__":
    main()