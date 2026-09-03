#!/usr/bin/env bash
# Owner-only recovery from the Funding Director external-write emergency stop.
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
STOP_FILE="$HERMES_HOME/funding-director/state/EXTERNAL_WRITES_STOPPED"
if [ ! -f "$STOP_FILE" ]; then
  echo "External writes are already enabled."
  exit 0
fi
echo "Current stop record:"
sed -n '1p' "$STOP_FILE"
read -r -p "Type RESUME EXTERNAL WRITES to continue: " answer
[ "$answer" = "RESUME EXTERNAL WRITES" ] || { echo "Nothing changed."; exit 1; }
rm -f -- "$STOP_FILE"
echo "External writes are enabled. Existing approvals are not recreated."
