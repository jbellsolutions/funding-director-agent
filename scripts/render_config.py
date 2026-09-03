#!/usr/bin/env python3
"""Render the public Hermes template into one private per-owner config."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys


def scalar(value: str) -> str:
    """JSON strings are valid YAML scalars and safely escape user input."""
    return json.dumps(value, ensure_ascii=False)


def strip_block(text: str, name: str) -> str:
    start = f"# __{name}_START__"
    end = f"# __{name}_END__"
    lines = text.splitlines()
    output: list[str] = []
    skipping = False
    found_start = found_end = False
    for line in lines:
        if line.strip() == start:
            skipping = True
            found_start = True
            continue
        if line.strip() == end:
            skipping = False
            found_end = True
            continue
        if not skipping:
            output.append(line)
    if not (found_start and found_end):
        raise SystemExit(f"template block markers missing: {name}")
    return "\n".join(output) + "\n"


def keep_block(text: str, name: str) -> str:
    return text.replace(f"# __{name}_START__\n", "").replace(f"# __{name}_END__\n", "")


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: render_config.py TEMPLATE OUTPUT")
    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    text = source.read_text(encoding="utf-8")

    conditions = {
        "FIREWORKS": bool(os.getenv("FIREWORKS_API_KEY")),
        "DEEPSEEK": bool(os.getenv("DEEPSEEK_API_KEY")),
        "TOGETHER": bool(os.getenv("TOGETHER_API_KEY")),
        "COMPOSIO": bool(os.getenv("COMPOSIO_API_KEY")),
        "FUNDING_MACHINE": bool(os.getenv("FUNDING_MACHINE_API_KEY")),
        "TELEGRAM_HOME": bool(os.getenv("TELEGRAM_HOME_CHANNEL")),
        "SLACK_HOME": bool(os.getenv("SLACK_HOME_CHANNEL")),
    }
    for name, enabled in conditions.items():
        text = keep_block(text, name) if enabled else strip_block(text, name)

    if not any(conditions[name] for name in ("FIREWORKS", "DEEPSEEK", "TOGETHER")):
        text = text.replace("fallback_providers:\n\n", "fallback_providers: []\n\n", 1)

    replacements = {
        "__HERMES_MODEL__": scalar(os.getenv("HERMES_MODEL", "openai/gpt-5.6-luna")),
        "__AGENT_PERSONA__": scalar(os.getenv("AGENT_PERSONA", "concise")),
        "__SLACK_ENABLED__": "true" if os.getenv("SLACK_BOT_TOKEN") and os.getenv("SLACK_APP_TOKEN") else "false",
        "__TELEGRAM_ENABLED__": "true" if os.getenv("TELEGRAM_BOT_TOKEN") else "false",
        "__DISCORD_ENABLED__": "true" if os.getenv("DISCORD_BOT_TOKEN") else "false",
        "__BLUEBUBBLES_ENABLED__": "true" if os.getenv("BLUEBUBBLES_SERVER_URL") and os.getenv("BLUEBUBBLES_PASSWORD") else "false",
        "__TELEGRAM_HOME_CHANNEL__": scalar(os.getenv("TELEGRAM_HOME_CHANNEL", "")),
        "__SLACK_HOME_CHANNEL__": scalar(os.getenv("SLACK_HOME_CHANNEL", "")),
        "__COMPOSIO_API_KEY__": scalar(os.getenv("COMPOSIO_API_KEY", "")),
        "__FUNDING_MACHINE_AUTHORIZATION__": scalar(
            "Bearer " + os.getenv("FUNDING_MACHINE_API_KEY", "")
        ),
    }
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)

    leftovers = sorted({word for word in text.split() if "__" in word})
    if leftovers:
        raise SystemExit(f"unrendered placeholders: {', '.join(leftovers)}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    destination.chmod(0o600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
