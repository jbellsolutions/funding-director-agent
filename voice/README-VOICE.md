# The Operator — Voice (ElevenLabs)

Talk to The Operator from any browser (desktop + phone). Same brain as Slack:
memory, vault, Gmail/Calendar/Linear/Notion — reached through the relay → hermes.

## Live surface
- **Talk page:** https://__VOICE_DOMAIN__/talk  (domain-locked widget; "Start a call")
- **Agent:** `__AGENT_ID__` (ElevenLabs, voice = Eric, LLM = gpt-4o-mini)
- **Relay:** `POST https://__VOICE_DOMAIN__/ask` (Bearer `$RELAY_TOKEN`) → `voice/relay.py`
  → `docker exec hermes hermes chat` against `/opt/data` (persistent voice session at `voice/session.id`).

## Architecture
```
phone/desktop browser → /talk (Caddy TLS) → <elevenlabs-convai> widget
   → ElevenLabs agent (Eric voice, gpt-4o-mini)
       └─ tool ask_the_operator (webhook, 60s, pre_tool_speech=force → auto "checking…")
            → https://__VOICE_DOMAIN__/ask (Bearer)
              → voice-relay.service (uvicorn 127.0.0.1:8787)
                → hermes one-shot → THE OPERATOR'S REAL BRAIN (memory + Composio tools)
```
Everything (live data + memory + actions) flows through the one relay path = one brain.
Widget auth: `enable_auth:false` + allowlist `__VOICE_DOMAIN__` (only loads on our page).

## Runbook

**Rotate the relay token** (do after any chat paste):
```
NEW=$(openssl rand -hex 24); sed -i "s/^RELAY_TOKEN=.*/RELAY_TOKEN=$NEW/" __BASE_DIR__/.env
systemctl restart voice-relay
# then PATCH the agent tool's Authorization header (see voice/create_agent.py tool step) or re-run it
```

**Change the voice:** pick a voice_id (`curl /v1/voices`), then
`PATCH /v1/convai/agents/<id>` body `{"conversation_config":{"tts":{"voice_id":"<id>"}}}`.

**Switch the LLM to Grok 4.5** (smart mode; billed to OpenRouter):
Custom-LLM needs the OpenRouter key as an ElevenLabs secret, then PATCH the agent prompt:
`{"conversation_config":{"agent":{"prompt":{"custom_llm":{"url":"https://openrouter.ai/api/v1","model_id":"x-ai/grok-4.5","api_key":{...secret...}}}}}}`.
Custom-LLM + tool-calling is a documented risk — test one relay turn after switching; revert to
`"llm":"gpt-4o-mini"` if tools misbehave. (Grok is already fallback #3 in the hermes brain regardless.)

**Direct Composio MCP (fast live-data):** gated to ElevenLabs **Business tier**. On Creator, all
tools route through the relay (slower, ~25-55s, masked by the auto-filler). Upgrade → attach MCP via
`POST /v1/convai/mcp-servers` (transport `STREAMABLE_HTTP`, header `x-api-key`).

**Real phone number (call it):** ElevenLabs → Phone Numbers → import Twilio number → assign this
agent. Minutes bill to the ElevenLabs plan; Twilio per-minute on top.

## Files (in this repo, deployed to __BASE_DIR__/voice/)
- `relay.py` — FastAPI relay (bearer auth, hermes one-shot, 55s guard, persistent voice session)
- `www/talk.html` — widget page (mobile add-to-homescreen ready)
- `create_agent.py` — recreates/updates the ElevenLabs agent from `.env` (idempotent-ish)
- `../.. /etc/systemd/system/voice-relay.service`, `/etc/caddy/Caddyfile` — service + TLS (host-level)

## Secrets (all in __BASE_DIR__/.env, gitignored)
`ELEVENLABS_API_KEY`, `RELAY_TOKEN`, plus the existing `COMPOSIO_*` / `OPENROUTER` keys.
