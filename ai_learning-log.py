# AI Learning Log

#15/10/2026

# Entry 1: Understanding sla.py

- Task: Understand what sla.py does and what SLA_HOURS and warn minutes mean.
- AI used: Claude 
- What I asked: Explain the function, the problems it handles, and whether warn minutes should match SLA hours.

- What I learned: SLA hours give each priority a deadline (due = created + SLA).

  warn_minutes is a lead time (warn me when due within N minutes), not the SLA.

- What the AI got wrong:Its first answer treated warn_minutes as time elapsed

  since creation. After seeing the code, it corrected itself.
  
- How I checked: Read the code and traced the comparison due > now + window.


# Entry 2: Fixing failing tests

- Task: Make test_sla.py pass.

- *What I learned:* Tests assumed SLA 4/8/24/72 but sla.py has 1/4/24/48.

  I chose to change the tests (not sla.py) because [your reason].

- Change: Updated ticket ages in the fixture and expected average age (510 → 390).

- How I checked:** Ran python3 -m unittest discover -s tests -v ; all test_sla tests passed.

## Entry 3: Rejecting a suggested change

- AI suggestion: Sort oldest ticket first, add assignee queues.

- What I found: Oldest-first lets an old low-priority ticket outrank a

  critical ticket. The AI also admitted its first idea (created_at tiebreaker)

  would never run, since same due time + same priority means same created_at.

- My decision: I Keep the current sort (overdue, due time, priority, ID).

- Why: It balances age and priority through the deadline.

## Entry 4: Git and unittest

- *Learned:  python3 pytest is wrong; python3 -m unittest discover -s tests -v works

  without installing anything. -s sets the start folder, -v shows each test.

- *Learned: Feature branch → commit → push → pull request.

- *Limitation:* test_tickets.py needs pytest, which I can't install on my managed device.

# What I would do differently / still unsure about

- [willing to inport django, and buit dashboards for staff, technians and fellows/learners, i want campusflow to be runing onserver not just Command line]