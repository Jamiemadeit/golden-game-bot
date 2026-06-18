
#!/usr/bin/env python3
"""
Golden Game — Telegram reminder bot (with inbox).

Two jobs, run together every 15 min on GitHub Actions:

  PHASE 1 — INBOX: poll Telegram for new messages you sent the bot.
    - If a message looks like a watchlist (lines starting with HH:MM),
      it's saved as today's watchlist and the bot confirms it.
    - Commands: /today, /clear, /help.

  PHASE 2 — REMINDERS: from the saved watchlist, send a "starting soon"
    ping ~15 min before each match.

State (state/sent.json) records the Telegram message offset (so messages
aren't re-read) and which reminders were already sent today.

Env (GitHub Secrets):
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Optional: LEAD_MINUTES (15), SUMMARY_HOUR (9)
"""

import os
import re
import json
import sys
from datetime import datetime, date
from zoneinfo import ZoneInfo

try:
    import requests
except ImportError:
    print("requests not installed; run: pip install requests")
    sys.exit(1)

TZ = ZoneInfo("Europe/Helsinki")
LEAD_MINUTES = int(os.environ.get("LEAD_MINUTES", "15"))
SUMMARY_HOUR = int(os.environ.get("SUMMARY_HOUR", "9"))
WATCHLIST_FILE = "watchlist.txt"
STATE_FILE = "state/sent.json"

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

TIME_RE = re.compile(r"^\s*([0-2]?\d[:.][0-5]\d)\b")
API = f"https://api.telegram.org/bot{TOKEN}"


# ─── Telegram helpers ───
def send_telegram(text):
    if not TOKEN or not CHAT_ID:
        print("ERROR: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set.")
        return False
    try:
        r = requests.post(f"{API}/sendMessage", data={
            "chat_id": CHAT_ID, "text": text,
            "parse_mode": "HTML", "disable_web_page_preview": True,
        }, timeout=20)
        if r.status_code == 200:
            print(f"Sent: {text[:50]!r}...")
            return True
        print(f"Telegram error {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"Send failed: {e}")
    return False


def get_updates(offset):
    try:
        params = {"timeout": 0, "allowed_updates": '["message"]'}
        if offset is not None:
            params["offset"] = offset
        r = requests.get(f"{API}/getUpdates", params=params, timeout=30)
        return r.json().get("result", [])
    except Exception as e:
        print(f"getUpdates failed: {e}")
        return []


# ─── Watchlist parsing ───
def is_match_line(line):
    return bool(TIME_RE.match(line))


def looks_like_watchlist(text):
    return sum(1 for ln in text.splitlines() if is_match_line(ln)) >= 1


def parse_watchlist_text(text):
    matches = []
    for raw in text.splitlines():
        line = raw.strip()
        m = TIME_RE.match(line)
        if not m:
            continue
        t = m.group(1).replace(".", ":")
        if len(t) == 4:
            t = "0" + t
        desc = line[m.end():].strip(" -–—\t").replace("\u23f0", "").strip()
        matches.append({"time": t, "desc": desc, "id": f"{t}|{desc[:30]}"})
    return matches


def read_watchlist_file():
    if not os.path.exists(WATCHLIST_FILE):
        return []
    with open(WATCHLIST_FILE, encoding="utf-8") as f:
        return parse_watchlist_text(f.read())


# ─── State ───
def load_state():
    today = date.today().isoformat()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") != today:
                data["date"] = today
                data["sent"] = []
            data.setdefault("sent", [])
            data.setdefault("update_offset", None)
            return data
        except Exception:
            pass
    return {"date": today, "sent": [], "update_offset": None}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ─── Phase 1: inbox ───
HELP_TEXT = (
    "\U0001f3be <b>Golden Game bot</b>\n\n"
    "Send me today's watchlist (the \"Copy for Telegram\" text) and I'll "
    "remind you before each match.\n\n"
    "Commands:\n"
    "\u2022 <b>/today</b> \u2014 show the current watchlist\n"
    "\u2022 <b>/clear</b> \u2014 clear today's watchlist (no reminders)\n"
    "\u2022 <b>/help</b> \u2014 this message"
)


def check_inbox(state):
    updates = get_updates(state.get("update_offset"))
    new_watchlist_text = None
    max_uid = state.get("update_offset")

    for u in updates:
        max_uid = u["update_id"] + 1
        msg = u.get("message")
        if not msg:
            continue
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if CHAT_ID and chat_id != CHAT_ID:
            continue
        text = (msg.get("text") or "").strip()
        if not text:
            continue

        low = text.lower()
        if low in ("/start", "/help"):
            send_telegram(HELP_TEXT)
        elif low in ("/today", "/list"):
            cur = read_watchlist_file()
            if cur:
                lines = [f"\U0001f3be <b>Today's watchlist</b> ({len(cur)} to watch):", ""]
                lines += [f"\u23f0 <b>{m['time']}</b>  {m['desc']}" for m in cur]
                send_telegram("\n".join(lines))
            else:
                send_telegram("No watchlist loaded yet. Send me today's matches.")
        elif low == "/clear":
            open(WATCHLIST_FILE, "w").close()
            state["sent"] = []
            send_telegram("\U0001f9f9 Watchlist cleared. No reminders today.")
        elif looks_like_watchlist(text):
            new_watchlist_text = text

    if max_uid is not None:
        state["update_offset"] = max_uid

    if new_watchlist_text is not None:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            f.write(new_watchlist_text.strip() + "\n")
        matches = parse_watchlist_text(new_watchlist_text)
        state["sent"] = ["summary"]
        state["date"] = date.today().isoformat()
        lines = [f"\u2705 <b>Loaded {len(matches)} match{'es' if len(matches)!=1 else ''} for today.</b>",
                 "I'll ping you ~15 min before each one.", ""]
        lines += [f"\u23f0 <b>{m['time']}</b>  {m['desc']}" for m in matches]
        send_telegram("\n".join(lines))
        return True
    return False


# ─── Phase 2: reminders ───
def send_due_reminders(state):
    now = datetime.now(TZ)
    matches = read_watchlist_file()
    if not matches:
        print("No watchlist — no reminders.")
        return
    sent = set(state["sent"])

    if "summary" not in sent and now.hour >= SUMMARY_HOUR:
        lines = [f"\U0001f3be <b>Golden Game — today's watchlist</b>",
                 f"{len(matches)} to watch (times EEST):", ""]
        lines += [f"\u23f0 <b>{m['time']}</b>  {m['desc']}" for m in matches]
        lines += ["", "Back the better-ranked player if they win set 1 (no tiebreak)."]
        if send_telegram("\n".join(lines)):
            sent.add("summary")

    for m in matches:
        if m["id"] in sent:
            continue
        try:
            hh, mm = map(int, m["time"].split(":"))
        except ValueError:
            continue
        start = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        mins = (start - now).total_seconds() / 60.0
        if -2 <= mins <= LEAD_MINUTES:
            when = "now" if mins <= 1 else f"in ~{round(mins)} min"
            send_telegram(
                f"\U0001f3be <b>Starting {when}</b>  ({m['time']} EEST)\n"
                f"{m['desc']}\n\n"
                f"\u2705 If the favourite wins set 1 cleanly (no tiebreak) \u2014 place the back bet."
            )
            sent.add(m["id"])

    state["sent"] = sorted(sent)


def main():
    state = load_state()
    check_inbox(state)
    send_due_reminders(state)
    save_state(state)
    print("Run complete.")


if __name__ == "__main__":
    main()
