"""CampusFlow append-only ticket event history."""

import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HISTORY_FILE = PROJECT_ROOT / "events.json"

REQUIRED_EVENT_FIELDS = {
    "ticket_id",
    "action",
    "actor",
    "timestamp",
    "details",
}


class HistoryError(Exception):
    """Raised when event history cannot safely be loaded or saved."""




def create_event(ticket_id, action, actor="system", details=None):
    """Create and return a validated event without storing it."""

    if not isinstance(ticket_id, str) or not ticket_id.strip():
        raise ValueError("Event ticket ID must be non-empty text.")

    if not isinstance(action, str) or not action.strip():
        raise ValueError("Event action must be non-empty text.")

    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("Event actor must be non-empty text.")

    if details is None:
        details = {}

    if not isinstance(details, dict):
        raise ValueError("Event details must be a dictionary.")

    timestamp = (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )

    return {
        "ticket_id": ticket_id.strip().upper(),
        "action": action.strip().upper(),
        "actor": actor.strip(),
        "timestamp": timestamp,
        "details": dict(details),
    }


def record_event(events, ticket_id, action, actor="system", details=None):
    """Append one event to the in-memory history."""

    if not isinstance(events, list):
        raise ValueError("Event history must be a list.")

    event = create_event(
        ticket_id=ticket_id,
        action=action,
        actor=actor,
        details=details,
    )

    events.append(event)

    return event




def validate_event_collection(events):
    """Reject invalid event collections before saving or using them."""

    if not isinstance(events, list):
        raise ValueError("Event history must be a list.")

    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValueError(
                f"Event at position {index} must be a dictionary."
            )

        if not REQUIRED_EVENT_FIELDS.issubset(event.keys()):
            raise ValueError(
                f"Event at position {index} is missing required fields."
            )

        for field in ("ticket_id", "action", "actor", "timestamp"):
            value = event[field]

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Event field '{field}' must contain non-empty text."
                )

        if not isinstance(event["details"], dict):
            raise ValueError(
                f"Event details at position {index} must be a dictionary."
            )

        try:
            parsed_timestamp = datetime.fromisoformat(
                event["timestamp"].replace("Z", "+00:00")
            )
        except ValueError as error:
            raise ValueError(
                f"Event at position {index} has an invalid timestamp."
            ) from error

        if parsed_timestamp.tzinfo is None:
            raise ValueError(
                f"Event at position {index} must use a timezone-aware timestamp."
            )

    return True



def load_events(path=DEFAULT_HISTORY_FILE):
    """Load saved events; return an empty list if no file exists."""

    path = Path(path)

    if not path.exists():
        return []

    try:
        with path.open("r", encoding="utf-8") as file:
            events = json.load(file)

    except json.JSONDecodeError as error:
        raise HistoryError(
            f"Malformed event-history JSON in '{path}': {error}"
        ) from error

    except OSError as error:
        raise HistoryError(
            f"Could not read event history from '{path}': {error}"
        ) from error

    try:
        validate_event_collection(events)

    except ValueError as error:
        raise HistoryError(
            f"Invalid event history in '{path}': {error}"
        ) from error

    return events



def save_events(events, path=DEFAULT_HISTORY_FILE):
    """Validate and save events using a temporary file."""

    path = Path(path)

    try:
        validate_event_collection(events)

    except ValueError as error:
        raise HistoryError(
            f"Cannot save event history: {error}"
        ) from error

    temporary_path = path.with_name(path.name + ".tmp")

    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(events, file, indent=4)
            file.write("\n")

        temporary_path.replace(path)

    except (OSError, TypeError, ValueError) as error:
        try:
            if temporary_path.exists():
                temporary_path.unlink()
        except OSError:
            pass

        raise HistoryError(
            f"Could not save event history to '{path}': {error}"
        ) from error



def get_ticket_history(events, ticket_id):
    """Return events belonging to one ticket, in recorded order."""

    if not isinstance(ticket_id, str):
        return []

    wanted_id = ticket_id.strip().upper()

    if not wanted_id:
        return []

    return [
        event
        for event in events
        if event.get("ticket_id", "").upper() == wanted_id
    ]


def display_ticket_history(events, ticket_id):
    """Display a ticket's event history."""

    history = get_ticket_history(events, ticket_id)

    print(f"\n========== HISTORY: {ticket_id.strip().upper()} ==========")

    if not history:
        print("No history events found for this ticket.")
        print("================================================")
        return

    for number, event in enumerate(history, start=1):
        print(f"\n{number}. {event['action']}")
        print(f"   Timestamp: {event['timestamp']}")
        print(f"   Actor: {event['actor']}")

        if event["details"]:
            print(
                "   Details: "
                + json.dumps(event["details"], ensure_ascii=False)
            )

    print("\n================================================")