#!/usr/bin/env python3
"""
Golden Game — Telegram reminder bot.

Reads watchlist.txt (the day's matches, with start times in Helsinki/EEST),
and sends Telegram reminders:
  1. A morning summary listing all of today's matches to watch.
  2. A per-match "starting soon" ping a short time before each match begins.

Runs statelessly on GitHub Actions cron. A small JSON state file
(state/sent.json) records what has already been sent today, so nothing
is sent twice even though the workflow fires every 15 minutes.

Environment variables (set as GitHub Secrets):
  TELEGRAM_BOT_TOKEN   – from @BotFather
  TELEGRAM_CHAT_ID     – your numeric chat id
Optional:
  LEAD_MINUTES         – how many minutes before a match to ping (default 15)
  SUMMARY_HOUR         – local hour to send the morning summary (default 9)
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

# ─── Config ───
TZ = ZoneInfo("Europe/Helsinki")          # your timezone (EEST in summer)
LEAD_MINUTES = int(os.environ.get("LEAD_MINUTES", "15"))
SUMMARY_HOUR = int(os.environ.get("SUMMARY_HOUR", "9"))
WATCHLIST_FILE = "watchlist.txt"
STATE_FILE = "state/sent.json"

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

TIME_RE = re.compile(r"^\s*([0-2]?\d[:.][0-5]\d)\b")


def send_telegram(text):
    """Send a message to the configured Telegram chat."""
    if not TOKEN or not CHAT_ID:
        print("ERROR: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set.")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=20)
        if r.status_code == 200:
            print(f"Sent: {text[:60]!r}...")
            return True
        print(f"Telegram API error {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"Telegram send failed: {e}")
        return False


def parse_watchlist():
    """Return a list of dicts: {time:'HH:MM', desc:'...', id:'...'}."""
    if not os.path.exists(WATCHLIST_FILE):
        print(f"No {WATCHLIST_FILE} found.")
        return []
    matches = []
    with open(WATCHLIST_FILE, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            m = TIME_RE.match(line)
            if not m:
                continue  # header / footer / note line — skip
            t = m.group(1).replace(".", ":")
            if len(t) == 4:
                t = "0" + t
            desc = line[m.end():].strip(" -–—\t")
            # strip a leading clock emoji if present
            desc = desc.replace("\u23f0", "").strip()
            mid = f"{t}|{desc[:30]}"
            matches.append({"time": t, "desc": desc, "id": mid})
    return matches


def load_state():
    today = date.today().isoformat()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") == today:
                return data
        except Exception:
            pass
    return {"date": today, "sent": []}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def main():
    now = datetime.now(TZ)
    matches = parse_watchlist()
    state = load_state()
    sent = set(state["sent"])
    did_something = False

    if not matches:
        print("Watchlist empty — nothing to do.")
        return

    # ── 1. Morning summary (once per day, after SUMMARY_HOUR) ──
    if "summary" not in sent and now.hour >= SUMMARY_HOUR:
        lines = [f"\U0001f3be <b>Golden Game — today's watchlist</b>",
                 f"{len(matches)} match{'es' if len(matches) != 1 else ''} to watch (times EEST):", ""]
        for mt in matches:
            lines.append(f"\u23f0 <b>{mt['time']}</b>  {mt['desc']}")
        lines.append("")
        lines.append("Back the better-ranked player if they win set 1 (no tiebreak).")
        if send_telegram("\n".join(lines)):
            sent.add("summary")
            did_something = True

    # ── 2. Per-match "starting soon" pings ──
    for mt in matches:
        if mt["id"] in sent:
            continue
        try:
            hh, mm = map(int, mt["time"].split(":"))
        except ValueError:
            continue
        start = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        mins_until = (start - now).total_seconds() / 60.0
        # fire if the match starts within the lead window (and hasn't already started long ago)
        if -2 <= mins_until <= LEAD_MINUTES:
            when = "now" if mins_until <= 1 else f"in ~{round(mins_until)} min"
            msg = (f"\U0001f3be <b>Starting {when}</b>  ({mt['time']} EEST)\n"
                   f"{mt['desc']}\n\n"
                   f"\u2705 If the favourite wins set 1 cleanly (no tiebreak) \u2014 place the back bet.")
            if send_telegram(msg):
                sent.add(mt["id"])
                did_something = True

    state["sent"] = sorted(sent)
    save_state(state)
    print("Done." if did_something else "No reminders due this run.")


if __name__ == "__main__":
    main()
