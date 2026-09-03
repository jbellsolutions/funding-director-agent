---
name: provider-onboarding
description: Convert current provider-controlled evidence into a reviewable Product Card and submission destination without inventing box rules.
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    category: funding
    tags: [provider, product-card, lender-matrix, activation]
---

# Provider Onboarding

Use this when the founder or relationship manager supplies a current provider
guide, rate sheet, portal, written confirmation, or recorded provider training.
Public marketing pages are discovery evidence only.

## Procedure

1. Identify the provider, exact program, source owner, effective date, expiry or
   re-verification date, and the private source reference.
2. Extract only explicit rules: amounts, state and industry availability,
   revenue, time in business, ownership, credit, bank-behavior limits,
   collateral, documents, stacking policy, and submission method.
3. Preserve ambiguous, conditional, or missing rules as unknown. Ask the
   relationship manager internally; do not infer them from a similar provider.
4. Draft one Product Card from `product-card.example.json` with status
   `verified`, never `active`.
5. Draft one destination from `destination.example.json`. For an API route,
   require HTTPS, a dedicated credential environment variable, an idempotency
   contract, and a receipt field. For a portal, record a reviewed browser
   playbook and receipt-verification step in private knowledge.
6. Run `scripts/validate_funding_config.py` against the proposed catalogs.
7. Present a compact activation review: source, rules, exclusions, documents,
   destination, receipt, expiry, contradictions, and unknowns.
8. Only the human owner may change both records to `active`. Record who
   approved, when, and the next review date in private evidence.

## Non-negotiable controls

- Never treat Biz Funding Depot, another broker's site, a classroom summary, or
  an old deal as current provider underwriting authority.
- Never store a portal password, API key, bank data, SSN, or customer document
  in a Product Card or Git.
- A live card without current provider evidence and a matching live destination
  is a configuration error.
- Pause the Product Card immediately when the provider changes its rules or the
  evidence expires.
