---
name: calendar-operator
description: Read, plan, create, move, or cancel business calendar events through the connected Google Calendar or Cal.com account.
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    category: productivity
    tags: [calendar, scheduling, meetings, google-calendar, calcom]
---

# Calendar Operator

Use Composio's Google Calendar tools for the owner's connected calendar. Use
Cal.com only when the request is specifically about booking links or Cal.com.

## Read work

For availability or schedule questions:

1. Confirm the timezone and date range.
2. Read the relevant calendars, not just the default if several are connected.
3. Treat tentative, all-day, travel, and focus events distinctly.
4. Return available windows with timezone labels.

## Calendar writes

Before creating, moving, or cancelling an event, show the exact title, date,
start/end time, timezone, attendees, location/link, and reminders. Obtain
explicit approval for that exact change.

After approval:

1. Re-check availability to avoid a race or duplicate.
2. Perform one write.
3. Read the event back and report its durable event ID or link.
4. If the result is unclear, reconcile before retrying.

Never invite an attendee, overwrite an existing event, or send an update based
only on an inferred timezone or email address.
