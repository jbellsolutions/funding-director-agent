#!/usr/bin/env bash
# Configure one authenticated Hermes A2A peer over a private Tailscale address.
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
ENV_FILE="$HERMES_HOME/.env"
CONFIG_FILE="$HERMES_HOME/config.yaml"
secret() { local value; read -r -s -p "$1: " value; printf '\n' >&2; printf '%s' "$value"; }
upsert() {
  local key=$1 value=$2 temp
  temp="$(mktemp "$HERMES_HOME/.env.tmp.XXXXXX")"
  awk -v key="$key" 'index($0, key "=") != 1 { print }' "$ENV_FILE" > "$temp"
  printf '%s=%s\n' "$key" "$value" >> "$temp"
  chmod 600 "$temp"
  mv "$temp" "$ENV_FILE"
}

[ -f "$CONFIG_FILE" ] || { echo "Run orgo/setup.sh first." >&2; exit 1; }
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"
command -v tailscale >/dev/null 2>&1 || {
  echo "Tailscale is required so A2A stays private. Install/connect Tailscale first." >&2
  exit 1
}
local_ip="$(tailscale ip -4 | head -n 1)"
[ -n "$local_ip" ] || { echo "This computer is not connected to Tailscale." >&2; exit 1; }

read -r -p "Peer name (for example relationship-manager): " peer_name
[[ "$peer_name" =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "Use lowercase letters, numbers, and dashes." >&2; exit 1; }
read -r -p "Peer Tailscale IPv4 address: " peer_ip
[[ "$peer_ip" =~ ^100\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "That is not a Tailscale IPv4 address." >&2; exit 1; }
incoming="$(secret "Paste the token this peer will use to call Funding Director")"
outgoing="$(secret "Paste the token Funding Director will use to call this peer")"
[ "${#incoming}" -ge 32 ] && [ "${#outgoing}" -ge 32 ] || { echo "Use tokens at least 32 characters long." >&2; exit 1; }

upsert A2A_PEER_TOKENS "$peer_name:$incoming"
upsert A2A_TRUSTED_PEERS "$peer_name"
upsert A2A_HOST 0.0.0.0
upsert A2A_PORT 9900
upsert A2A_AGENT_NAME funding-director
upsert A2A_PUBLIC_URL "http://$local_ip:9900"
upsert A2A_MAX_PINGPONG_TURNS 3
unset incoming
hermes config set "a2a_agents.$peer_name.url" "http://$peer_ip:9900" >/dev/null
hermes config set "a2a_agents.$peer_name.auth.type" bearer >/dev/null
hermes config set "a2a_agents.$peer_name.auth.token" "$outgoing" >/dev/null
hermes config set "a2a_agents.$peer_name.timeout" 120 >/dev/null
unset outgoing
chmod 600 "$CONFIG_FILE"
hermes gateway restart >/dev/null 2>&1 || true
echo "A2A is configured for one trusted peer. Inbound A2A cannot call another peer."
