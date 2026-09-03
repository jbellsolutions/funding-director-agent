#!/usr/bin/env bash
# Immediately stop every Funding Director external write without stopping analysis.
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
STATE_DIR="$HERMES_HOME/funding-director/state"
STOP_FILE="$STATE_DIR/EXTERNAL_WRITES_STOPPED"
mkdir -p "$STATE_DIR"
reason="${*:-Owner emergency stop}"
timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
temporary="$(mktemp "$STATE_DIR/stop.XXXXXX")"
printf '%s | human-founder | %s\n' "$timestamp" "$reason" > "$temporary"
chmod 600 "$temporary"
mv "$temporary" "$STOP_FILE"
echo "External submissions and CRM writes are stopped. Analysis remains available."
