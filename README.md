# TG Online Tracker

A small Telegram userbot that watches the online status of one or two accounts, logs every change to `log.txt`, optionally sends notifications to a chat, and marks the moments when **both tracked accounts are online at the same time**.

Built with [Telethon](https://github.com/LonamiWebs/Telethon). Login is done with a QR code, so no confirmation code is needed.

## Features

- Tracks one or two Telegram accounts
- Real-time updates via Telegram events, plus polling as a fallback
- Every change is written to `log.txt` with a timestamp
- Shows how long each online session lasted
- Detects **joint online** periods of both targets, with start, end, duration and who left first (highlighted with `★`)
- Optional notifications to Saved Messages or any chat
- Live console view: log entries scroll above a separator line, a single polling line is updated below it
- Summary of joint online time on `Ctrl+C`
- Warns you when an account's exact status is hidden by privacy settings

## Requirements

- Python 3.9 or newer
- A Telegram account to run the bot from
- Telegram API credentials (`API_ID` and `API_HASH`)

## Setup

### 1. Get API credentials

1. Open <https://my.telegram.org> and log in with the phone number of the account that will run the bot.
2. Go to **API development tools** and create an application (title and short name can be anything).
3. Copy the `api_id` (a number) and `api_hash` (a string).

### 2. Install dependencies

With [uv](https://github.com/astral-sh/uv):

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Or with plain pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

Copy the example config and fill it in:

```bash
cp local.env.example local.env
```

| Variable | Required | Description |
|---|---|---|
| `SESSION_NAME` | no | Name of the session file (default `tracker`, creates `tracker.session`) |
| `API_ID` | yes | Numeric API ID from my.telegram.org |
| `API_HASH` | yes | API hash from my.telegram.org |
| `TARGET_USER` | yes | Account to track: username without `@`, or numeric user ID |
| `TARGET_USER_2` | no | Second account. If set, joint online tracking is enabled |
| `DUMP_CHAT` | no | Where to send notifications: `me` (Saved Messages), a username, or a numeric chat ID. Empty = no notifications |
| `UPDATE_TIME` | no | Polling interval in seconds (default `10`) |

### 4. Run

Run it from the project folder (the config and `log.txt` are read and written in the current directory):

```bash
python bot.py
```

On the first run a QR code is printed in the terminal. On your phone open
**Telegram → Settings → Devices → Link Desktop Device** and scan it. If the account has two-step verification, you will be asked for the cloud password. The login is saved in `tracker.session`, so you only do this once.

Stop the bot with `Ctrl+C`.

## Output

Console:

```
2026-11-23 16:10:02 | Tracking: 7313390398 (@first), current status: offline (last seen 15:40:12)
2026-11-23 16:10:02 | Tracking: 5551234567 (@second), current status: online
2026-11-23 16:10:07 | [event] @first ONLINE
2026-11-23 16:10:07 | ★ ONLINE SIMULTANEOUSLY: @first + @second
2026-11-23 16:12:41 | [event] @second OFFLINE (last seen 16:12:41), was online for 5m 12s
2026-11-23 16:12:41 | ★ joint online ended: 2m 34s (16:10:07–16:12:41), @second left first
--------------------------------------------------------
16:12:50 poll ok: @first online | @second offline (last seen 16:12:41)
```

- `[event]` means the change came from a real-time Telegram update, `[poll]` means it was caught by polling.
- Lines with `★` are joint online events (yellow in the console).
- The separator and the live polling line exist only in the console. `log.txt` contains just the entries.

Search joint online events in the log:

```bash
grep ★ log.txt
```

## Privacy settings (important)

Telegram only reveals an exact online status when privacy settings allow it:

1. **Target account:** *Settings → Privacy and Security → Last Seen & Online* must show the status to the account running the bot (set it to *Everybody*, or add the bot account to the *Always share with* exceptions).
2. **Bot account:** Telegram applies reciprocity. If you hide your own last seen, you will not see other people's exact status either (unless you have Telegram Premium). Set it to *Everybody* or add exceptions.

If the status is hidden you will see `recently`, `last_week` or `last_month` instead of `online`/`offline`, and the bot will print a warning at startup.

## Troubleshooting

**Status always shows `recently`**
See the privacy section above. Check both accounts.

**`ValueError: Cannot find any entity corresponding to ""`**
`DUMP_CHAT` is empty in an older version of the script. In this version, an empty `DUMP_CHAT` simply disables notifications. To send to Saved Messages use `DUMP_CHAT=me`.

**"Too many attempts" on my.telegram.org**
Telegram temporarily rate-limits the site. Wait a few hours (sometimes a day), turn off VPN or proxy, and try another browser or a mobile connection. Avoid repeating the attempts, as each one can extend the block.

**Events do not arrive, only `[poll]` entries**
Real-time events are only delivered for accounts that share a dialog or contact with the bot account. Polling still works for everyone, with a delay of up to `UPDATE_TIME` seconds.

**`FloodWait` messages**
Telegram asked the bot to slow down. The bot waits automatically. Increase `UPDATE_TIME` if it happens often.

**QR code is not scannable**
Make the terminal window larger or reduce the font size. The QR code refreshes every 30 seconds.

## Security notes

- `tracker.session` gives **full access to the Telegram account**. Treat it like a password and never commit or share it.
- `local.env` contains your API credentials. Never commit it.
- Both are already listed in `.gitignore`. Commit `local.env.example` instead.
- If a session is leaked, end it in *Telegram → Settings → Devices*.

## Responsible use

Use this tool only on accounts you own, or with the explicit consent of the person you are tracking. Online-status monitoring can be invasive, and the legal rules differ between countries.

## Project files

| File | Purpose |
|---|---|
| `bot.py` | The tracker |
| `requirements.txt` | Python dependencies |
| `local.env.example` | Config template |
| `.gitignore` | Keeps secrets, sessions and logs out of git |
