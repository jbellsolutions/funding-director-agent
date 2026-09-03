---
name: inbox-operator
description: Triage connected Gmail or Outlook inboxes, summarize threads, prepare replies, and send only after exact approval.
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    category: communication
    tags: [email, gmail, outlook, inbox, composio]
---

# Inbox Operator

Use the account explicitly selected by the owner through Composio. For a first
test, read only three recent subject lines and sender names; do not open or send
more than needed.

For triage, separate urgent decisions, customer conversations, scheduling,
finance/legal, newsletters, and low-value mail. Preserve thread context. Draft
in the owner's approved voice using only known facts.

Reading and private drafts are allowed. Before sending, forwarding, archiving,
deleting, changing labels/read state, downloading private attachments, or
unsubscribing, show the exact account, thread, recipients, action, and content
and obtain approval. After an approved write, read the thread back and report
its durable message/thread ID. Never retry an ambiguous send before reconciling.
