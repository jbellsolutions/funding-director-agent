#!/usr/bin/env python3
"""
Create "The Operator (Voice)" ElevenLabs agent — schema modeled on the LIVE API
(inspected from an existing working agent, 2026-07-15). Reads all secrets from
__BASE_DIR__/.env. Prints agent_id + hosted link. Reports each step's error.
"""
import json, os, sys, urllib.request, urllib.error

def env(key, default=""):
    for line in open("__BASE_DIR__/.env"):
        line = line.strip()
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default

XI = env("ELEVENLABS_API_KEY")
RELAY_TOKEN = env("RELAY_TOKEN")
COMPOSIO_KEY = env("COMPOSIO_API_KEY")
COMPOSIO_USER = env("COMPOSIO_USER_ID")
MCP_URL = ("https://backend.composio.dev/v3/mcp/__COMPOSIO_MCP_SERVER_ID__/mcp"
           "?include_composio_helper_actions=true&user_id=" + COMPOSIO_USER)
API = "https://api.elevenlabs.io"

def call(method, path, body=None):
    req = urllib.request.Request(API + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"xi-api-key": XI, "Content-Type": "application/json"}, method=method)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=40).read() or b"{}"), None
    except urllib.error.HTTPError as e:
        return None, "%s %s" % (e.code, e.read().decode()[:600])

SYSTEM_PROMPT = """You are The Operator — Justin's always-on business operations partner, on a live voice call.

VOICE STYLE: Speak in 1-3 short sentences. No lists, no markdown, no reading URLs or IDs aloud. Direct and grounded — lead with the answer, then at most one detail.

YOUR TOOLS:
- You have direct integration tools for live data — unread email, calendar, Linear issues, Notion. Use them for quick lookups and to take actions on those apps.
- ask_the_operator is your LONG-TERM BRAIN (memory, vault, business context, ongoing projects, and anything multi-step). Route to it whenever the answer depends on remembered context or on doing real work. It already speaks a short "checking" line for you.
- Before anything that sends, writes, changes, or deletes, say plainly what you're about to do and get a spoken yes first.

If a task needs more than a minute, tell Justin you'll finish it and post the result in his Slack DM (ask_the_operator handles that). Never read secrets, tokens, or IDs out loud."""

# ── 1) standalone webhook tool: ask_the_operator ─────────────────────────────
tool_body = {"tool_config": {
    "type": "webhook",
    "name": "ask_the_operator",
    "description": ("Ask The Operator's main brain (long-term memory, vault, business context, "
                    "project status) or have it perform a multi-step action. Pass the user's "
                    "request as `query`, verbatim, plus any context you already gathered."),
    "response_timeout_secs": 60,
    "disable_interruptions": True,
    "interruption_mode": "disable_during_tool_and_turn",
    "pre_tool_speech": "force",
    "api_schema": {
        "url": "https://__VOICE_DOMAIN__/ask",
        "method": "POST",
        "request_headers": {"Authorization": "Bearer " + RELAY_TOKEN},
        "request_body_schema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string",
                          "description": "The user's request, verbatim, plus any needed context."}
            },
        },
        "content_type": "application/json",
    },
}}
tool, err = call("POST", "/v1/convai/tools", tool_body)
if err:
    print("TOOL_ERROR:", err); sys.exit(1)
tool_id = tool.get("id") or (tool.get("tool_config") or {}).get("id")
print("TOOL_ID:", tool_id)

# ── 2) Composio MCP server ───────────────────────────────────────────────────
mcp_id = None
for shape in (
    {"config": {"url": MCP_URL, "name": "composio-operator", "transport": "STREAMABLE_HTTP",
                "approval_policy": "auto_approve_all", "request_headers": {"x-api-key": COMPOSIO_KEY}}},
    {"url": MCP_URL, "name": "composio-operator", "transport": "STREAMABLE_HTTP",
     "approval_policy": "auto_approve_all", "request_headers": {"x-api-key": COMPOSIO_KEY}},
):
    mcp, err = call("POST", "/v1/convai/mcp-servers", shape)
    if not err:
        mcp_id = mcp.get("id") or (mcp.get("config") or {}).get("id"); break
    last_mcp_err = err
print("MCP_ID:", mcp_id or ("FAILED: " + last_mcp_err))

# ── 3) the agent ─────────────────────────────────────────────────────────────
prompt = {"prompt": SYSTEM_PROMPT, "llm": "gpt-4o-mini", "temperature": 0.4,
          "tool_ids": [tool_id]}
if mcp_id:
    prompt["mcp_server_ids"] = [mcp_id]
agent_body = {
    "name": "The Operator (Voice)",
    "conversation_config": {
        "agent": {"first_message": "Operator here — what do you need?",
                  "language": "en", "prompt": prompt},
        "tts": {"voice_id": "__ELEVENLABS_VOICE_ID__", "model_id": "eleven_flash_v2"},
    },
    "platform_settings": {"auth": {"enable_auth": False,
                                   "allowlist": [{"hostname": "__VOICE_DOMAIN__"}]}},
}
agent, err = call("POST", "/v1/convai/agents/create", agent_body)
if err:
    print("AGENT_ERROR:", err); sys.exit(1)
agent_id = agent.get("agent_id")
print("AGENT_ID:", agent_id)

link, err = call("GET", "/v1/convai/agents/%s/link" % agent_id)
print("LINK:", json.dumps(link) if link else err)
