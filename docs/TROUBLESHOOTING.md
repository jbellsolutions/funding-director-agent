# Troubleshooting

Re-run the appropriate installer after correcting a private connection. It
refreshes declared configuration while preserving durable cases, audit history,
private knowledge, and activated Product Cards.

## Fast status

VPS:

```bash
docker compose ps
docker compose logs --tail=100 hermes
docker exec "$AGENT_NAME" /opt/hermes/.venv/bin/hermes gateway status
docker exec "$AGENT_NAME" /opt/hermes/.venv/bin/hermes mcp list
```

Orgo:

```bash
./orgo/verify.sh --allow-unconnected
```

## Symptom → safe response

| Symptom | Response |
|---|---|
| Agent cannot recommend a provider | This is expected until an owner-verified Product Card is active; inspect the missing evidence list |
| Submission says `approval required` | Review the exact product, destination, payload digest, consent reference, and permissible-purpose reference; approve only that action |
| Submission result is `failed-or-unknown` | Do not retry; reconcile in the provider portal and record the receipt or prepare a new action |
| External writes are stopped | Keep analysis running; investigate the reason in `EXTERNAL_WRITES_STOPPED`; only the owner may run the resume helper |
| Funding Machine reads fail | Confirm the private API key and remote MCP connection; it is intentionally read-only and cannot run a credit pull |
| GoHighLevel rejects credentials | Use a sub-account Private Integration Token beginning `pit-` plus the matching location ID; never use a browser-session credential |
| GoHighLevel returns 401/403 | Check the token's location and only the required contact/opportunity scopes; do not broaden to agency-wide access |
| A CRM write failed ambiguously | Read the contact/opportunity first; do not repeat the write until reconciled |
| Slack ignores messages | Confirm the bot is installed, invited to the channel, and the owner's Member ID is in `SLACK_ALLOWED_USERS` |
| Dashboard does not open | It is private by design; use the SSH tunnel printed by the VPS installer |
| History disappeared after rebuild | Restore the original data mounts and base directory; do not initialize a replacement database over the old one |
| Private training is missing | Authenticate to the authorized training source on the private computer and rebuild only derived procedures; do not place paid source material in Git |

## Emergency stop

On Orgo, run `orgo/emergency-stop.sh "reason"`. On a VPS, create the exact
sentinel file in the configured Funding Director state directory. The stop
blocks submissions and CRM writes but leaves file analysis and case work
available. The owner resumes with `orgo/resume-external-writes.sh` only after
reconciliation.

## Backup

```bash
cd /srv/<agent>
docker compose stop
tar -czf /srv/<agent>-backup.tgz hermes/data vault funding-director .env
docker compose start
```

The archive contains secrets and customer information. Keep it private and
encrypted.
