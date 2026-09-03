# Funding Director — VPS Edition

This is the self-hosted alternative to the Orgo install. It deploys the same
Funding Director on a private Ubuntu server with durable case state, a governed
product catalog, approval-gated submissions, offer comparison, GoHighLevel,
and read-only My Funding Machine access.

## Install

Give this repository URL to a computer-using setup agent and tell it to read
`AGENTS.md` and `START-HERE.md`, then deploy the VPS edition for you:

```text
https://github.com/jbellsolutions/funding-director-agent
```

The direct server command is:

```bash
git clone https://github.com/jbellsolutions/funding-director-agent.git
cd funding-director-agent
./setup.sh
```

The installer prepares a digest-pinned Hermes Agent 0.21.0 container, collects
private values without printing them, starts the agent, and waits for a healthy
result. Telegram or Slack provides the first messaging channel. The private
dashboard remains bound to localhost.

## What is included

| Area | Capability |
|---|---|
| Case operations | Durable stage machine from intake through funded/declined/withdrawn |
| Underwriting | Completeness, bank-statement and credit-profile review inputs |
| Product routing | Deterministic matching against owner-verified Product Cards |
| Submissions | Exact payload freeze, one-time approval, receipt, deduplication, no uncertain retry |
| Offers | Normalized cost and debt-service comparison with unknown terms preserved |
| CRM | Location-scoped GoHighLevel reads and approval-gated limited writes |
| Funding system | Read-only My Funding Machine context through its documented MCP/API |
| Safety | Emergency stop, immutable audit events, least privilege, human-only financial/legal decisions |

The public catalog intentionally ships in discovery mode. Real provider names,
box rules, credentials, portals, rate sheets, and paid training remain private.
An owner activates a Product Card only after current provider evidence and a
submission destination have been verified.

## Private connections

After launch, run `/srv/<agent>/bin/finish-setup.sh` to add channels and optional
business apps. Configure these funding connections only in the private `.env`:

- `FUNDING_MACHINE_API_KEY` for read-only Funding Machine context.
- `GHL_API_KEY` using a sub-account Private Integration Token beginning `pit-`.
- `GHL_LOCATION_ID` for the single authorized GoHighLevel sub-account.

GoHighLevel changes and funding submissions require an exact, expiring,
one-time approval at launch. No connector may pull credit, accept an offer,
sign an agreement, move money, charge a fee, or send an adverse-action notice.

## Durable data and recovery

Private state is stored under `/srv/<agent>` and is not committed to Git. Back
up `hermes/data`, `vault`, `funding-director`, and `.env`. Never use
`docker compose down -v` on a production installation.

Verification:

```bash
./scripts/verify.sh
sudo ./tests/smoke_deployment.sh
```

See `SECURITY.md`, `docs/TOOLS.md`, and `docs/UPDATES.md` before production use.
This software supports operations; it is not a lender, credit bureau, law firm,
or substitute for provider underwriting and required disclosures.
