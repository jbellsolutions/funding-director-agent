---
name: submission-operator
description: Prepare, approve, execute, verify, and follow up business-funding submissions without guessing fields or duplicating applications.
---

# Submission Operator

1. Require a durable case in `submission_ready`.
2. Require an active Product Card and a named approved destination.
3. Re-run eligibility and required-document checks at preparation time.
4. Require a recorded client-authorization reference and permissible-purpose
   reference. Never treat possession of a document as consent.
5. Build the exact payload from source-backed fields. Missing data blocks.
6. Freeze the payload, destination, product, and evidence into a digest.
7. For approval-required routes, show the exact action and obtain a one-time,
   expiring approval bound to that digest. The approval tool exists only on the
   separate untrusted approval surface, so Hermes must show the human prompt.
8. The initial release always requires one-time approval. A standing-playbook
   schema is reserved for a later audited release and is not active by default.
9. For an HTTP adapter, execute once. For a browser adapter, call
   `funding_submission_begin_browser` first so the approval is consumed before
   the portal changes state; then perform exactly the reviewed playbook once.
10. Record the external receipt and read back the durable result. If the portal
    result is ambiguous, call `funding_submission_mark_unknown`, stop, and
    reconcile manually. Without a
    receipt or explicit verified portal state, report `not verified`.

The skill never accepts an offer, signs an agreement, changes bank instructions,
or claims funding occurred from a submission confirmation alone.
