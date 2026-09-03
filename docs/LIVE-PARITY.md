# Source and Runtime Lineage

Audit date: 2026-09-02.

The project began from the owner's `head-of-ops-orgo` deployment pattern and
was compared with the owner's `ai-cofounder-orgo` governance pattern. It now has
a funding-specific identity, deterministic operating core, product catalog,
and permissions rather than a renamed generic assistant.

## Preserved, reviewed infrastructure

| Source pattern | Funding Director implementation |
|---|---|
| Persistent single Hermes operator | One accountable Funding Director; temporary workers may assist but cannot own cases or approvals |
| Orgo setup overlay | `orgo/setup.sh`, pinned installer checksum, verification, desktop launchers |
| Self-hosted container | Digest-pinned Hermes Agent v0.21.0 and durable private mounts |
| Messaging gateway | Slack, Telegram, Discord, WhatsApp, BlueBubbles/iMessage, private dashboard |
| Browser capability | Vendored Super Browser package with its upstream source and runtime lock unchanged |
| Durable memory | Funding knowledge vault plus SQLite case, approval, offer, and audit state |
| Safety controls | Manual approvals, hard loop stop, fail-closed security checks, emergency external-write stop |

## Funding-specific additions

- Case lifecycle and underwriting profile validation.
- Discovery-only public product families and owner-verified live Product Cards.
- Provider destination registry and reviewed HTTPS/browser submission adapters.
- Frozen payload hashes, expiring one-time approvals, receipts, and deduplication.
- Offer normalization without equating factor rate and APR.
- Current HighLevel v3 contact/opportunity contract with a location-scoped PIT.
- Read-only My Funding Machine connection and operating map.
- Private training ingestion rules that preserve paid-content boundaries.

## Intentionally excluded

- Keys, cookies, OAuth sessions, private provider portals, rate sheets, lender
  contacts, customer files, credit reports, bank statements, and audit data.
- Full paid Skool lessons, recordings, transcripts, and downloadable resources.
- Provider eligibility rules or terms that have not been verified from current
  provider-controlled evidence.
- Automatic credit pulls, offer acceptance, signatures, fees, movement of
  money, legal notices, or deletion of audit history.

Those omissions are operational controls, not missing features. Each private
installation supplies its own verified provider evidence and authorized
connections.
