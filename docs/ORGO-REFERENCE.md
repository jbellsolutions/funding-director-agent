# Orgo reference for Funding Director

Last checked against the official Orgo documentation: **August 30, 2026**.

The current machine-readable source is Orgo's
[`llms.txt`](https://docs.orgo.ai/llms.txt). An installation agent should check
that source before deployment because available plans, limits, templates, and
API fields can change. If it conflicts with this page, the current official
documentation wins unless following it would weaken this repository's security
rules.

## What Orgo provides

Orgo provides the persistent Linux computer. Funding Director and Hermes run inside
it. The computer keeps its files and `~/.hermes` state while the owner's
personal computer is off.

Orgo documents these relevant capabilities:

- create and list workspaces;
- create, inspect, start, stop, restart, clone, resize, and move computers;
- launch a computer from a curated template by passing `template_ref`;
- run terminal commands and inspect screenshots through authenticated APIs;
- connect through the Orgo dashboard, CLI, SDK, or MCP server.

The official [Hermes guide](https://docs.orgo.ai/guides/hermes) also explains
that Orgo computers do not have a public inbound hostname. Funding Director therefore
uses Slack Socket Mode and Telegram long-polling. It does not require a public
Slack or Telegram webhook.

## The plain-English deployment

1. Sign in to the intended Orgo account and confirm it can launch the curated
   Hermes template.
2. Find or create the customer workspace. For the AI Guy installation, use
   `AI Guy`.
3. Find or create `ai-guy-funding-director`. If a computer with that name is already
   present, inspect it and continue rather than creating a duplicate.
4. Launch `system/hermes-agent@1.0.0` with the values in
   `orgo/deployment.json`.
5. Wait for the computer to report `running`, open its terminal, clone this
   repository, and run `./orgo/setup.sh`.
6. Complete the model setup privately, prove a local response, then connect
   Slack, optional Telegram, and the approved business accounts.
7. Send `hello`, select quick start or guided onboarding, run
   `./orgo/verify.sh`, and send a real authorized message. Preserve the computer
   if an optional connection must be finished later.

## API map used by a setup agent

The base URL is `https://www.orgo.ai/api`. Requests use a bearer API key. Never
print the key or place it in a repository file.

| Purpose | Official API operation |
|---|---|
| Find or create the customer workspace | `GET /workspaces`, then `POST /workspaces` only if missing |
| Create the Funding Director computer | `POST /computers` |
| Wait for launch and inspect state | `GET /computers/{id}` |
| Run installation commands | `POST /computers/{id}/bash` or an authenticated terminal session |
| Inspect the visible result | `GET /computers/{id}/screenshot` |
| Recover a stopped computer | `POST /computers/{id}/start` |
| Restart after a configuration change | `POST /computers/{id}/restart` |

The create request is equivalent to this shape; values come from the committed
deployment manifest:

```json
{
  "workspace_id": "WORKSPACE_ID",
  "name": "ai-guy-funding-director",
  "template_ref": "system/hermes-agent@1.0.0",
  "os": "linux",
  "ram": 8,
  "cpu": 2,
  "disk_size_gb": 40,
  "resolution": "1440x900x24"
}
```

Use an account-wide key only for the initial workspace lookup or creation. A
workspace-scoped key is preferable for later automation because Orgo documents
that it cannot access another workspace.

## Why this is not a custom template

Orgo's [template documentation](https://docs.orgo.ai/guides/templates/introduction)
states that curated `system` templates can launch on paid plans, while publishing
and building a private custom template requires Scale. This repository keeps the
Startup-compatible path: launch the curated Hermes computer, then apply the
reviewed repository overlay.

## Sizing note

The repository requests 8 GB RAM, 2 vCPU, and 40 GB disk. This is the selected
Startup-compatible footprint. Orgo's general Hermes guide may recommend more
CPU for heavier workloads; plan limits and pricing must be checked at deployment
time rather than inferred from this repository.

## Source links

- [Orgo complete `llms.txt`](https://docs.orgo.ai/llms.txt)
- [Orgo Hermes guide](https://docs.orgo.ai/guides/hermes)
- [Orgo templates](https://docs.orgo.ai/guides/templates/introduction)
- [Orgo API reference](https://docs.orgo.ai/api-reference/introduction)
- [Orgo pricing](https://www.orgo.ai/pricing)
