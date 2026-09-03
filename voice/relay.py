#!/usr/bin/env python3
"""
The Operator — voice relay.

Bridges the ElevenLabs voice agent to The Operator's REAL brain: forwards a
query into the hermes container (one-shot chat against /opt/data — same memory,
vault, persona, Composio MCP as Slack/Telegram) and returns the cleaned reply.

Endpoints (served on 127.0.0.1:8787 behind Caddy TLS):
  POST /ask     {"query": "..."}  + Authorization: Bearer $RELAY_TOKEN
  GET  /healthz

Design notes:
- Persistent voice session: session id stored at SESSION_FILE so the voice
  channel keeps continuity across calls (falls back to a fresh session and
  stores the new id, parsed from --pass-session-id output).
- 55s guard (ElevenLabs webhook timeout is 60s): on timeout we return a
  graceful spoken deferral. The prompt nudges hermes to answer briefly and to
  deliver anything long via Slack DM instead.
- Single-flight lock: one hermes turn at a time (voice is single-user).
"""
import json, os, re, subprocess, threading
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

BASE = "__BASE_DIR__"
SESSION_FILE = BASE + "/voice/session.id"
ENV_PATH = BASE + "/.env"
HERMES = ["docker", "exec", "__AGENT_NAME__", "/opt/hermes/.venv/bin/hermes"]
TIMEOUT_S = 55

def _env(key, default=""):
    try:
        for line in open(ENV_PATH):
            line = line.strip()
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return os.environ.get(key, default)

RELAY_TOKEN = _env("RELAY_TOKEN")

app = FastAPI()
_lock = threading.Lock()

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_NOISE = ("session_id:", "↻", "Query:", "Initializing", "Resume this session",
          "Session:", "Duration:", "Messages:", "─", "⚠", "Run 'hermes",
          "┊", "(tip)", "╭", "╰", "│")

def _clean(out: str) -> str:
    lines = []
    for raw in out.splitlines():
        line = _ANSI.sub("", raw).rstrip()
        if not line.strip():
            lines.append("")
            continue
        if any(line.lstrip().startswith(p) for p in _NOISE):
            continue
        lines.append(line)
    text = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", text)

def _session_id() -> str:
    try:
        return open(SESSION_FILE).read().strip()
    except FileNotFoundError:
        return ""

def _store_session(out: str):
    m = re.search(r"session_id:\s*([A-Za-z0-9_\-]+)", out)
    if m:
        os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
        with open(SESSION_FILE, "w") as f:
            f.write(m.group(1))

# Voice brain path uses a NON-reasoning model: it returns content immediately (grok-4.5
# and deepseek-v4-pro are reasoning models that emit empty content in this one-shot path).
# flash keeps Slack's pro untouched (that's set in hermes config; -m overrides only here).
VOICE_MODEL = "deepseek/deepseek-v4-flash"
VOICE_MODEL_ARGS = ["-m", VOICE_MODEL, "--provider", "openrouter"]

def ask_hermes(query: str) -> str:
    prompt = ("[voice call — answer in 1-3 short spoken sentences; if the task needs "
              "longer output or more than ~40s of work, say you'll post the result in "
              "the Slack DM and do that instead] " + query)
    sid = _session_id()
    cmd = HERMES + ["chat", "-Q", "-q", prompt] + VOICE_MODEL_ARGS + ["--pass-session-id"]
    if sid:
        cmd += ["--resume", sid]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return ("That one's taking me longer than a minute — I'll finish it and "
                "post the result in our Slack DM.")
    combined = (r.stdout or "") + "\n" + (r.stderr or "")
    _store_session(combined)
    reply = _clean(r.stdout or "")
    if not reply:
        # stale session can 404 on resume — retry once fresh
        if sid:
            try:
                os.remove(SESSION_FILE)
            except OSError:
                pass
            r2 = subprocess.run(HERMES + ["chat", "-Q", "-q", prompt] + VOICE_MODEL_ARGS + ["--pass-session-id"],
                                capture_output=True, text=True, timeout=TIMEOUT_S)
            _store_session((r2.stdout or "") + "\n" + (r2.stderr or ""))
            reply = _clean(r2.stdout or "")
        if not reply:
            return "I hit a snag processing that — try me again in a moment."
    return reply

# ── fast direct-Composio tools (bypass hermes — ~4-5s vs ~40s) ───────────────
# Reuse the proven jobs.py fetch_* helpers; they run in this same venv.
_jobs = None
def jobs():
    global _jobs
    if _jobs is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "jobs", "__BASE_DIR__/scripts/jobs/jobs.py")
        _jobs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_jobs)
    return _jobs

def _authed(request):
    return bool(RELAY_TOKEN) and request.headers.get("authorization", "") == "Bearer " + RELAY_TOKEN

def _speak_emails(items):
    if not items:
        return "Your inbox is clear — nothing unread."
    top = "; ".join("%s about %s" % (e["from"].split("<")[0].strip()[:30] or "someone",
                                     e["subject"][:50]) for e in items[:3])
    return "You have %d unread. Top: %s." % (len(items), top)

def _speak_calendar(items):
    if not items:
        return "Nothing on your calendar coming up."
    parts = []
    for ev in items[:4]:
        t = (ev.get("start") or "")[11:16] or (ev.get("start") or "")[:10]
        parts.append("%s at %s" % (ev.get("summary", "an event")[:40], t) if t else ev.get("summary", "an event")[:40])
    return "Next up: " + "; ".join(parts) + "."

def _speak_linear(items):
    if items is None:
        return "I couldn't reach Linear just now."
    if not items:
        return "No open Linear issues."
    overdue = [i for i in items if i.get("due")]
    lead = "%d open issues" % len(items)
    if overdue:
        lead += ", %d with due dates" % len(overdue)
    return lead + ". Top: " + "; ".join(i["title"][:45] for i in items[:3]) + "."

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.post("/tool/email")
async def tool_email(request: Request):
    if not _authed(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return {"response": _speak_emails(jobs().fetch_unread_emails(8))}

@app.post("/tool/calendar")
async def tool_calendar(request: Request):
    if not _authed(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return {"response": _speak_calendar(jobs().fetch_calendar(8))}

@app.post("/tool/linear")
async def tool_linear(request: Request):
    if not _authed(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return {"response": _speak_linear(jobs().fetch_linear_issues())}

@app.post("/ask")
async def ask(request: Request):
    if not _authed(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "bad json"}, status_code=400)
    query = (body.get("query") or "").strip()
    if not query:
        return JSONResponse({"error": "query required"}, status_code=400)
    with _lock:  # single-flight: voice is single-user (only the hermes path needs this)
        reply = ask_hermes(query)
    return {"response": reply}
