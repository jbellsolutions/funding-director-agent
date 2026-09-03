#!/usr/bin/env bash
set -euo pipefail

ALLOW_UNCONNECTED=false
STATIC_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --allow-unconnected) ALLOW_UNCONNECTED=true ;;
    --static) STATIC_ONLY=true ;;
    *) echo "Unknown verification option: $arg" >&2; exit 2 ;;
  esac
done
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
EXPECTED_COMMIT="29112bef099274229cadff79cdff7bf7b99c4b77"

python3 -m json.tool "$REPO_DIR/orgo/deployment.json" >/dev/null
python3 -m json.tool "$REPO_DIR/org/registry.json" >/dev/null
python3 -m json.tool "$REPO_DIR/policies/permissions.json" >/dev/null
python3 -m json.tool "$REPO_DIR/files/local-packages/funding-director/config/products.json" >/dev/null
python3 -m json.tool "$REPO_DIR/files/local-packages/funding-director/config/destinations.json" >/dev/null
python3 -m json.tool "$REPO_DIR/files/local-packages/funding-director/config/training-sources.json" >/dev/null
python3 "$REPO_DIR/scripts/validate_funding_config.py"
find "$REPO_DIR/orgo" -type f -name '*.sh' -print0 | xargs -0 bash -n
python3 -m compileall -q "$REPO_DIR/orgo" "$REPO_DIR/files/local-packages/funding-director/src" "$REPO_DIR/tests"
PYTHONPATH="$REPO_DIR/files/local-packages/funding-director/src" \
  python3 -m unittest discover -s "$REPO_DIR/tests" -p 'test_*.py' -v

if [ "$STATIC_ONLY" = true ]; then
  echo "Funding Director static verification passed."
  exit 0
fi

[ -f "$HERMES_HOME/SOUL.md" ]
[ -f "$HERMES_HOME/AGENTS.md" ]
[ -f "$HERMES_HOME/skills/roles/funding-director/SKILL.md" ]
[ -f "$HERMES_HOME/skills/funding/submission-operator/SKILL.md" ]
[ -f "$HERMES_HOME/funding-director/config/products.json" ]
[ -f "$HERMES_HOME/funding-director/config/destinations.json" ]
[ -f "$HERMES_HOME/funding-director/policies/permissions.json" ]
[ -d "$HERMES_HOME/funding-director/state" ]
[ -d "$HERMES_HOME/funding-director/private-knowledge" ]
installed=""
for candidate in /usr/local/lib/hermes-agent "$HERMES_HOME/hermes-agent"; do
  if [ -d "$candidate/.git" ]; then
    installed="$(git -C "$candidate" rev-parse HEAD 2>/dev/null || true)"
    [ "$installed" = "$EXPECTED_COMMIT" ] && break
  fi
done
[ "$installed" = "$EXPECTED_COMMIT" ] || { echo "Hermes is not at the reviewed commit." >&2; exit 1; }
hermes config get gateway.platforms.a2a.enabled 2>/dev/null | grep -qi true
hermes config get platform_toolsets.cli 2>/dev/null | grep -q a2a
hermes config get platform_toolsets.cli 2>/dev/null | grep -q mcp-funding-director-core
hermes config get platform_toolsets.cli 2>/dev/null | grep -q mcp-funding-director-approvals
hermes config get mcp_servers.funding-director-core.trust 2>/dev/null | grep -q full
hermes config get mcp_servers.funding-director-approvals.trust 2>/dev/null | grep -q untrusted
hermes config get mcp_servers.funding-director-approvals.tools.include 2>/dev/null | grep -q funding_submission_approve
hermes config get approvals.mode 2>/dev/null | grep -q manual
hermes config get tool_loop_guardrails.hard_stop_enabled 2>/dev/null | grep -qi true
if [ "$ALLOW_UNCONNECTED" = false ]; then
  hermes doctor
  hermes gateway status
  hermes mcp list | grep -q funding-director-core
fi
echo "Funding Director Orgo verification passed."
