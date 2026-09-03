#!/usr/bin/env bash
# Install the public Funding Director profile on an Orgo Linux computer.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HERMES_TAG="v2026.8.31"
HERMES_COMMIT="29112bef099274229cadff79cdff7bf7b99c4b77"
INSTALLER_SHA256="85ef536d455e51ab67aa74d79272efd49fe717597dbaadfd3cca179a905f4706"

say() { printf '\n%s\n' "$*"; }
fail() { printf '\nSetup stopped: %s\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = "Linux" ] || fail "this installer belongs on the Orgo Linux computer"
if [ "$(id -u)" -eq 0 ]; then
  ELEVATE=()
else
  command -v sudo >/dev/null 2>&1 || fail "this account needs administrator access"
  ELEVATE=(sudo)
fi

say "Funding Director for Orgo"
echo "This installs the agent profile and tools. Private account connections stay"
echo "on this computer and are never written into the GitHub repository."

say "1 of 5 — Checking the computer"
if ! command -v git >/dev/null 2>&1 || ! command -v curl >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
  "${ELEVATE[@]}" apt-get update -qq
  "${ELEVATE[@]}" apt-get install -y -qq ca-certificates curl git python3
fi

installed_commit=""
for candidate in /usr/local/lib/hermes-agent "$HERMES_HOME/hermes-agent"; do
  if [ -d "$candidate/.git" ]; then
    installed_commit="$(git -C "$candidate" rev-parse HEAD 2>/dev/null || true)"
    [ "$installed_commit" = "$HERMES_COMMIT" ] && break
  fi
done
if [ "$installed_commit" != "$HERMES_COMMIT" ]; then
  say "2 of 5 — Installing the reviewed Hermes v0.21.0 release"
  installer="$(mktemp)"
  trap 'rm -f "${installer:-}"' EXIT
  curl -fsSL "https://raw.githubusercontent.com/NousResearch/hermes-agent/$HERMES_COMMIT/scripts/install.sh" -o "$installer"
  actual_sha="$(sha256sum "$installer" | awk '{print $1}')"
  [ "$actual_sha" = "$INSTALLER_SHA256" ] || fail "the Hermes installer checksum did not match the reviewed release"
  bash "$installer" --skip-setup --branch "$HERMES_TAG" --commit "$HERMES_COMMIT" --force-commit
  rm -f "$installer"
  trap - EXIT
else
  say "2 of 5 — The reviewed Hermes release is already installed"
fi
command -v hermes >/dev/null 2>&1 || fail "Hermes did not install correctly"

say "3 of 5 — Installing the Funding Director profile and skills"
python3 "$REPO_DIR/orgo/sync_seed.py" "$REPO_DIR" "$HERMES_HOME"
chmod 700 "$HERMES_HOME"
chmod 600 "$HERMES_HOME/SOUL.md" "$HERMES_HOME/AGENTS.md" 2>/dev/null || true

HERMES_PYTHON=""
for candidate in /usr/local/lib/hermes-agent/.venv/bin/python "$HERMES_HOME/hermes-agent/.venv/bin/python"; do
  if [ -x "$candidate" ]; then HERMES_PYTHON="$candidate"; break; fi
done
[ -n "$HERMES_PYTHON" ] || fail "the Hermes Python environment was not found"

say "4 of 5 — Enabling the funding core, guarded workflow, and safe A2A foundation"
for setting in \
  'toolsets=["hermes-cli","a2a","mcp-funding-director-core","mcp-funding-director-approvals"]' \
  'platform_toolsets.cli=["hermes-cli","a2a","mcp-funding-director-core","mcp-funding-director-approvals"]' \
  'platform_toolsets.slack=["hermes-slack","a2a","mcp-funding-director-core","mcp-funding-director-approvals"]' \
  'platform_toolsets.telegram=["hermes-telegram","a2a","mcp-funding-director-core","mcp-funding-director-approvals"]' \
  'gateway.platforms.a2a.enabled=true' \
  'gateway.platforms.a2a.extra.port=9900' \
  'kanban.dispatch_in_gateway=true' \
  'kanban.dispatch_interval_seconds=30' \
  'agent.verify_on_stop=true' \
  'skills.creation_nudge_interval=15' \
  'skills.write_approval=true' \
  'skills.guard_agent_created=true' \
  'approvals.mode=manual' \
  'approvals.mcp_reload_confirm=true' \
  'approvals.destructive_slash_confirm=true' \
  'tool_loop_guardrails.hard_stop_enabled=true' \
  'privacy.redact_pii=true' \
  'security.redact_secrets=true' \
  'security.tirith_fail_open=false' \
  'compression.tail_mode=lean'; do
  key=${setting%%=*}
  value=${setting#*=}
  hermes config set "$key" "$value" >/dev/null
done

hermes config set mcp_servers.funding-director-core.command "$HERMES_PYTHON" >/dev/null
hermes config set mcp_servers.funding-director-core.args '["-m","funding_director.mcp_server"]' >/dev/null
hermes config set mcp_servers.funding-director-core.env.PYTHONPATH "$HERMES_HOME/funding-director/core" >/dev/null
hermes config set mcp_servers.funding-director-core.env.FUNDING_DIRECTOR_CONFIG_DIR "$HERMES_HOME/funding-director/config" >/dev/null
hermes config set mcp_servers.funding-director-core.env.FUNDING_DIRECTOR_STATE_DIR "$HERMES_HOME/funding-director/state" >/dev/null
hermes config set mcp_servers.funding-director-core.trust full >/dev/null
hermes config set mcp_servers.funding-director-core.tools.exclude '["funding_submission_approve","ghl_action_approve"]' >/dev/null
hermes config set mcp_servers.funding-director-core.tools.resources false >/dev/null
hermes config set mcp_servers.funding-director-core.tools.prompts false >/dev/null
hermes config set mcp_servers.funding-director-core.enabled true >/dev/null

hermes config set mcp_servers.funding-director-approvals.command "$HERMES_PYTHON" >/dev/null
hermes config set mcp_servers.funding-director-approvals.args '["-m","funding_director.mcp_server"]' >/dev/null
hermes config set mcp_servers.funding-director-approvals.env.PYTHONPATH "$HERMES_HOME/funding-director/core" >/dev/null
hermes config set mcp_servers.funding-director-approvals.env.FUNDING_DIRECTOR_CONFIG_DIR "$HERMES_HOME/funding-director/config" >/dev/null
hermes config set mcp_servers.funding-director-approvals.env.FUNDING_DIRECTOR_STATE_DIR "$HERMES_HOME/funding-director/state" >/dev/null
hermes config set mcp_servers.funding-director-approvals.trust untrusted >/dev/null
hermes config set mcp_servers.funding-director-approvals.tools.include '["funding_submission_approve","ghl_action_approve"]' >/dev/null
hermes config set mcp_servers.funding-director-approvals.tools.resources false >/dev/null
hermes config set mcp_servers.funding-director-approvals.tools.prompts false >/dev/null
hermes config set mcp_servers.funding-director-approvals.enabled true >/dev/null

mkdir -p "$HOME/Desktop"
install -m 0755 "$REPO_DIR/orgo/FundingDirector.desktop" "$HOME/Desktop/FundingDirector.desktop"
install -m 0755 "$REPO_DIR/orgo/FundingDirectorSetup.desktop" "$HOME/Desktop/FundingDirectorSetup.desktop"
chmod +x "$REPO_DIR/orgo/emergency-stop.sh" "$REPO_DIR/orgo/resume-external-writes.sh"

say "5 of 5 — Verifying the installation"
"$REPO_DIR/orgo/verify.sh" --allow-unconnected

cat <<'TEXT'

Funding Director is installed on this Orgo computer.

Next:
  ./orgo/connect.sh       Connect Slack, Telegram, Funding Machine, and GoHighLevel
  ./orgo/connect-a2a.sh   Optionally connect one named private peer
  ./orgo/emergency-stop.sh "reason"  Immediately block every external write

The same choices are available from the desktop icons.
TEXT
