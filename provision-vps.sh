#!/usr/bin/env bash
# Prepare a fresh Ubuntu server, clone the repository, and hand off to setup.sh.
set -euo pipefail

REPOSITORY="${FUNDING_DIRECTOR_REPO:-https://github.com/jbellsolutions/funding-director-agent.git}"
DESTINATION="${FUNDING_DIRECTOR_DEST:-$HOME/funding-director}"

if [ "$(id -u)" -eq 0 ]; then
  ELEVATE=()
else
  ELEVATE=(sudo)
fi

if ! command -v git >/dev/null 2>&1; then
  "${ELEVATE[@]}" apt-get update -qq
  "${ELEVATE[@]}" apt-get install -y -qq git ca-certificates
fi

if [ -d "$DESTINATION/.git" ]; then
  git -C "$DESTINATION" pull --ff-only
else
  git clone "$REPOSITORY" "$DESTINATION"
fi

echo
echo "The setup files are ready at $DESTINATION."
echo "Run:"
echo "  cd $DESTINATION && ./setup.sh"
