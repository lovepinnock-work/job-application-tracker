# Data Model

## Applications

One row per application

Tracks:

- company
- role
- status
- applied date
- updated date
- interview date
- assessment date
- offer due date
- application identity key

## Events

One row per event.

Examples:
- assessment invite
- interview invitation
- offer deadline

## EventApplications

A join table linking events to one or more applications.

This supports scenarios like:
- one shared assessment tied to multiple applications
- multiple events tied to the same application

## ReviewQueue

A human-in-the-loop fallback for ambiguous cases.

If an email cannot be matched confidently, it is routed here rather than risking an incorrect update.
