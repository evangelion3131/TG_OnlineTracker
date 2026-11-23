import asyncio
import os
import sys
from datetime import datetime, timedelta

import qrcode
from dotenv import load_dotenv
from telethon import TelegramClient, events, functions, types
from telethon.errors import FloodWaitError, SessionPasswordNeededError

load_dotenv("local.env", override=True)

SESSION_NAME = os.getenv("SESSION_NAME", "tracker")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
DUMP_CHAT = os.getenv("DUMP_CHAT", "").strip()
UPDATE_TIME = int(os.getenv("UPDATE_TIME", "10"))
LOG_FILE = "log.txt"
SEP = "-" * 56  # separator line, console only
YELLOW, RESET = "\033[1;33m", "\033[0m"


def to_int_if_possible(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


TARGET_REFS = [
    to_int_if_possible(v.strip())
    for v in (os.getenv("TARGET_USER", ""), os.getenv("TARGET_USER_2", ""))
    if v and v.strip()
]
DUMP_CHAT = to_int_if_possible(DUMP_CHAT) if DUMP_CHAT else None  # empty = don't send


class Target:
    def __init__(self, entity):
        self.id = entity.id
        self.name = f"@{entity.username}" if entity.username else (entity.first_name or str(entity.id))
        self.input = None
        self.online = False
        self.since = None      # when the current online session started
        self.last_kind = None  # status type: online / offline / recently ...


targets: list[Target] = []
overlap_start = None
overlap_total = timedelta(0)
overlap_count = 0

# bottom console block: separator + live polling line
live_text = ""
bottom_drawn = False


def fmt_td(td: timedelta) -> str:
    s = int(td.total_seconds())
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def log(text: str, mark: bool = False) -> None:
    """Write to log.txt and to the console above the separator (mark = yellow in console)."""
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} | {text}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

    shown = f"{YELLOW}{line}{RESET}" if mark else line
    if bottom_drawn:
        # erase the live line and the separator, print the entry, redraw the block
        sys.stdout.write(f"\r\033[K\033[A\033[K{shown}\n{SEP}\n{live_text}")
    else:
        sys.stdout.write(shown + "\n")
    sys.stdout.flush()


def draw_bottom() -> None:
    global bottom_drawn
    sys.stdout.write(SEP + "\n")
    sys.stdout.flush()
    bottom_drawn = True


def update_live(text: str) -> None:
    global live_text
    live_text = text
    sys.stdout.write(f"\r{text}\033[K")
    sys.stdout.flush()


def describe(status) -> str:
    if isinstance(status, types.UserStatusOnline):
        return "online"
    if isinstance(status, types.UserStatusOffline):
        seen = status.was_online.astimezone().strftime("%H:%M:%S")
        return f"offline (last seen {seen})"
    if isinstance(status, types.UserStatusRecently):
        return "recently (hidden by privacy settings)"
    if isinstance(status, types.UserStatusLastWeek):
        return "last_week (hidden by privacy settings)"
    if isinstance(status, types.UserStatusLastMonth):
        return "last_month (hidden by privacy settings)"
    return "unknown (hidden by privacy settings)"


async def set_state(client: TelegramClient, t: Target, online: bool, source: str, detail: str = "") -> bool:
    """Update a target's state and track joint online time. Returns True if the state changed."""
    global overlap_start, overlap_total, overlap_count

    if online == t.online:
        return False

    now = datetime.now()
    was_all = all(x.online for x in targets)
    t.online = online
    is_all = all(x.online for x in targets)

    lines = []  # what to send to DUMP_CHAT
    if online:
        t.since = now
        log(f"[{source}] {t.name} ONLINE")
        lines.append(f"{t.name} came online")
    else:
        dur = f", was online for {fmt_td(now - t.since)}" if t.since else ""
        t.since = None
        log(f"[{source}] {t.name} OFFLINE{detail}{dur}")
        lines.append(f"{t.name} went offline")

    if len(targets) > 1:
        if is_all and not was_all:
            overlap_start = now
            names = " + ".join(x.name for x in targets)
            log(f"★ ONLINE SIMULTANEOUSLY: {names}", mark=True)
            lines.append(f"★ both online: {names}")
        elif was_all and not is_all and overlap_start:
            dur = now - overlap_start
            overlap_total += dur
            overlap_count += 1
            msg = (f"★ joint online ended: {fmt_td(dur)} "
                   f"({overlap_start:%H:%M:%S}–{now:%H:%M:%S}), {t.name} left first")
            log(msg, mark=True)
            lines.append(msg)
            overlap_start = None

    if DUMP_CHAT:
        try:
            await client.send_message(DUMP_CHAT, "\n".join(lines))
        except Exception as e:
            log(f"Failed to send to DUMP_CHAT: {e!r}")
    return True


def summary() -> str:
    total, count = overlap_total, overlap_count
    if overlap_start:
        total += datetime.now() - overlap_start
        count += 1
    return f"Total joint online sessions: {count}, {fmt_td(total)} in total"


def show_qr(url: str) -> None:
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.print_ascii(invert=True)


async def login_by_qr(client: TelegramClient) -> None:
    qr = await client.qr_login()
    while True:
        print("\nOn your phone open Telegram: Settings → Devices → Link Desktop Device, then scan this QR code:")
        show_qr(qr.url)
        try:
            await qr.wait(timeout=30)
            return
        except asyncio.TimeoutError:
            await qr.recreate()  # a QR code lives ~30 s, generate a new one
        except SessionPasswordNeededError:
            await client.sign_in(password=input("Cloud password (2FA): "))
            return


async def main() -> None:
    global overlap_start

    if not TARGET_REFS:
        sys.exit("Set TARGET_USER in local.env (username without @, or numeric ID).")

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        await login_by_qr(client)

    # --- initialize targets ---
    now = datetime.now()
    for ref in TARGET_REFS:
        entity = await client.get_entity(ref)
        t = Target(entity)
        t.input = await client.get_input_entity(entity.id)
        t.online = isinstance(entity.status, types.UserStatusOnline)
        t.since = now if t.online else None
        t.last_kind = describe(entity.status).split()[0]
        targets.append(t)

        log(f"Tracking: {t.id} ({t.name}), current status: {describe(entity.status)}")
        if t.last_kind not in ("online", "offline"):
            log(f"⚠ {t.name}: exact status is hidden, check the privacy settings of both accounts")

    if len(targets) > 1 and all(x.online for x in targets):
        overlap_start = now
        log("★ both targets are already online at startup", mark=True)

    draw_bottom()
    by_id = {t.id: t for t in targets}

    # --- real-time events (work while there is a shared dialog/contact) ---
    @client.on(events.UserUpdate(chats=[t.id for t in targets]))
    async def on_update(event):
        if event.online is None:
            return
        uid = getattr(event, "user_id", None) or event.chat_id
        t = by_id.get(uid)
        if t is None:
            return
        detail = ""
        last_seen = getattr(event, "last_seen", None)
        if not event.online and last_seen:
            detail = f" (last seen {last_seen.astimezone():%H:%M:%S})"
        await set_state(client, t, event.online, "event", detail)

    # --- polling: one request for all targets ---
    inputs = [t.input for t in targets]
    while True:
        try:
            users = await client(functions.users.GetUsersRequest(inputs))
            parts = []
            for user in users:
                t = by_id.get(user.id)
                if t is None:
                    continue
                desc = describe(user.status)
                kind = desc.split()[0]
                online = isinstance(user.status, types.UserStatusOnline)

                detail = ""
                if isinstance(user.status, types.UserStatusOffline):
                    detail = f" (last seen {user.status.was_online.astimezone():%H:%M:%S})"

                changed = await set_state(client, t, online, "poll", detail)

                # status type changed without an online/offline change (e.g. offline -> recently)
                if not changed and kind != t.last_kind:
                    log(f"{t.name}: status {desc}")
                t.last_kind = kind

                parts.append(f"{t.name} {desc}")

            marker = "★ " if overlap_start else ""
            update_live(f"{datetime.now():%H:%M:%S} poll ok: {marker}" + " | ".join(parts))

        except FloodWaitError as e:
            log(f"FloodWait: waiting {e.seconds} s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            log(f"Error: {e!r}")

        await asyncio.sleep(UPDATE_TIME)


try:
    asyncio.run(main())
except KeyboardInterrupt:
    bottom_drawn = False  # print the summary as a plain line
    print()
    if len(targets) > 1:
        log(summary())
