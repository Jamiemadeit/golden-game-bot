# 🎾 Golden Game Telegram Reminders — Setup Guide

This sets up a **free, set-and-forget** bot that sends you Telegram reminders
before each match on your daily watchlist. It runs in the cloud on GitHub
Actions, so **your computer does not need to be on**.

You do this setup **once** (about 10 minutes). After that, your only daily job
is to paste the day's watchlist into one file (covered at the end).

---

## What you'll end up with

- A **morning summary** message listing all of today's matches to watch.
- A **"starting soon" ping** ~15 minutes before each match begins.
- Both arrive on your phone via Telegram, automatically, every day.

---

## Part 1 — Create your Telegram bot (3 min)

1. Open Telegram and search for **@BotFather** (the one with the blue checkmark).
2. Send it the message: `/newbot`
3. It asks for a **name** — type anything, e.g. `Golden Game Reminders`.
4. It asks for a **username** — must end in `bot`, e.g. `my_golden_game_bot`.
5. BotFather replies with a line like:
   ```
   Use this token to access the HTTP API:
   8123456789:AAH2x...long...string
   ```
   **Copy that whole token** and keep it safe. This is your `TELEGRAM_BOT_TOKEN`.

6. Now **start a chat with your new bot**: tap its link in BotFather's message,
   then press **Start** (or send it any message like "hi"). This step matters —
   the bot can't message you until you've messaged it first.

---

## Part 2 — Get your Chat ID (2 min)

1. In Telegram, search for **@userinfobot** and press **Start**.
2. It instantly replies with your details, including:
   ```
   Id: 123456789
   ```
   **Copy that number.** This is your `TELEGRAM_CHAT_ID`.

---

## Part 3 — Put the project on GitHub (3 min)

1. Go to **github.com** and sign in (create a free account if needed).
2. Click the **+** (top right) → **New repository**.
3. Name it `golden-game-bot`. Set it to **Public**
   *(Public repos get unlimited free Actions minutes — recommended. Your secret
   token is NOT stored in the code, so public is safe.)*
4. Click **Create repository**.
5. On the new repo page, click **uploading an existing file**.
6. Drag in **all the files from this package**, keeping the folder structure:
   ```
   send_reminders.py
   watchlist.txt
   state/sent.json
   .github/workflows/reminders.yml
   ```
   *(If GitHub's web uploader flattens folders, upload the loose files first,
   then use "Add file → Create new file" and type the path
   `.github/workflows/reminders.yml` to recreate it — paste the contents in.)*
7. Click **Commit changes**.

---

## Part 4 — Add your secrets (2 min)

This is where your bot token and chat ID go — stored securely, never in the code.

1. In your repo, click **Settings** (top menu).
2. Left sidebar: **Secrets and variables** → **Actions**.
3. Click **New repository secret**. Add the first one:
   - **Name:** `TELEGRAM_BOT_TOKEN`
   - **Secret:** paste the token from Part 1
   - Click **Add secret**
4. Click **New repository secret** again. Add the second:
   - **Name:** `TELEGRAM_CHAT_ID`
   - **Secret:** paste the number from Part 2
   - Click **Add secret**

---

## Part 5 — Turn it on and test (1 min)

1. In your repo, click the **Actions** tab.
2. If prompted "Workflows aren't being run on this repository," click
   **I understand my workflows, go ahead and enable them**.
3. Click **Golden Game Reminders** in the left list.
4. Click **Run workflow** → **Run workflow** (this runs it manually right now).
5. Wait ~30 seconds. Since the example `watchlist.txt` has today's matches and
   it's past 09:00, you should get the **morning summary** on Telegram. 🎉

If it doesn't arrive, see Troubleshooting below.

---

## ✅ Your daily routine (the only ongoing step)

Each morning, after you've built your watchlist (paste the day's matches to
Claude, get back the formatted list):

1. Go to your repo on GitHub (the phone app or website both work).
2. Open **watchlist.txt** → click the **pencil** (Edit) icon.
3. Delete the old contents, paste the new day's list. The format is exactly the
   "Copy for Telegram" output from the watchlist tool — lines like:
   ```
   12:30 Taylor Fritz (#9) vs Fabian Marozsan (#60) — gap 51
   14:00 Ben Shelton (#5) vs Ethan Quinn (#67) — gap 62
   ```
   Each line must **start with the time** (HH:MM, 24-hour, Helsinki time).
   Header/footer lines without a time are ignored automatically.
4. Click **Commit changes**.

That's it. The bot picks up the new list within 15 minutes and sends reminders
all day. No computer needed.

---

## How it works (so you can tweak it)

- **`reminders.yml`** runs the bot every 15 min from 08:00–20:00 UTC
  (= 11:00–23:00 Helsinki). Change the `cron` line to adjust hours.
- **`LEAD_MINUTES`** (in `reminders.yml`, default 15) = how many minutes before
  a match you get the "starting soon" ping.
- **`SUMMARY_HOUR`** (default 9) = the local hour after which the morning
  summary is sent.
- **`state/sent.json`** remembers what's already been sent today, so you never
  get duplicates. It resets automatically each day.

---

## Troubleshooting

**No message arrived after a manual run:**
- Check you pressed **Start** on your bot (Part 1, step 6). The bot literally
  cannot message you until you message it first.
- In **Actions**, click the run → open the **Send reminders** step and read the
  log. "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set" means a secret name is
  wrong (they must match exactly, all caps).
- "Telegram API error 400: chat not found" means the chat ID is wrong.

**Reminders are a few minutes late:**
- Normal. GitHub's free cron can be delayed several minutes under load. For
  "go watch this match" that's fine. The lead time absorbs it.

**Reminders stopped after a couple of weeks of not betting:**
- GitHub pauses scheduled workflows on repos with no recent activity. Your daily
  watchlist commit normally prevents this. If you take a long break, just commit
  anything (or press Run workflow once) to wake it back up.

**Want to stop reminders for a day:**
- Just leave `watchlist.txt` empty (or with only header lines). No matches = no
  pings.
