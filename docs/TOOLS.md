# Funding Director tools

## Funding core

The trusted local core owns durable cases, state transitions, Product Card
matching, offer comparison, submission packets, one-time approvals, receipts,
GoHighLevel write approvals, audit events, and emergency-stop enforcement. It
contains no provider credentials and uses Python's standard library plus the
Hermes MCP runtime.

The two functions that create approval records are excluded from the full-trust
core toolset and exposed only by a second `untrusted` MCP entry. Hermes manual
mode therefore asks the human before either approval is recorded. Execution
then consumes that exact approval once.

## Funding Machine

The documented Funding Machine MCP/API is read-only. It can list locations,
search contacts, read stored credit summaries and redacted reports, read stored
underwriting results, funding plans, stages, next steps, pipeline contacts, and
dashboard statistics. It must never be represented as initiating a credit pull
or new underwriting run.

## GoHighLevel

The local client exposes narrow location-scoped reads for contacts,
opportunities, and pipelines. The only write operations are add tags, create an
internal note, and update an allowlisted set of opportunity fields. Every write
is frozen and approved once before execution. Broad agency credentials,
Firebase tokens, delete actions, payments, campaigns, and bulk operations are
not exposed.

## Submission routes

`destinations.json` is empty by default. A real route must be explicitly added
with its product allowlist, adapter, HTTPS endpoint or reviewed browser
playbook, authentication environment variable, and receipt field. An uncertain
result consumes the approval and requires manual reconciliation; it is never
automatically retried.

## Supporting tools

Hermes supplies document/PDF/spreadsheet analysis, web research, browser use,
Slack/Telegram, Kanban, memory, and bounded delegation. Composio can optionally
connect calendar, inbox, and files. A connection is capability, not permission;
begin with read-only proof and follow `policies/permissions.json`.
