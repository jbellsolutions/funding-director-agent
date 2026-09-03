# Security

## Public repository boundary

This repository must contain zero live credentials and zero customer data.
Commit only templates, seeded instructions, and code.

Never commit:

- `agent.env`, `.env`, or a rendered `hermes/data/config.yaml`.
- API keys, bot tokens, OAuth sessions, cookies, SSH keys, or webhook secrets.
- Applicant lists, applications, credit reports, bank statements, tax returns,
  conversations, provider offers, call notes, or browser profiles.
- Personal Slack, Telegram, Discord, WhatsApp, iMessage, Notion, tailnet,
  calendar, or A2A identifiers.
- Paid training source material, private lender rules, portal playbooks,
  provider contacts, or another owner's persona and private skills.

The safe copy intentionally excludes all of those from the live VPS.

## Where private values live

- `/srv/<operator>/.env` — owner-provided keys; mode 600.
- `/srv/<operator>/hermes/data/config.yaml` — rendered config and the Composio
  consumer header; mode 600.
- `/srv/<operator>/hermes/data/` — sessions, authentication, memory, and work.
- `/srv/<operator>/vault/` — durable business knowledge and mirrored history.
- `/srv/<operator>/funding-director/` — cases, audit records, private training,
  Product Cards, destinations, permissions, and organization state.

These paths are host-mounted runtime state and are ignored by git.

## Network boundary

The dashboard binds to `127.0.0.1`. Reach it through an SSH tunnel or a private
Tailscale network. Do not publish port 18789 directly to the internet.

Keep `GATEWAY_ALLOW_ALL_USERS=false` unless a public bot is intentional. Use
channel pairing, invite the Slack app only to intended channels, and keep
provider scopes as narrow as practical.

## External actions

Research, file analysis, local drafts, and internal case updates can run
autonomously. Every funding submission and every GoHighLevel mutation requires
an exact, expiring, single-use approval. The model-facing full-trust MCP excludes
both approval-creation tools; those tools exist only on a second `untrusted`
surface, so Hermes manual mode prompts the human before writing the approval
record. Do not add them back to the full-trust toolset.

Credit pulls, provider or Product Card activation, offer acceptance, signatures,
fee/term changes, bank instructions, money movement, and adverse-action notices
remain human-only. Uncertain external results are reconciled before retry.

## Before pushing a fork

Run:

```bash
./scripts/verify.sh
git status --short
```

Review every staged file. A green scan cannot decide whether ordinary-looking
business data is private.

## If a secret is exposed

1. Revoke or rotate it at the provider immediately.
2. Replace it in the private server `.env`.
3. Re-run the appropriate setup/connection helper and restart Funding Director.
4. Remove it from git history; deleting the current line is not enough.
5. Review provider audit logs for unexpected use.

Report security issues privately to the repository owner instead of opening a
public issue with sensitive details.
