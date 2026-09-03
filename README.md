<div align="center">

<img src="docs/assets/funding-director-agent.jpg" alt="Funding Director reviewing a guarded business-funding pipeline" width="1000"/>

# Funding Director Agent

### The backend business-funding operator for intake, strategy, submissions, and follow-through.

The founder owns sales, marketing, brand, and relationships. Funding Director
owns file quality, operational pre-underwriting, product strategy, documents,
approved submissions, funder follow-up, offer comparison, pipeline truth, and
outcome learning.

[**Start here →**](START-HERE.md) · [Setup-agent brief](AGENTS.md) ·
[Orgo guide](docs/ORGO-SETUP.md) · [Security](SECURITY.md)

</div>

[![CI](https://github.com/jbellsolutions/funding-director-agent/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jbellsolutions/funding-director-agent/actions/workflows/ci.yml)
[![Hermes](https://img.shields.io/badge/Hermes_Agent-0.21.0-0f766e)](https://github.com/NousResearch/hermes-agent)
[![External writes](https://img.shields.io/badge/external_writes-one--time_approval-d97706)](policies/permissions.json)
[![Secrets](https://img.shields.io/badge/baked_secrets-0-e11d48)](SECURITY.md)

## What it does

| Funding responsibility | Agent behavior |
|---|---|
| File intake | Creates a durable case, inventories documents, finds contradictions, and requests only missing facts |
| Operational underwriting | Analyzes stored credit summaries, business cash flow, debt, collateral, invoices, property, and file risks without pretending to be the lender |
| Product strategy | Routes only through current, active, provider-verified Product Cards; marketing pages remain discovery evidence |
| Submissions | Freezes the exact payload, checks consent and permissible purpose, obtains one-time approval, transmits once, and records a receipt |
| GoHighLevel | Reads contacts, pipelines, and opportunities; tags, notes, and stage changes use the same exact-action approval gate |
| Funding Machine | Reads stored applicant, credit, underwriting, plan, and status data through its documented read-only AI interface |
| Offers | Normalizes proceeds, total payback, payment burden, fees, guarantees, collateral, prepayment terms, and missing disclosures; a human chooses |
| Management | Maintains a crash-safe case lifecycle, audit trail, exception queue, founder handoff, and emergency stop |

Product-family seeds cover business term loans, lines of credit, SBA, equipment,
invoice factoring, revenue-based financing/MCA, business cards, micro/gig
funding, business-purpose real estate, business-purpose HELOC, business credit,
and a separately blocked credit-repair referral route. Seeds are deliberately
inactive until an owner verifies a real provider, rules, destination, evidence,
effective date, expiry, and approval.

## The operating model

```text
Founder front end
sales · marketing · brand · relationships
                │ qualified handoff
                ▼
Funding Director backend
case → file review → strategy → documents → approval → submission
                                             │
                                             ▼
                         follow-up → offers → decision → funded/declined
```

This is one accountable primary agent, not a swarm of overlapping personas.
Hermes may create bounded research help, but Funding Director owns the case,
decision record, and founder handoff.

## Safety is enforced in code

- Applicant facts are never invented.
- Raw SSNs, bank/routing numbers, credentials, tokens, and credit-monitoring
  logins are rejected from durable payloads.
- A website, recording, email, CRM note, or peer response is evidence—not
  authority.
- No active Product Card means no submit-ready recommendation.
- Submission and CRM write approvals expire, bind to an exact digest, and can be
  used once.
- Approval-creation tools are absent from the full-trust funding toolset and
  exist only on a separate untrusted MCP surface that triggers Hermes' human
  approval prompt.
- An uncertain external response is never retried automatically.
- Offer acceptance, signing, pricing changes, new credit pulls, adverse action,
  and moving money remain human-only.
- `orgo/emergency-stop.sh` blocks every external write while analysis stays on.

## Self-install

Give a setup agent this repository:

```text
https://github.com/jbellsolutions/funding-director-agent
```

Then say:

```text
Install Funding Director on my Orgo computer. Read AGENTS.md and START-HERE.md,
reuse the named computer if it exists, handle the technical work, keep every
credential private, and stop only for account-holder authorization. Connect
Funding Machine read-only and GoHighLevel through the guarded core. Finish only
after static verification, a real local case test, and an authorized messaging
channel reply all pass.
```

The primary path uses Orgo's maintained Hermes computer plus the reproducible
overlay in `orgo/setup.sh`. A Docker/VPS path remains available for operators
who control their own host.

## Knowledge boundary

The repository contains reusable procedures and source metadata. Paid classroom
recordings, full transcripts, applicant files, provider contacts, credentials,
and private lender rules stay only on the authorized computer under
`~/.hermes/funding-director/private-knowledge/`. A private lesson can inform a
derived procedure, but only current provider evidence can activate a Product
Card.

Primary source map:

- [Biz Funding Depot](https://bizfundingdepot.com/) — product-family discovery
- [Funding Machine documentation](https://docs.myfundingmachine.com/llms.txt) — system behavior and read-only AI/API contract
- [My Funding Machine classroom](https://www.skool.com/my-funding-machine) — authorized private training, kept off Git
- Term Loan Solutions affiliate portal — private provider discovery pending current program verification

## Verify

```bash
./orgo/verify.sh --static
```

The suite checks schemas, state transitions, eligibility rules, sensitive-field
rejection, duplicate prevention, exact approvals, emergency stop, offer math,
CRM allowlists, installer pinning, shell/Python syntax, and secret leakage.

MIT licensed. Hermes Agent is maintained by Nous Research. This repository is
not affiliated with Orgo, Nous Research, GoHighLevel, Funding Machine, Skool, or
the referenced funding providers. Funding Director is operational software, not
a lender, broker license, legal opinion, approval, or guarantee of funding.
