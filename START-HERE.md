# Start Here: Funding Director on Orgo

Funding Director is a persistent backend business-funding co-founder. A setup
agent performs the technical work from this repository and involves the account
holder only when a private service requires sign-in, consent, billing, or a
credential entered into a hidden prompt.

## One-message handoff

```text
Install Funding Director from
https://github.com/jbellsolutions/funding-director-agent

Read AGENTS.md, START-HERE.md, and docs/ORGO-SETUP.md. Inspect my Orgo account
before changing anything and reuse ai-guy-funding-director if it exists. Handle
all technical steps. Keep keys out of chat, screenshots, logs, and Git. Connect
Funding Machine read-only, connect GoHighLevel with a location-scoped private
integration token, and add only the messaging channels I authorize. Do not
activate a lender or Product Card without current provider evidence and my
approval. Finish only after orgo/verify.sh passes, a synthetic case completes
the approval/receipt workflow, and a real authorized message gets a reply.
```

## What the setup agent does

1. Inspects the Orgo workspace and reuses the intended computer when present.
2. Otherwise launches `system/hermes-agent@1.0.0` as
   `ai-guy-funding-director` with the shape in `orgo/deployment.json`.
3. Clones this repository and runs `./orgo/setup.sh`.
4. Configures the model privately and proves one harmless local response.
5. Runs `./orgo/connect.sh` for the selected channel, Funding Machine,
   GoHighLevel, and optional business apps.
6. Runs `./orgo/verify.sh`, completes a synthetic case test, and proves one real
   authorized Slack or Telegram exchange.

The installer pins Hermes v0.21.0 to an exact reviewed commit and checksum. It
installs the Funding Director identity, funding skills, deterministic core,
versioned product and destination catalogs, durable SQLite state, audit log,
manual approvals, hard loop stop, PII/secret redaction, and desktop launchers.

## Connection rules

- Funding Machine uses a dedicated `fmk_` key and its documented read-only MCP.
- GoHighLevel uses a location-scoped `pit-` Private Integration Token. Never use
  a Firebase login or refresh token.
- Slack is restricted to named Member IDs; invite the app only to intended
  channels.
- Account credentials are entered only into hidden prompts on the private
  computer and stored in its protected environment file.
- Paid classroom material remains in private runtime knowledge and is never
  bundled into copies of the repository.

## First operating proof

The setup agent creates a synthetic applicant with no real personal data,
advances the case through the allowed state machine, confirms the public seed
has no active submit-ready funder, and tests a temporary provider fixture. It
must prove that:

- missing documents and inactive products block submission;
- an exact, expiring approval is required;
- a changed digest is rejected;
- a used approval cannot be reused;
- an external receipt is stored;
- the emergency stop blocks both submissions and CRM writes.

## Going live

The agent opens the private onboarding conversation, captures the business
context, maps the founder/relationship-manager handoff, inventories current
provider programs, and creates one Product Card per real program. A card becomes
active only after current rules, state/industry limits, documents, destination,
effective date, expiry, and owner approval are recorded.

Start every real destination with one-time approvals. Graduated autonomy is a
later audited release for one named product/destination playbook at a time; it
is not enabled by this initial installer.

Use `./orgo/emergency-stop.sh "reason"` to freeze every external write without
losing analysis or case access. Only the account holder should run
`./orgo/resume-external-writes.sh` after reviewing the stop reason.
