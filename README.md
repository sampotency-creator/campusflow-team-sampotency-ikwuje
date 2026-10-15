# CampusFlow

A command-line ticket system for campus IT issues. It creates tickets,
moves them through a workflow, and shows which tickets need attention first.

## Features
- Create, assign, and update tickets (open → in_progress → resolved)
- Duplicate-ticket warning when creating a ticket
- Work queue sorted by priority
- SLA attention queue: overdue and due-soon tickets, plus health metrics
- Knowledge lab quiz

## SLA rules
Each ticket has an optional created_at timestamp. Due time = created_at + SLA hours.

| Priority | SLA |
|---|---|
| critical | 1 hour |
| high | 4 hours |
| medium | 24 hours |
| low | 48 hours |

Tickets are warned about when they are due within 240 minutes.
Tickets without created_at are "untracked" and never appear in the SLA queue.

SLA queue sort order:
1. Overdue before not overdue
2. Earliest due time first
3. Priority (critical first)
4. Numeric ticket ID

## Requirements
- Python 3.12 (no extra packages needed for the main tests)

## Running the program
python3 main.py        

## Running the tests
python3 -m unittest discover -s tests -v

Note: tests/test_tickets.py imports pytest. If pytest is not installed,
that one file reports an import error; all other tests run normally.

## Project structure
campusflow/   application code (workflow.py, sla.py, ...)
tests/ unit tests and helpers.py