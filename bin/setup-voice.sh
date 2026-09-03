#!/usr/bin/env bash
# Install the voice front-end: FastAPI relay (systemd) + Caddy TLS + build the
# ElevenLabs agent + wire the talk page. Run AFTER the agent container is up and
# AFTER a DNS A-record for VOICE_DOMAIN points at this host. Root recommended.
set -euo pipefail
BASE="__BASE_DIR__"
DOMAIN="__VOICE_DOMAIN__"
AGENT="__AGENT_NAME__"
PY="$BASE/venv/bin/python3"

# venv + relay deps (composio for the fast tools, fastapi/uvicorn for the relay)
if [ ! -x "$PY" ]; then python3 -m venv "$BASE/venv"; "$BASE/venv/bin/pip" -q install --upgrade pip composio; fi
"$BASE/venv/bin/pip" -q install fastapi uvicorn

# systemd relay (127.0.0.1:8787)
cp "$BASE/voice/voice-relay.service" /etc/systemd/system/voice-relay.service
systemctl daemon-reload
systemctl enable --now voice-relay
sleep 2; curl -fsS 127.0.0.1:8787/healthz >/dev/null && echo "  · relay up" || { echo "relay failed — check: journalctl -u voice-relay"; exit 1; }

# Caddy TLS + talk page
if ! command -v caddy >/dev/null 2>&1; then
  apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl >/dev/null 2>&1
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq >/dev/null 2>&1; apt-get install -y -qq caddy >/dev/null 2>&1
fi
mkdir -p "$BASE/voice/www"
cp "$BASE/voice/Caddyfile" /etc/caddy/Caddyfile
ufw allow 80/tcp >/dev/null 2>&1 || true; ufw allow 443/tcp >/dev/null 2>&1 || true
systemctl restart caddy

# Build the ElevenLabs agent, capture id, wire the page + fast tools
echo "  · creating ElevenLabs agent…"
AGENT_ID=$("$PY" "$BASE/voice/create_agent.py" | awk -F': ' '/^AGENT_ID:/{print $2}')
[ -n "$AGENT_ID" ] || { echo "agent creation failed"; exit 1; }
echo "$AGENT_ID" > "$BASE/voice/agent.id"
sed -i "s#__AGENT_ID__#${AGENT_ID}#g" "$BASE/voice/www/talk.html"
AGENT_ID="$AGENT_ID" "$PY" "$BASE/voice/patch_agent.py"   # add fast direct-Composio tools

echo ""
echo "✅ Voice live:  https://${DOMAIN}/talk   (agent ${AGENT_ID})"
echo "   Tap 'Start a call' from any browser (desktop or phone)."
