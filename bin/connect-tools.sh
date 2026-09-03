#!/usr/bin/env bash
# Connect optional business tools used around the funding workflow.
set -euo pipefail

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/operator-lib.sh"
operator_load_env
operator_init_docker

echo
echo "Connect Funding Machine, GoHighLevel, and supporting business apps"
echo "No password or token will be printed by this helper."

while true; do
  cat <<'MENU'

  1. Show connection status
  2. Connect My Funding Machine (read-only)
  3. Connect GoHighLevel (one location, guarded writes)
  4. Connect Composio for Calendar, Gmail, Outlook, files, and business apps
  5. Test the browser tool
  6. Finish
MENU
  read -r -p "Choose a number: " choice
  case "$choice" in
    1)
      operator_hermes mcp list
      ;;
    2)
      echo "Create a dedicated read-only AI key in My Funding Machine. Keys begin fmk_."
      key="$(operator_secret "Paste the fmk_ Funding Machine key")"
      [[ "$key" == fmk_* ]] || operator_fail "the Funding Machine key must begin with fmk_"
      operator_save_value FUNDING_MACHINE_API_KEY "$key"
      unset key
      operator_refresh
      echo "Funding Machine is connected read-only. First test: list accessible locations."
      ;;
    3)
      echo "Create a sub-account Private Integration Token in GoHighLevel."
      echo "Grant only the required contacts and opportunities scopes."
      token="$(operator_secret "Paste the pit- Private Integration Token")"
      [[ "$token" == pit-* ]] || operator_fail "the GoHighLevel token must begin with pit-"
      read -r -p "Paste the exact GoHighLevel Location ID: " location
      [[ "$location" =~ ^[A-Za-z0-9_-]{8,80}$ ]] || operator_fail "that Location ID is not valid"
      operator_save_value GHL_API_KEY "$token"
      operator_save_value GHL_LOCATION_ID "$location"
      unset token location
      operator_refresh
      echo "GoHighLevel is connected through the guarded funding core."
      echo "First test: list pipelines or search one approved contact; do not change it."
      ;;
    4)
      if [ -z "${COMPOSIO_API_KEY:-}" ]; then
        echo "Open https://app.composio.dev and create a consumer API key."
        key="$(operator_secret "Paste the Composio consumer key")"
        [ -n "$key" ] || operator_fail "the Composio key cannot be blank"
        operator_save_value COMPOSIO_API_KEY "$key"
        operator_refresh
        COMPOSIO_API_KEY=$key
      fi
      cat <<'TEXT'

Composio is installed. In its dashboard, connect only the accounts you want:
Google Calendar, Gmail or Outlook, Drive/Docs/Sheets, Notion, CRM, or others.

First safe tests to send the Operator:
  Read my next three calendar events. Do not change anything.
  List three recent inbox subject lines. Do not send or change anything.
TEXT
      ;;
    5)
      echo "Testing the local Super Browser route..."
      operator_docker exec "${AGENT_NAME:-funding-director}" \
        /opt/super-browser/.venv/bin/python -m super_browser.cli doctor
      ;;
    6)
      echo "Business-tool setup is finished."
      break
      ;;
    *) echo "Choose a number from 1 through 6." ;;
  esac
done
