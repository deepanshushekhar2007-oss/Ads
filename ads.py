import asyncio
import os
import time
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = TelegramClient("bot", API_ID, API_HASH)

# Mongo setup
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo.ads_bot
col = db.users

# Runtime storage
user_state = {}
temp_client = {}
admin_state = {}

# ✅ NEW (IMPORTANT)
login_cooldown = {}
active_logins = {}

ADMINS = [ADMIN_ID]

# ================= FORCE SUB ================= #

FORCE_CHANNELS = [
    "@SPIDY_W_S"
]

async def check_all_joined(user_id):
    not_joined = []

    for ch in FORCE_CHANNELS:
        try:
            await bot.get_permissions(ch, user_id)
        except:
            not_joined.append(ch)

    return not_joined


async def force_sub_msg(e, not_joined):
    buttons = []

    # ✅ buttons only (no text names)
    for ch in not_joined:
        buttons.append([Button.url("📢 Join Channel", f"https://t.me/{ch.strip('@')}")])

    buttons.append([Button.inline("✅ Joined", b"check_join")])

    await e.respond(
        "🚫 <b>Access Denied</b>\n\n"
        "👉 Please join required channels to continue.",
        buttons=buttons,
        parse_mode="html"
    )

# ================= DB FUNCTIONS ================= #

async def get_user(uid):
    data = await col.find_one({"_id": uid})
    
    if not data:
        data = {
            "_id": uid,
            "message": None,
            "groups": [],
            "selected": [],
            "target_mode": "All",
            "delay": 120,
            "running": False,
            "round": 0,
            "session": None,
            "is_banned": False,
            "phone": None
        }
        await col.insert_one(data)
    
    return data


async def update_user(uid, data):
    data.pop("_id", None)
    await col.update_one({"_id": uid}, {"$set": data})


# ================= MENU FUNCTION ================= #

def menu(d):
    phone = d.get("phone")
    phone_display = phone if phone else "❌ Not Added"

    txt = (
        "🌐 <b>ADS CONTROL PANEL</b> 🌐\n\n"
        f"👤 <b>Account:</b> {'✅ Connected' if d.get('session') else '❌ Not Connected'}\n"
        f"📱 <b>Number:</b> <code>{phone_display}</code>\n"
        f"📊 <b>Status:</b> {'▶️ Running' if d.get('running') else '⏹️ Stopped'}\n\n"
        "⚙️ <b>Settings:</b>\n"
        f"✉️ <b>Message:</b> {d.get('message') if d.get('message') else '❌ Not set'}\n"
        f"🎯 <b>Target Mode:</b> {d.get('target_mode')}\n"
        f"⏱️ <b>Delay:</b> {d.get('delay', 120)} sec\n"
        f"🔄 <b>Rounds Completed:</b> {d.get('round', 0)}\n\n"
        "💡 <i>Use the buttons below to manage your ads</i>"
    )

    buttons = [
        [Button.inline("➕ Add Account", b"add"), Button.inline("✉️ Message Menu", b"msg")],
        [Button.inline("🎯 Target Groups", b"target"), Button.inline("⏱️ Set Delay", b"time")],
        [Button.inline("▶️ Start Ads", b"start"), Button.inline("⏹️ Stop Ads", b"stop")],
        [Button.inline("🚪 Logout", b"logout")]
    ]

    return txt, buttons
# ================= PROFILE NAME ================= #

from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.users import GetFullUserRequest

# ✅ YOUR BRANDING
TAG = "@spidyadsbot"
BIO = "🚀 Powered by @spidyadsbot | Smart Ads Automation ⚡"


async def set_name(client):
    try:
        me = await client.get_me()

        first = me.first_name or ""

        # ✅ remove old tag safely
        clean = first.replace(TAG, "").strip()

        # ✅ always add at END
        new_first_name = f"{clean} {TAG}".strip()

        last = me.last_name or ""

        # ✅ NAME UPDATE (safe)
        if me.first_name != new_first_name:
            await client(UpdateProfileRequest(
                first_name=new_first_name,
                last_name=last
            ))

        # ✅ BIO UPDATE (STRONG FIX)
        full = await client(GetFullUserRequest(me.id))
        current_bio = (full.about or "").strip()

        if current_bio != BIO:
            await client(UpdateProfileRequest(about=BIO))
            await asyncio.sleep(1)  # telegram sync delay

            # ✅ RE-CHECK (important)
            full = await client(GetFullUserRequest(me.id))
            if (full.about or "").strip() != BIO:
                print("⚠️ Bio not updated, retrying...")
                await client(UpdateProfileRequest(about=BIO))

    except Exception as ex:
        print(f"⚠️ set_name failed: {ex}")


async def check_profile(client):
    try:
        me = await client.get_me()

        name = (me.first_name or "").strip()

        # ✅ MUST end with tag (strict match)
        if not name.endswith(TAG):
            return False

        full = await client(GetFullUserRequest(me.id))
        bio = (full.about or "").strip()

        # ✅ strict bio check
        if bio != BIO:
            return False

        return True

    except Exception as ex:
        print(f"⚠️ check_profile failed: {ex}")
        return False


# ================= START & ADMIN COMMANDS ================= #

@bot.on(events.NewMessage(pattern="/start"))
async def start(e):
    uid = e.sender_id

    # ✅ FORCE SUB CHECK
    not_joined = await check_all_joined(uid)
    if not_joined:
        return await force_sub_msg(e, not_joined)

    d = await get_user(uid)

    if d.get("is_banned"):
        return await e.reply("🚫 You are banned from using this bot")

    # ✅ SAFE PROFILE RESTORE
    if d.get("session"):
        try:
            client = TelegramClient(StringSession(d["session"]), API_ID, API_HASH)
            await client.start()

            try:
                if not await check_profile(client):
                    await set_name(client)
            except:
                pass

            await client.disconnect()

        except Exception as ex:
            print(f"⚠️ Restore error {uid}: {ex}")

    txt, btn = menu(d)
    await e.respond(txt, buttons=btn, parse_mode="html")


# ================= ADMIN ================= #

@bot.on(events.NewMessage(pattern=r'/ban (\d+)'))
async def ban_user(e):
    if e.sender_id not in ADMINS:
        return await e.reply("❌ You are not authorized to use this command")
    
    target_id = int(e.pattern_match.group(1))
    d = await get_user(target_id)

    d["is_banned"] = True
    await update_user(target_id, d)

    await e.reply(f"🚫 User {target_id} has been banned")


@bot.on(events.NewMessage(pattern=r'/unban (\d+)'))
async def unban_user(e):
    if e.sender_id not in ADMINS:
        return await e.reply("❌ You are not authorized to use this command")
    
    target_id = int(e.pattern_match.group(1))
    d = await get_user(target_id)

    d["is_banned"] = False
    await update_user(target_id, d)

    await e.reply(f"✅ User {target_id} has been unbanned")


# ================= CALLBACK QUERY HANDLER ================= #

from telethon.tl.functions.users import GetFullUserRequest

# ✅ PROFILE CHECK (OUTSIDE - IMPORTANT)
async def profile_ok(session_str):
    if not session_str:
        return False

    try:
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.start()

        me = await client.get_me()
        name = (me.first_name or "").strip()

        # ✅ must end with your tag
        if not name.endswith("@spidyadsbot"):
            return False

        full = await client(GetFullUserRequest(me.id))
        bio = (full.about or "").strip()

        if bio != "🚀 Powered by @spidyadsbot | Smart Ads Automation ⚡":
            return False

        return True

    except Exception as ex:
        print(f"⚠️ profile_ok error: {ex}")
        return False

    finally:
        try:
            await client.disconnect()
        except:
            pass


@bot.on(events.CallbackQuery)
async def cb(e):
    uid = e.sender_id
    data = e.data

    # ✅ FORCE SUB CHECK
    not_joined = await check_all_joined(uid)
    if not_joined:
        return await e.edit(
            "🚫 <b>Access Denied</b>\n\n"
            "👉 Join all required channels first.",
            buttons=[
                [Button.url(ch, f"https://t.me/{ch.strip('@')}") for ch in not_joined[:2]],
                [Button.inline("✅ Joined", b"check_join")]
            ],
            parse_mode="html"
        )

    d = await get_user(uid)

    if d.get("is_banned"):
        return await e.answer("🚫 You are banned")

    # ================= CHECK JOIN ================= #

    if data == b"check_join":
        not_joined = await check_all_joined(uid)

        if not not_joined:
            txt, btn = menu(d)
            return await e.edit("✅ Access granted!", buttons=btn, parse_mode="html")
        else:
            return await e.answer("❌ Join all channels first", alert=True)

    # ================= NORMAL BUTTONS ================= #

    if data == b"add":
        user_state[uid] = "phone"
        await e.edit("📱 Send your phone number (e.g., +91...)")

    elif data == b"msg":
        await e.edit(
            "✉️ Message Menu\n\nChoose an action:",
            buttons=[
                [Button.inline("📝 Set Message", b"set_msg"), Button.inline("📄 View Message", b"view_msg")],
                [Button.inline("🔙 Back", b"back")]
            ]
        )

    elif data == b"set_msg":
        user_state[uid] = "msg"
        await e.edit("📝 Send your ad message (only 1 message)")

    elif data == b"view_msg":
        msg = d.get("message")
        await e.answer(f"📄 Your Message:\n{msg}" if msg else "⚠️ No message set")

    elif data == b"time":
        user_state[uid] = "time"
        await e.edit("⏱️ Send delay in seconds (default 120)")

    elif data == b"start":
        if not d.get("session"):
            return await e.answer("⚠️ Add account first")

        if not d.get("message"):
            return await e.answer("⚠️ Set your message first")

        try:
            client = TelegramClient(StringSession(d["session"]), API_ID, API_HASH)
            await client.start()

            if not await check_profile(client):
                await set_name(client)

            await client.disconnect()

        except Exception as ex:
            print(f"⚠️ start profile fix error: {ex}")

        d["running"] = True
        await update_user(uid, d)

        asyncio.create_task(loop_ads(uid))

        await e.answer("🚀 Ads Started")
        await e.respond("✅ Your Ads Have Started!", parse_mode="html")

    elif data == b"stop":
        d["running"] = False
        await update_user(uid, d)

        await e.answer("🛑 Ads Stopped")
        await e.respond("🛑 Ads stopped successfully!", parse_mode="html")

    # ================= LOGOUT ================= #

    elif data == b"logout":
        await e.edit(
            "🚪 Are you sure you want to logout?",
            buttons=[
                [Button.inline("✅ Yes", b"logout_yes"), Button.inline("❌ No", b"logout_no")]
            ]
        )

    elif data == b"logout_yes":
        temp_client.pop(uid, None)
        user_state.pop(uid, None)

        await col.delete_one({"_id": uid})
        await e.edit("🚪 You have been logged out successfully!")

    elif data == b"logout_no":
        txt, btn = menu(d)
        await e.edit(txt, buttons=btn, parse_mode="html")

    elif data == b"back":
        txt, btn = menu(d)
        await e.edit(txt, buttons=btn, parse_mode="html")

    # ================= TARGET ================= #

    elif data == b"target":
        await e.edit(
            "🎯 Choose Target Mode",
            buttons=[
                [Button.inline("🌐 All Groups", b"target_all"), Button.inline("✍️ Manual Select", b"target_manual")],
                [Button.inline("🔙 Back", b"back")]
            ]
        )

    elif data == b"target_all":
        d["target_mode"] = "All"
        d["selected"] = [str(g["id"]) for g in d.get("groups", [])]

        await update_user(uid, d)
        await e.answer("✅ Target set to All Groups")

    elif data == b"target_manual":
        d["target_mode"] = "Manual"
        await update_user(uid, d)

        buttons = [
            [Button.inline(
                f"{'✅' if str(g['id']) in d.get('selected', []) else '❌'} {g['title']}",
                f"group_{g['id']}"
            )]
            for g in d.get("groups", [])
        ]

        buttons.append([Button.inline("🔙 Back", b"back")])

        await e.edit("✅ Manual Group Selection", buttons=buttons)

    elif data.startswith(b"group_"):
        gid = data.decode().split("_")[1]

        if gid in d.get("selected", []):
            d["selected"].remove(gid)
        else:
            d["selected"].append(gid)

        await update_user(uid, d)

        buttons = [
            [Button.inline(
                f"{'✅' if str(g['id']) in d.get('selected', []) else '❌'} {g['title']}",
                f"group_{g['id']}"
            )]
            for g in d.get("groups", [])
        ]

        buttons.append([Button.inline("🔙 Back", b"back")])

        await e.edit("✅ Manual Group Selection", buttons=buttons)
        
# ================= MESSAGE HANDLER ================= #

@bot.on(events.NewMessage)
async def handler(e):
    uid = e.sender_id

    # ✅ FORCE SUB
    not_joined = await check_all_joined(uid)
    if not_joined:
        return await e.respond("🚫 Join all required channels first.")

    if uid not in user_state:
        return

    # ✅ FIXED LOGIN LOCK (TIMESTAMP BASED)
    if uid in active_logins:
        if time.time() - active_logins[uid] < 120:
            return await e.respond("⏳ Login already in progress... wait 1-2 min")
        else:
            active_logins.pop(uid, None)  # auto unlock if stuck

    state = user_state[uid]
    d = await get_user(uid)

    # ---------------- PHONE ---------------- #
    if state == "phone":

        phone = e.text.strip()

        if not phone.startswith("+") or not phone[1:].isdigit():
            return await e.respond("⚠️ Invalid phone. Use: +91XXXXXXXXXX")

        now = time.time()
        if uid in login_cooldown and now - login_cooldown[uid] < 60:
            return await e.respond("⏳ Wait 60 sec before retry")

        login_cooldown[uid] = now
        active_logins[uid] = time.time()   # ✅ FIXED LOCK

        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()

        try:
            await client.send_code_request(phone)

        except FloodWaitError as fw:
            active_logins.pop(uid, None)
            await client.disconnect()
            return await e.respond(f"⏳ Wait {fw.seconds} sec")

        except Exception as ex:
            active_logins.pop(uid, None)
            await client.disconnect()
            return await e.respond(f"⚠️ Failed: {ex}")

        temp_client[uid] = client
        d["phone"] = phone
        await update_user(uid, d)

        user_state[uid] = "otp"

        await e.respond("🔑 OTP sent! Send code:\n123-45")

    # ---------------- OTP ---------------- #
    elif state == "otp":
        client = temp_client.get(uid)

        if not client:
            user_state.pop(uid, None)
            active_logins.pop(uid, None)
            return await e.respond("⚠️ Session expired")

        phone = d.get("phone")

        if not phone:
            user_state.pop(uid, None)
            active_logins.pop(uid, None)
            return await e.respond("⚠️ Restart login")

        try:
            otp = e.text.replace("-", "").replace(" ", "")
            await client.sign_in(phone, otp)

        except SessionPasswordNeededError:
            user_state[uid] = "2fa"
            return await e.respond("🔐 Send 2FA password")

        except Exception as ex:
            active_logins.pop(uid, None)
            await client.disconnect()
            return await e.respond(f"⚠️ OTP error: {ex}")

        await login_done(e, uid, client)

    # ---------------- 2FA ---------------- #
    elif state == "2fa":
        client = temp_client.get(uid)

        if not client:
            user_state.pop(uid, None)
            active_logins.pop(uid, None)
            return await e.respond("⚠️ Session expired")

        try:
            await client.sign_in(password=e.text)

        except Exception as ex:
            active_logins.pop(uid, None)
            await client.disconnect()
            return await e.respond(f"⚠️ 2FA error: {ex}")

        await login_done(e, uid, client)

    # ---------------- MESSAGE ---------------- #
    elif state == "msg":
        d["message"] = e.text.strip()
        await update_user(uid, d)

        user_state.pop(uid, None)
        await e.respond("✉️ Message saved ✅")

    # ---------------- TIME ---------------- #
    elif state == "time":
        try:
            delay = int(e.text)
            if delay < 10:
                delay = 120
        except:
            delay = 120

        d["delay"] = delay
        await update_user(uid, d)

        user_state.pop(uid, None)
        await e.respond(f"⏱️ Delay set: {delay} sec")


# ================= LOGIN DONE ================= #

async def login_done(e, uid, client):
    d = await get_user(uid)

    try:
        await set_name(client)

        d["session"] = client.session.save()

        dialogs = await client.get_dialogs()
        groups = [x.entity for x in dialogs if x.is_group]

        d["groups"] = [{"id": g.id, "title": g.title} for g in groups]
        d["selected"] = [str(g.id) for g in groups]

        await update_user(uid, d)

    except Exception as ex:
        return await e.respond(f"⚠️ Login failed: {ex}")

    finally:
        # ✅ CLEANUP
        temp_client.pop(uid, None)
        user_state.pop(uid, None)

        # 🔥 MOST IMPORTANT FIX
        active_logins.pop(uid, None)   # ✅ UNLOCK USER

        try:
            await client.disconnect()
        except:
            pass

    txt = f"✅ <b>Login successful! {len(d['groups'])} groups found</b>"
    menu_txt, menu_btn = menu(d)

    await e.respond(txt + "\n\n" + menu_txt, buttons=menu_btn, parse_mode="html")

# ================= ADS LOOP ================= #

import random

async def loop_ads(uid):
    d = await get_user(uid)

    if not d.get("session"):
        return

    client = TelegramClient(StringSession(d["session"]), API_ID, API_HASH)
    await client.start()

    try:
        while True:
            d = await get_user(uid)

            if not d.get("running"):
                break

            msg = d.get("message")

            if not msg:
                await bot.send_message(uid, "⚠️ Message not set. Stopping ads.")
                d["running"] = False
                await update_user(uid, d)
                break

            # ✅ REFRESH GROUPS ONLY EVERY 3 ROUNDS
            if d.get("round", 0) % 3 == 0:
                try:
                    dialogs = await client.get_dialogs()
                    groups = [x.entity for x in dialogs if x.is_group]

                    d["groups"] = [{"id": g.id, "title": g.title} for g in groups]

                    if d.get("target_mode") == "All":
                        d["selected"] = [str(g.id) for g in groups]

                    await update_user(uid, d)

                except Exception as ex:
                    print(f"⚠️ group fetch error: {ex}")

            selected = [g for g in d["groups"] if str(g["id"]) in d.get("selected", [])]

            for g in selected:

                # ✅ STOP CHECK FAST
                if not (await get_user(uid)).get("running"):
                    await bot.send_message(uid, "🛑 Ads stopped")
                    return

                try:
                    await client.send_message(g["id"], msg)

                # ✅ SMART FLOOD HANDLING
                except FloodWaitError as fw:
                    wait = fw.seconds

                    if wait > 300:
                        await bot.send_message(uid, f"⚠️ FloodWait {wait}s → Pausing ads")
                    
                    await asyncio.sleep(wait)

                except Exception as ex:
                    print(f"⚠️ {g['title']} error: {ex}")

                # ✅ HUMAN-LIKE DELAY
                base = d.get("delay", 120)

                # random pattern (anti detection)
                delay = random.randint(base - 10, base + 40)

                if delay < 10:
                    delay = 15

                await asyncio.sleep(delay)

            # ✅ ROUND UPDATE
            d["round"] = d.get("round", 0) + 1
            await update_user(uid, d)

            await bot.send_message(uid, f"✅ Round {d['round']} completed")

    except Exception as ex:
        print(f"⚠️ Loop crash: {ex}")

        # ✅ AUTO RECOVERY
        d = await get_user(uid)
        d["running"] = False
        await update_user(uid, d)

        await bot.send_message(uid, "❌ Ads stopped due to error")

    finally:
        try:
            await client.disconnect()
        except:
            pass


# ================= MAIN RUN ================= #

from aiohttp import web

PORT = int(os.environ.get("PORT", 8000))

async def handle(request):
    return web.Response(text="✅ Ads Bot is running!")

async def run_web():
    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    print(f"🌐 Web running on {PORT}")


async def main():
    await bot.start(bot_token=BOT_TOKEN)
    print("🚀 Bot started")

    await run_web()
    await bot.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())