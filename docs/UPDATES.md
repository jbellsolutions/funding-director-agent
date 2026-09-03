# Runtime and update guide

## Reviewed runtime

Funding Director pins Hermes Agent v0.21.0:

```text
tag: v2026.8.31
commit: 29112bef099274229cadff79cdff7bf7b99c4b77
image: nousresearch/hermes-agent:v2026.8.31
multi-architecture digest: sha256:64923faeae267792bf9bf87fe3b4c4869e35004e360c7df01730ad801b74d524
```

The Orgo installer also verifies the reviewed upstream installer SHA-256 stored
in `orgo/deployment.json`. Production never follows `latest`.

## Safe update

Run `./update.sh /srv/<operator>/.env` on a Docker/VPS deployment, or pull the
repository and rerun `./orgo/setup.sh` on Orgo. Seed synchronization refreshes
unchanged public files but preserves owner-edited knowledge, activated private
Product Cards, destination rules, credentials, audit state, and private
training.

Before changing a runtime pin, review official release/migration notes, record
the exact commit/tag/digest/installer hash, run static and fresh-install tests,
prove the funding MCP, run a synthetic approval/receipt case, and test one
authorized messaging channel on a non-production computer.
