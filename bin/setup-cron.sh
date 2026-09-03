#!/usr/bin/env bash
# Install the Operator jobs schedule (host cron). Run after the agent is up.
# jobs.py self-gates via state/<job>-<date>.done + flock, so the every-minute-
# within-the-hour lines are a safe retry-until-delivered, not 60 sends.
set -euo pipefail
BASE="__BASE_DIR__"
PY="$BASE/venv/bin/python3"

# jobs.py needs the Composio SDK in a host venv
if [ ! -x "$PY" ]; then
  python3 -m venv "$BASE/venv"
  "$BASE/venv/bin/pip" -q install --upgrade pip
  "$BASE/venv/bin/pip" -q install composio
fi
mkdir -p "$BASE/state" "$BASE/logs"

J="$PY $BASE/scripts/jobs/jobs.py"
NEW=$(cat <<CRON
* 8 * * * $J briefing >> $BASE/logs/jobs.log 2>&1
* 13 * * * $J triage >> $BASE/logs/jobs.log 2>&1
* 9 * * 1-5 $J standup >> $BASE/logs/jobs.log 2>&1
* 10 * * 1-5 $J reminders >> $BASE/logs/jobs.log 2>&1
* 17 * * 5 $J weekly >> $BASE/logs/jobs.log 2>&1
* 18 * * * $J learning >> $BASE/logs/jobs.log 2>&1
*/30 * * * * $J credits >> $BASE/logs/jobs.log 2>&1
CRON
)
( crontab -l 2>/dev/null | grep -vF "$BASE/scripts/jobs/jobs.py"; echo "$NEW" ) | crontab -
echo "✅ jobs cron installed. Test one now:  $J briefing"
