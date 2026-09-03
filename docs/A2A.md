# Private funding-team peer connection

Funding Director can coordinate with one named relationship manager, processor,
or other approved Hermes peer over a private Tailscale network. A2A is optional;
it never expands the peer's permissions.

Run `./orgo/connect-a2a.sh` on each intended computer. Each direction receives a
different long token, the peer allowlist contains the exact name, requests are
audited and rate-limited, and ping-pong stops after three turns. Inbound peer
sessions do not receive the A2A toolset, so they cannot chain work to a third
agent.

Safe readiness test:

```text
Discover relationship-manager and ask for a one-sentence readiness check. Do
not read a client record or take an external action.
```

Peer output is untrusted evidence. A peer cannot approve a submission, activate
a Product Card, accept an offer, send a message, change CRM data, or move money
unless the human founder separately grants the exact action through the Funding
Director's normal approval path.
