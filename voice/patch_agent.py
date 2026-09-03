#!/usr/bin/env python3
"""Add fast direct-Composio webhook tools to the voice agent + tighten routing prompt."""
import json, sys, urllib.request, urllib.error

def env(k):
    for l in open("__BASE_DIR__/.env"):
        if l.strip().startswith(k+"="): return l.strip().split("=",1)[1]
    return ""

XI = env("ELEVENLABS_API_KEY"); RELAY = env("RELAY_TOKEN")
import os
AGENT = os.environ.get("AGENT_ID") or "__AGENT_ID__"
API = "https://api.elevenlabs.io"

def call(method, path, body=None):
    req = urllib.request.Request(API+path, data=json.dumps(body).encode() if body is not None else None,
        headers={"xi-api-key": XI, "Content-Type": "application/json"}, method=method)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=40).read() or b"{}"), None
    except urllib.error.HTTPError as e:
        return None, "%s %s" % (e.code, e.read().decode()[:400])

def fast_tool(name, desc, path):
    body = {"tool_config": {
        "type": "webhook", "name": name, "description": desc,
        "response_timeout_secs": 15, "pre_tool_speech": "auto",
        "api_schema": {
            "url": "https://__VOICE_DOMAIN__" + path, "method": "POST",
            "request_headers": {"Authorization": "Bearer " + RELAY},
            "request_body_schema": {"type": "object", "required": [], "properties": {}},
            "content_type": "application/json",
        }}}
    t, err = call("POST", "/v1/convai/tools", body)
    if err: print("TOOL", name, "ERROR", err); sys.exit(1)
    tid = t.get("id") or (t.get("tool_config") or {}).get("id")
    print("tool", name, "->", tid)
    return tid

ids = [
    fast_tool("get_unread_email", "Get the count and top senders/subjects of Justin's UNREAD email right now. Use for any 'do I have email / unread / who emailed me' question. Fast.", "/tool/email"),
    fast_tool("get_calendar_today", "Get Justin's upcoming calendar events. Use for any 'what's on my calendar / next meeting / am I free' question. Fast.", "/tool/calendar"),
    fast_tool("get_linear_issues", "Get Justin's open Linear issues (counts, due dates, top titles). Use for any 'what's on my plate / linear / issues / tasks / overdue' question. Fast.", "/tool/linear"),
]

# fetch current agent → keep existing tool_ids (ask_the_operator) + append fast tools
agent, err = call("GET", "/v1/convai/agents/%s" % AGENT)
if err: print("GET agent ERROR", err); sys.exit(1)
pr = agent["conversation_config"]["agent"]["prompt"]
existing = pr.get("tool_ids") or []
merged = list(dict.fromkeys(existing + ids))

NEW_PROMPT = """You are The Operator — Justin's always-on business operations partner, on a live voice call.

VOICE STYLE: 1-3 short spoken sentences. No lists, no markdown, no reading URLs or IDs aloud. Lead with the answer.

ROUTING (important for speed):
- Email / unread / who emailed → get_unread_email.
- Calendar / next meeting / am I free → get_calendar_today.
- Linear / my plate / tasks / issues / overdue → get_linear_issues.
  (Those three are fast — prefer them for lookups.)
- Memory, business context, ongoing projects, multi-step work, or TAKING AN ACTION (sending, changing, drafting) → ask_the_operator. It's your long-term brain; trust and speak its answer.
- Before anything that sends, writes, or changes something, say what you'll do and get a spoken yes.

If something needs more than a minute, say you'll finish it and post the result in Justin's Slack DM. Never read secrets, tokens, or IDs aloud."""

upd, err = call("PATCH", "/v1/convai/agents/%s" % AGENT,
    {"conversation_config": {"agent": {"prompt": {"tool_ids": merged, "prompt": NEW_PROMPT}}}})
if err: print("PATCH ERROR", err); sys.exit(1)
print("AGENT PATCHED — tool_ids:", merged)
