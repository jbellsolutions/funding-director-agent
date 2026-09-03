#!/usr/bin/env python3
"""
Operator — scheduled ops jobs (briefing/triage/standup/reminders/weekly/credits/learning).

Self-contained by design: talks to Slack/Telegram/OpenRouter over plain HTTPS and
to Composio via its SDK. No dependency on the chat gateway — reports deliver even
if OpenClaw is mid-restart.

Usage (driven by cron, see docs/setup.md):
    jobs.py briefing     # morning briefing  (marker-gated: retries all hour until delivered)
    jobs.py triage       # email triage      (marker-gated)
    jobs.py standup      # Linear standup digest (marker-gated)
    jobs.py reminders    # Linear overdue/due-soon sweep (marker-gated, weekdays)
    jobs.py weekly       # weekly progress report (marker-gated, Mondays)
    jobs.py credits      # OpenRouter credit watch (alerts under threshold)

Success semantics: a job writes __BASE_DIR__/state/<job>-<date>.done ONLY
after delivery succeeds. Cron fires every minute inside the job's hour; the marker
makes completed runs no-ops. A failing job therefore retries ~60x with alerts,
instead of silently skipping the day (the failure mode that hid 2 weeks of missed
silent skips).
"""
import json, os, sys, time, urllib.request
from datetime import datetime

BASE = "__BASE_DIR__"
ENV_PATH = BASE + "/.env"
STATE = BASE + "/state"
VAULT = BASE + "/vault"

def load_env(path=ENV_PATH):
    env = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return env

ENV = load_env()
def cfg(key, default=""):
    return ENV.get(key) or os.environ.get(key) or default

SLACK_BOT_TOKEN = cfg("SLACK_BOT_TOKEN")
BRIEF_SLACK_CHANNEL = cfg("BRIEF_SLACK_CHANNEL")
TG_TOKEN = cfg("TELEGRAM_BOT_TOKEN")
TG_CHAT = cfg("TELEGRAM_CHAT_ID")
OR_KEY = cfg("HERMES_OPENROUTER_API_KEY") or cfg("OPENCLAW_OPENROUTER_API_KEY")
# Credit-watch must check EVERY distinct OpenRouter key. The chat gateway (OpenClaw)
# and the jobs/orchestrator (Hermes) can use different keys; if only one is checked,
# the other can run dry while the alarm reports healthy (the exact Jul-11 outage class).
OR_KEYS = []
for _n in ("HERMES_OPENROUTER_API_KEY", "OPENCLAW_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"):
    _v = cfg(_n)
    if _v and _v not in [k for _, k in OR_KEYS]:
        OR_KEYS.append((_n, _v))
if not OR_KEYS and OR_KEY:
    OR_KEYS = [("OPENROUTER", OR_KEY)]
COMPOSIO_KEY = cfg("COMPOSIO_API_KEY")
COMPOSIO_USER = cfg("COMPOSIO_USER_ID")
MODEL = cfg("JOBS_MODEL", "deepseek/deepseek-v4-flash")
FALLBACK = cfg("JOBS_FALLBACK_MODEL", "z-ai/glm-5.2")
THRESHOLD = float(cfg("CREDIT_ALERT_THRESHOLD", "10"))

os.makedirs(STATE, exist_ok=True)

def log(msg):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg), flush=True)
    try:
        os.makedirs(VAULT + "/daily-logs", exist_ok=True)
        with open(VAULT + "/daily-logs/" + datetime.now().strftime("%Y-%m-%d") + ".md", "a") as f:
            f.write("- [%s] jobs: %s\n" % (datetime.now().strftime("%H:%M"), msg))
    except Exception:
        pass

# ── delivery ─────────────────────────────────────────────────────────────────
def _http(url, payload=None, headers=None, timeout=20):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers or {})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

def slack_post(text, channel=None):
    channel = channel or BRIEF_SLACK_CHANNEL
    if not (SLACK_BOT_TOKEN and channel):
        return False
    try:
        r = _http("https://slack.com/api/chat.postMessage",
                  {"channel": channel, "text": text},
                  {"Authorization": "Bearer " + SLACK_BOT_TOKEN,
                   "Content-Type": "application/json"})
        if not r.get("ok"):
            log("slack_post error: " + str(r.get("error")))
        return bool(r.get("ok"))
    except Exception as e:
        log("slack_post exception: " + str(e)[:120])
        return False

def tg_send(text):
    if not (TG_TOKEN and TG_CHAT):
        return False
    for attempt in range(3):
        try:
            _http("https://api.telegram.org/bot%s/sendMessage" % TG_TOKEN,
                  {"chat_id": TG_CHAT, "text": text},
                  {"Content-Type": "application/json"})
            return True
        except Exception as e:
            if attempt == 2:
                log("tg_send failed: " + str(e)[:120])
            time.sleep(3)
    return False

def deliver(text):
    """Owner delivery = Slack DM + Telegram. Success if EITHER lands (alert if one fails)."""
    s = slack_post(text)
    t = tg_send(text)
    if s and not t:
        log("delivered to Slack only (Telegram failed)")
    if t and not s:
        log("delivered to Telegram only (Slack failed)")
    return s or t

# ── model ────────────────────────────────────────────────────────────────────
def complete(prompt, max_tokens=1400):
    for m in (MODEL, FALLBACK):
        try:
            d = _http("https://openrouter.ai/api/v1/chat/completions",
                      {"model": m, "max_tokens": max_tokens,
                       "messages": [{"role": "user", "content": prompt}]},
                      {"Authorization": "Bearer " + OR_KEY,
                       "Content-Type": "application/json"}, timeout=110)
            out = ((d.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
            if out:
                return out
            log("empty completion from " + m)
        except Exception as e:
            log("completion error %s: %s" % (m, str(e)[:120]))
    return ""

# ── composio tools ───────────────────────────────────────────────────────────
_composio = None
def composio():
    global _composio
    if _composio is None:
        from composio import Composio
        _composio = Composio(api_key=COMPOSIO_KEY)
    return _composio

def tool(slug, args):
    try:
        r = composio().tools.execute(slug, arguments=args, user_id=COMPOSIO_USER,
                                     dangerously_skip_version_check=True)
        d = r if isinstance(r, dict) else getattr(r, "__dict__", {})
        if d.get("successful") or d.get("successfull"):
            return d.get("data")
        log("composio %s error: %s" % (slug, str(d.get("error"))[:120]))
    except Exception as e:
        log("composio %s exception: %s" % (slug, str(e)[:120]))
    return None

def fetch_unread_emails(n=12):
    data = tool("GMAIL_FETCH_EMAILS", {"max_results": n, "query": "is:unread in:inbox"})
    out = []
    if isinstance(data, dict):
        for m in (data.get("messages") or [])[:n]:
            preview = m.get("preview")
            out.append({
                "from": m.get("sender") or m.get("from") or "",
                "subject": m.get("subject") or "(no subject)",
                "snippet": (preview.get("body") if isinstance(preview, dict) else None)
                           or m.get("snippet") or (m.get("messageText") or "")[:200],
            })
    return out

def fetch_calendar(n=10):
    data = tool("GOOGLECALENDAR_EVENTS_LIST", {"max_results": 50, "calendar_id": "primary"})
    out = []
    today = datetime.now().strftime("%Y-%m-%d")
    if isinstance(data, dict):
        for ev in (data.get("items") or []):
            st = ev.get("start") or {}
            start = st.get("dateTime") or st.get("date") or ""
            if start[:10] >= today:  # drop historical ghosts (2023 recurrences polluted briefings)
                out.append({"summary": ev.get("summary") or "(no title)", "start": start})
    return out[:n]

def fetch_linear_issues():
    """Active issues via Composio Linear toolkit.
    Returns a list on success ([] = genuinely no issues), or None if the tool CALL
    failed (Composio down, creds expired, bad slug). Callers MUST treat None as a
    failure to retry — never as an empty standup — so integration outages don't get
    silently marked done."""
    data = tool("LINEAR_LIST_LINEAR_ISSUES", {"first": 50})
    if data is None:
        return None  # tool call failed — distinct from an authenticated empty result
    issues = []
    if isinstance(data, dict):
        raw = data.get("issues") or data.get("nodes") or data.get("items") or []
        if isinstance(raw, dict):
            raw = raw.get("nodes") or []
        for i in raw:
            state = i.get("state")
            issues.append({
                "title": i.get("title") or "",
                "state": (state.get("name") if isinstance(state, dict) else state) or "",
                "due": i.get("dueDate") or "",
                "assignee": ((i.get("assignee") or {}).get("name")
                             if isinstance(i.get("assignee"), dict) else "") or "",
                "project": ((i.get("project") or {}).get("name")
                            if isinstance(i.get("project"), dict) else "") or "",
            })
    return issues

# ── marker gating ────────────────────────────────────────────────────────────
def done_today(job):
    return os.path.exists("%s/%s-%s.done" % (STATE, job, datetime.now().strftime("%Y-%m-%d")))

def mark_done(job):
    open("%s/%s-%s.done" % (STATE, job, datetime.now().strftime("%Y-%m-%d")), "w").write("ok\n")

# ── jobs ─────────────────────────────────────────────────────────────────────
def job_briefing():
    emails = fetch_unread_emails(12)
    events = fetch_calendar(10)
    email_txt = "\n".join("- %s | %s — %s" % (e["from"][:38], e["subject"][:60], e["snippet"][:90])
                          for e in emails) or "(none)"
    cal_txt = "\n".join("- %s — %s" % (ev["start"][:16], ev["summary"][:60]) for ev in events) or "(none)"
    prompt = ("Write a short morning briefing for a business owner as tight bullets. Cover, in "
              "order: unread email that needs attention (who/what), today's calendar, and anything "
              "requiring his response. Concise, no filler.\n\nUNREAD EMAIL:\n" + email_txt +
              "\n\nCALENDAR:\n" + cal_txt)
    out = complete(prompt)
    if not out:
        return False
    ok = deliver("☀️ *Morning Briefing* — " + datetime.now().strftime("%a %b %d") + "\n\n" + out)
    if ok:
        os.makedirs(VAULT + "/daily-logs", exist_ok=True)
        with open(VAULT + "/daily-logs/briefing-" + datetime.now().strftime("%Y-%m-%d") + ".md", "w") as f:
            f.write("# Briefing %s\n\n%s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M"), out))
        log("briefing delivered (emails=%d events=%d)" % (len(emails), len(events)))
    return ok

def job_triage():
    emails = fetch_unread_emails(18)
    if not emails:
        log("triage: no unread")
        return True
    listing = "\n".join("%d. %s | %s — %s" % (i + 1, e["from"][:40], e["subject"][:70], e["snippet"][:110])
                        for i, e in enumerate(emails))
    prompt = ("Triage these unread emails for the owner. Group as NEEDS REPLY (one-line suggested "
              "action each), FYI, and IGNORE/PROMO. Tight; surface only what matters.\n\n" + listing)
    out = complete(prompt)
    if not out:
        return False
    ok = deliver("📧 *Email Triage* — %d unread\n\n%s" % (len(emails), out))
    if ok:
        log("triage delivered (%d unread)" % len(emails))
    return ok

def job_standup():
    issues = fetch_linear_issues()
    if issues is None:
        log("standup: Linear fetch FAILED (Composio/creds) — will retry")
        return False
    if not issues:
        log("standup: no Linear issues (authenticated, genuinely empty)")
        return True
    listing = "\n".join("- [%s] %s%s%s" % (
        i["state"], i["title"][:70],
        (" · due " + i["due"]) if i["due"] else "",
        (" · @" + i["assignee"]) if i["assignee"] else "") for i in issues[:40])
    prompt = ("Write a daily standup digest from these Linear issues: what's IN PROGRESS, what's "
              "BLOCKED or stale, what's OVERDUE or due in 48h (call these out hard), and 1-3 "
              "suggested priorities for today. Tight bullets.\n\n" + listing)
    out = complete(prompt)
    if not out:
        return False
    ok = deliver("📋 *Daily Standup* — " + datetime.now().strftime("%a %b %d") + "\n\n" + out)
    if ok:
        log("standup delivered (%d issues)" % len(issues))
    return ok

def job_reminders():
    issues = fetch_linear_issues()
    if issues is None:
        log("reminders: Linear fetch FAILED (Composio/creds) — will retry")
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    soon = [i for i in issues if i["due"] and i["due"] <= today]
    if not soon:
        log("reminders: nothing overdue/due today")
        return True
    listing = "\n".join("- %s (due %s%s)" % (i["title"][:70], i["due"],
                        (", @" + i["assignee"]) if i["assignee"] else "") for i in soon[:20])
    ok = deliver("⏰ *Reminders — overdue / due today*\n\n" + listing)
    if ok:
        log("reminders delivered (%d items)" % len(soon))
    return ok

def job_weekly():
    issues = fetch_linear_issues()
    if issues is None:
        log("weekly: Linear fetch FAILED (Composio/creds) — will retry")
        return False
    if not issues:
        log("weekly: no Linear issues (authenticated, genuinely empty)")
        return True
    listing = "\n".join("- [%s] %s%s" % (i["state"], i["title"][:70],
                        (" · " + i["project"]) if i["project"] else "") for i in issues[:60])
    prompt = ("Write a weekly progress report from these Linear issues, grouped by project: "
              "shipped/completed, in flight, blocked, and next week's focus. Written so it could "
              "be forwarded to a client or manager with light editing. Professional, concise.\n\n" + listing)
    out = complete(prompt, max_tokens=1800)
    if not out:
        return False
    ok = deliver("📊 *Weekly Progress Report* — week of " + datetime.now().strftime("%b %d") + "\n\n" + out)
    if ok:
        log("weekly report delivered")
    return ok

def _check_one_credit(label, key):
    """Return remaining balance for one OpenRouter key, or None if the check failed."""
    try:
        d = _http("https://openrouter.ai/api/v1/credits", None,
                  {"Authorization": "Bearer " + key})
        data = d.get("data") or {}
        remaining = float(data.get("total_credits", 0)) - float(data.get("total_usage", 0))
        log("credits[%s] remaining: $%.2f" % (label, remaining))
        return remaining
    except Exception as e:
        log("credit check[%s] FAILED: %s" % (label, str(e)[:120]))
        return None

def job_credits():
    """Alert when ANY OpenRouter balance runs low — the missing alarm from the Jul 11
    outage. Checks every distinct key (OpenClaw + Hermes). Returns False if a check
    failed OR a low-balance alert could not be delivered, so cron keeps surfacing it."""
    ok_overall = True
    any_low_undelivered = False
    for label, key in OR_KEYS:
        remaining = _check_one_credit(label, key)
        flag = STATE + "/credit-alerted-" + label
        if remaining is None:
            ok_overall = False  # couldn't verify this key — do not go quiet
            continue
        if remaining < THRESHOLD:
            if not os.path.exists(flag) or time.time() - os.path.getmtime(flag) > 21600:
                msg = ("🚨 Business Operator: OpenRouter balance [%s] is $%.2f (threshold $%.0f). "
                       "Top up now or the agent goes brainless." % (label, remaining, THRESHOLD))
                # only silence the alarm once it has ACTUALLY reached someone
                if deliver(msg):
                    open(flag, "w").write(str(remaining))
                else:
                    any_low_undelivered = True
                    log("credit alert[%s] UNDELIVERED — not suppressing" % label)
        elif os.path.exists(flag):
            os.remove(flag)  # recovered — reset so the next dip re-alerts
    return ok_overall and not any_low_undelivered

def job_learning():
    """Distill the last few days of vault daily-logs into Reference/business-context.md
    so the agent's standing context compounds (the learning loop, restored on the new stack)."""
    import glob
    logs_dir = VAULT + "/daily-logs"
    files = sorted(glob.glob(logs_dir + "/2*.md"))[-4:]  # last ~4 days, skip briefing-*.md
    files = [f for f in files if "/briefing-" not in f]
    corpus = ""
    for f in files:
        try:
            corpus += "\n\n### %s\n%s" % (os.path.basename(f), open(f).read()[:4000])
        except Exception:
            pass
    if not corpus.strip():
        log("learning: no recent daily-logs")
        return True
    ref_dir = VAULT + "/Reference"
    os.makedirs(ref_dir, exist_ok=True)
    ref_path = ref_dir + "/business-context.md"
    prior = ""
    if os.path.exists(ref_path):
        prior = open(ref_path).read()[:6000]
    prompt = ("You maintain a durable business-context file for an operations agent. Given the "
              "PRIOR context and RECENT activity logs, output an updated business-context.md: "
              "durable facts, people, projects, preferences, and recurring commitments worth "
              "remembering. Merge — keep what's still true, add what's new, drop noise/one-offs. "
              "Return ONLY the file body in markdown.\n\n=== PRIOR ===\n" + (prior or "(none yet)") +
              "\n\n=== RECENT ACTIVITY ===\n" + corpus)
    out = complete(prompt, max_tokens=1800)
    if not out:
        return False
    with open(ref_path, "w") as f:
        f.write("# Business Context (auto-distilled %s)\n\n%s\n" %
                (datetime.now().strftime("%Y-%m-%d"), out))
    log("learning: business-context.md updated (%d source logs)" % len(files))
    return True

JOBS = {"briefing": job_briefing, "triage": job_triage, "standup": job_standup,
        "reminders": job_reminders, "weekly": job_weekly, "credits": job_credits,
        "learning": job_learning}

if __name__ == "__main__":
    import fcntl
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if name not in JOBS:
        print("usage: jobs.py [%s]" % "|".join(JOBS)); sys.exit(2)
    # Per-job lock: a job can run >60s (a model call alone waits up to 110s), so two
    # every-minute cron ticks can overlap. A non-blocking flock makes the second tick
    # a clean no-op instead of double-delivering / racing the marker + vault writes.
    lock_fh = open("%s/%s.lock" % (STATE, name), "w")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        sys.exit(0)  # another run of this job is already in progress
    try:
        if name == "credits":
            # not day-gated (runs every 30 min); exit nonzero on failure so cron/log surfaces it
            if not JOBS[name]():
                log("credits: check unhealthy or alert undelivered — exit 1")
                sys.exit(1)
        else:
            if done_today(name):
                sys.exit(0)
            if JOBS[name]():
                mark_done(name)
            else:
                log(name + " FAILED — will retry on next cron tick")
                sys.exit(1)
    finally:
        fcntl.flock(lock_fh, fcntl.LOCK_UN)
        lock_fh.close()
