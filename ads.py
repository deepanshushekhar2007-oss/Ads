import asyncio
import os
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

# Mongo setup (optimized)
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo.ads_bot
col = db.users

# Runtime storage
user_state = {}
temp_client = {}
admin_state = {}

ADMINS = [ADMIN_ID]

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
    # ⚠️ Safe update (avoid overwriting _id)
    data.pop("_id", None)
    await col.update_one({"_id": uid}, {"$set": data})


# ================= MENU FUNCTION ================= #

def menu(d):
    txt = (
        "🌐 <b>ADS CONTROL PANEL</b> 🌐\n\n"
        f"👤 <b>Account:</b> {'✅ Connected' if d.get('session') else '❌ Not Connected'}\n"
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

from telethon import functions
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.users import GetFullUserRequest

TAG = "| AdsBot"
BIO = "AdsBot Active"

async def set_name(client):
    """
    Smart profile setter (no duplicate tag, safe update)
    """
    try:
        me = await client.get_me()

        # ✅ Clean existing name (remove old tag if present)
        first = (me.first_name or "").replace(TAG, "").strip()
        new_first_name = f"{first} {TAG}".strip()

        last = me.last_name or ""

        # ✅ Update only if needed
        if me.first_name != new_first_name or me.last_name != last:
            await client(UpdateProfileRequest(
                first_name=new_first_name,
                last_name=last
            ))

        # ✅ Get current bio
        full = await client(GetFullUserRequest(me.id))
        current_bio = (full.about or "").strip()

        # ✅ Update bio only if needed
        if current_bio != BIO:
            await client(functions.account.UpdateProfileRequest(
                about=BIO
            ))

    except Exception as ex:
        print(f"⚠️ set_name failed: {ex}")


async def check_profile(client):
    """
    Reliable profile check (name + bio)
    """
    try:
        me = await client.get_me()

        # ✅ Name check (ignore spaces)
        if not me.first_name or TAG.replace(" ", "") not in me.first_name.replace(" ", ""):
            return False

        # ✅ Correct bio fetch
        full = await client(GetFullUserRequest(me.id))
        bio = (full.about or "").strip()

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
    d = await get_user(uid)

    if d.get("is_banned"):
        return await e.reply("🚫 You are banned from using this bot")

    # ---------------- Restore profile silently ----------------
    if d.get("session"):
        try:
            client = TelegramClient(StringSession(d["session"]), API_ID, API_HASH)
            await client.start()

            # ✅ Auto fix profile (no warning spam)
            await set_name(client)

            await client.disconnect()

        except Exception as ex:
            print(f"⚠️ Error restoring profile for {uid}: {ex}")

    # ---------------- Show main menu ----------------
    txt, btn = menu(d)
    await e.respond(txt, buttons=btn, parse_mode="html")
    
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

@bot.on(events.CallbackQuery)
async def cb(e):
    uid = e.sender_id
    d = await get_user(uid)
    
    if d.get("is_banned"):
        return await e.answer("🚫 You are banned")
    
    data = e.data

    # ---------------- PROFILE ENFORCEMENT CHECK ---------------- #
    from telethon.tl.functions.users import GetFullUserRequest

    async def profile_ok(session_str):
        if not session_str:
            return False

        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.start()
        try:
            me = await client.get_me()

            # ✅ Name check (ignore spaces)
            if not me.first_name or "|AdsBot" not in me.first_name.replace(" ", ""):
                return False

            # ✅ Correct bio fetch
            full = await client(GetFullUserRequest(me.id))
            bio = (full.about or "").strip()

            if bio != "AdsBot Active":
                return False

            return True

        except Exception as ex:
            print(f"⚠️ profile_ok error: {ex}")
            return False

        finally:
            await client.disconnect()


    # ---------------- NORMAL USER BUTTONS ---------------- #

    if data == b"add":
        user_state[uid] = "phone"
        await e.edit("📱 Send your phone number (e.g., +91...)")

    elif data == b"msg":
        txt = "✉️ Message Menu\n\nChoose an action:"
        buttons = [
            [Button.inline("📝 Set Message", b"set_msg"), Button.inline("📄 View Message", b"view_msg")],
            [Button.inline("🔙 Back", b"back")]
        ]
        await e.edit(txt, buttons=buttons)

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

        # ✅ Profile enforcement (fixed)
        if not await profile_ok(d["session"]):
            return await e.answer("⚠️ Fix your profile (name/bio) to start ads")

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


    # ---------------- LOGOUT ---------------- #

    elif data == b"logout":
        buttons = [
            [Button.inline("✅ Yes", b"logout_yes"), Button.inline("❌ No", b"logout_no")]
        ]
        await e.edit("🚪 Are you sure you want to logout?", buttons=buttons)

    elif data == b"logout_yes":
        temp_client.pop(uid, None)
        user_state.pop(uid, None)

        await col.delete_one({"_id": uid})
        await e.edit("🚪 You have been logged out successfully!")

    elif data == b"logout_no":
        txt, btn = menu(d)
        await e.edit("⚠️ Logout cancelled", buttons=btn, parse_mode="html")

    elif data == b"back":
        txt, btn = menu(d)
        await e.edit(txt, buttons=btn, parse_mode="html")


    # ---------------- TARGET ---------------- #

    elif data == b"target":
        txt = "🎯 Choose Target Mode"
        buttons = [
            [Button.inline("🌐 All Groups", b"target_all"), Button.inline("✍️ Manual Select", b"target_manual")],
            [Button.inline("🔙 Back", b"back")]
        ]
        await e.edit(txt, buttons=buttons)

    elif data == b"target_all":
        d["target_mode"] = "All"
        d["selected"] = [str(g["id"]) for g in d.get("groups", [])]

        await update_user(uid, d)
        await e.answer("✅ Target set to All Groups")

    elif data == b"target_manual":
        d["target_mode"] = "Manual"
        await update_user(uid, d)

        txt = "✅ Manual Group Selection\n\nTap to select/deselect groups:"
        buttons = []

        for g in d.get("groups", []):
            sel = "✅" if str(g["id"]) in d.get("selected", []) else "❌"
            buttons.append([Button.inline(f"{sel} {g['title']}", f"group_{g['id']}")])

        buttons.append([Button.inline("🔙 Back", b"back")])

        await e.edit(txt, buttons=buttons)

    elif data.startswith(b"group_"):
        gid = data.decode().split("_")[1]

        if gid in d.get("selected", []):
            d["selected"].remove(gid)
        else:
            d["selected"].append(gid)

        await update_user(uid, d)

        # refresh
        txt = "✅ Manual Group Selection\n\nTap to select/deselect groups:"
        buttons = []

        for g in d.get("groups", []):
            sel = "✅" if str(g["id"]) in d.get("selected", []) else "❌"
            buttons.append([Button.inline(f"{sel} {g['title']}", f"group_{g['id']}")])

        buttons.append([Button.inline("🔙 Back", b"back")])

        await e.edit(txt, buttons=buttons)
        
# ================= MESSAGE HANDLER ================= #

@bot.on(events.NewMessage)
async def handler(e):
    uid = e.sender_id

    if uid not in user_state:
        return

    state = user_state[uid]
    d = await get_user(uid)

    # --- PHONE NUMBER ENTRY ---
    if state == "phone":
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()

        try:
            await client.send_code_request(e.text)
        except Exception as ex:
            return await e.respond(f"⚠️ Failed to send code: {ex}")

        temp_client[uid] = client
        d["phone"] = e.text
        await update_user(uid, d)

        user_state[uid] = "otp"

        await e.respond(
            "🔑 <b>OTP sent!</b>\n\n"
            "Send the code exactly as received.\n\n"
            "Examples:\n"
            "• 1-2-3-4-5\n"
            "• 12345",
            parse_mode="html"
        )

    # --- OTP ENTRY ---
    elif state == "otp":
        client = temp_client.get(uid)

        if not client:
            user_state.pop(uid, None)
            return await e.respond("⚠️ Session expired, try again.")

        try:
            # ✅ Clean OTP (remove spaces & dashes)
            otp = e.text.replace("-", "").replace(" ", "")
            await client.sign_in(d["phone"], otp)

        except SessionPasswordNeededError:
            user_state[uid] = "2fa"
            return await e.respond("🔐 <b>Send your 2FA password</b>", parse_mode="html")

        except Exception as ex:
            return await e.respond(f"⚠️ OTP error: {ex}")

        await login_done(e, uid, client)

    # --- 2FA PASSWORD ENTRY ---
    elif state == "2fa":
        client = temp_client.get(uid)

        if not client:
            user_state.pop(uid, None)
            return await e.respond("⚠️ Session expired, try again.")

        try:
            await client.sign_in(password=e.text)
        except Exception as ex:
            return await e.respond(f"⚠️ 2FA error: {ex}")

        await login_done(e, uid, client)

    # --- SET MESSAGE ---
    elif state == "msg":
        d["message"] = e.text.strip()
        await update_user(uid, d)

        user_state.pop(uid, None)
        await e.respond("✉️ <b>Message saved ✅</b>", parse_mode="html")

    # --- SET DELAY ---
    elif state == "time":
        try:
            delay = int(e.text)
            if delay < 10:
                delay = 120  # ✅ safety limit
        except:
            delay = 120

        d["delay"] = delay
        await update_user(uid, d)

        user_state.pop(uid, None)
        await e.respond(f"⏱️ Delay set to {delay} sec", parse_mode="html")


# ================= LOGIN DONE ================= #

async def login_done(e, uid, client):
    d = await get_user(uid)

    # ✅ Auto fix profile
    await set_name(client)

    # ✅ Save session
    d["session"] = client.session.save()

    # ✅ Fetch groups safely
    dialogs = await client.get_dialogs()
    groups = [x.entity for x in dialogs if x.is_group]

    d["groups"] = [{"id": g.id, "title": g.title} for g in groups]
    d["selected"] = [str(g.id) for g in groups]

    await update_user(uid, d)

    # ✅ cleanup
    temp_client.pop(uid, None)
    user_state.pop(uid, None)

    txt = f"✅ <b>Login successful! {len(groups)} groups found</b>"
    menu_txt, menu_btn = menu(d)

    await e.respond(txt + "\n\n" + menu_txt, buttons=menu_btn, parse_mode="html")


# ================= ADS LOOP ================= #

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

            # ✅ refresh groups every round
            dialogs = await client.get_dialogs()
            groups = [x.entity for x in dialogs if x.is_group]

            d["groups"] = [{"id": g.id, "title": g.title} for g in groups]

            if d.get("target_mode") == "All":
                d["selected"] = [str(g.id) for g in groups]

            await update_user(uid, d)

            selected = [g for g in d["groups"] if str(g["id"]) in d.get("selected", [])]

            for g in selected:
                d = await get_user(uid)

                if not d.get("running"):
                    await bot.send_message(uid, "🛑 Ads stopped")
                    return

                try:
                    await client.send_message(g["id"], msg)

                except FloodWaitError as fw:
                    await asyncio.sleep(fw.seconds)

                except Exception as ex:
                    print(f"⚠️ {g['title']} error: {ex}")

                await asyncio.sleep(d.get("delay", 120))

            # ✅ round update
            d["round"] = d.get("round", 0) + 1
            await update_user(uid, d)

            await bot.send_message(uid, f"✅ Round {d['round']} completed")

    finally:
        await client.disconnect()


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