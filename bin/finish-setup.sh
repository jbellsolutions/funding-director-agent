#!/usr/bin/env bash
# Friendly post-launch menu: channels, business tools, optional extras, finish.
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo
echo "Your Funding Director is hosted and running. Let's finish the useful connections."

while true; do
  cat <<'MENU'

  1. Connect Funding Machine, GoHighLevel, Calendar, inboxes, and files
  2. Add Slack, Telegram, iMessage, WhatsApp, or Discord
  3. Create the current Slack Agent-view manifest
  4. Review optional computer control
  5. All done
MENU
  read -r -p "Choose a number: " choice
  case "$choice" in
    1) "$BASE_DIR/bin/connect-tools.sh" ;;
    2) "$BASE_DIR/bin/connect-channels.sh" ;;
    3)
      # shellcheck disable=SC1091
      source "$BASE_DIR/bin/operator-lib.sh"
      operator_load_env
      operator_init_docker
      manifest="$(operator_generate_slack_manifest)"
      echo "Current Slack Agent-view manifest created at: $manifest"
      ;;
    4)
      cat <<'TEXT'

The Operator already has a private cloud browser. Giving a remote agent control
of your own Mac, browser profile, files, or desktop is a separate privilege.
Add it only for a specific need, with the smallest permissions possible, and
turn it off afterward. The first-run interview will record the use case before
recommending any local Computer Use connection.
TEXT
      ;;
    5)
      echo
      echo "All right — we're all done. Send 'hello' in your messaging app."
      echo "The Operator will offer quick start or guided personalization."
      break
      ;;
    *) echo "Choose a number from 1 through 5." ;;
  esac
done
