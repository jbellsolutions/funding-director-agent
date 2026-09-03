# Funding Director on Orgo

This is the supported deployment path. It gives the Funding Director a
persistent visible Linux computer, durable case state, private knowledge, and
its own Slack or Telegram presence.

## Deployment contract

The setup agent first inspects the account. It reuses
`ai-guy-funding-director` if present and never changes an unrelated computer.
When missing, it launches `system/hermes-agent@1.0.0` with the hardware in
`orgo/deployment.json`, waits for `running`, and opens the terminal.

```bash
git clone https://github.com/jbellsolutions/funding-director-agent.git
cd funding-director-agent
./orgo/setup.sh
```

The installer verifies and installs the exact Hermes v0.21.0 commit, then adds:

- the single Funding Director operating profile;
- durable funding case, offer, approval, audit, and submission state;
- versioned Product Cards and destination allowlists;
- funding file, routing, submission, offer, handoff, and knowledge skills;
- the guarded GoHighLevel client and read-only Funding Machine connection path;
- manual approvals, hard loop stop, redaction, and an external-write emergency
  stop.

## Private connections

Run `./orgo/connect.sh` once per selected connection. Secrets are entered with
hidden prompts and stored only in `~/.hermes/.env` with mode `600`.

- Funding Machine: dedicated `fmk_` key, read-only MCP.
- GoHighLevel: exact location ID and location-scoped `pit-` Private Integration
  Token. Firebase/session credentials are forbidden.
- Slack: `xoxb-` and `xapp-` tokens plus a named Member-ID allowlist.
- Telegram: dedicated bot token.
- Composio: optional supporting calendar, inbox, and file access.

Begin with read-only proof. No real submission, CRM write, credit pull, message,
agreement, acceptance, or payment is part of installation.

## Private training and providers

Authenticated Skool lessons, transcripts, provider contacts, attachments, and
real program rules belong in
`~/.hermes/funding-director/private-knowledge/`. The directory is created mode
`700` and is not synchronized into Git. Store derived procedures with source and
date; activate Product Cards only from current provider evidence.

## Verification

```bash
./orgo/verify.sh
```

The live verifier checks the pinned runtime, seed, skills, schemas, deterministic
tests, approval mode, loop stop, funding MCP, gateway, and connections. The
setup agent also runs one PII-free synthetic case and proves one authorized
messaging-channel reply.

Emergency stop:

```bash
./orgo/emergency-stop.sh "reason"
```

This leaves analysis and case access running but blocks every external
submission and CRM write. Resume is a separate owner-confirmed operation:
`./orgo/resume-external-writes.sh`.

Orgo plan capabilities and pricing can change. Recheck current facts against
[Orgo's official `llms.txt`](https://docs.orgo.ai/llms.txt) at deployment time.
