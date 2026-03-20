import asyncio
import random
import os
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.account import UpdateProfileRequest
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = TelegramClient("bot", API_ID, API_HASH)

mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["ads_bot"]
col = db["users"]

user_state = {}
temp_client = {}
admin_state = {}

# ================= DB ================= #

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
    await col.update_one({"_id": uid}, {"$set": data})

# ================= MENU ================= #

def menu(d):
    txt = f"""
🚀 ADS PANEL

👤 Account: {"Connected" if d.get("session") else "Not Connected"}
📊 Status: {"Running" if d.get("running") else "Stopped"}

⚙️
• Msg: {d.get("message") if d.get("message") else 'None'}
• Target Mode: {d.get("target_mode")}
• Delay: {d.get("delay")} sec
"""
    # 2 buttons per row
    buttons = [
        [Button.inline("➕ Add Account", b"add"), Button.inline("✉️ Message", b"msg")],
        [Button.inline("🎯 Target", b"target"), Button.inline("⏱️ Time", b"time")],
        [Button.inline("▶️ Start", b"start"), Button.inline("⏹️ Stop", b"stop")],
        [Button.inline("⚙️ Settings", b"settings"), Button.inline("🚪 Logout", b"logout")]
    ]
    return txt, buttons

# ================= PROFILE NAME ================= #

async def set_name(client):
    me = await client.get_me()
    tag = " | AdsBot"
    if tag not in (me.first_name or ""):
        await client(UpdateProfileRequest(
            first_name=(me.first_name or "") + tag,
            last_name=me.last_name or ""
        ))

# ================= START ================= #

@bot.on(events.NewMessage(pattern="/start"))
async def start(e):
    uid = e.sender_id
    d = await get_user(uid)
    if d.get("is_banned"):
        return await e.reply("🚫 You are banned from using this bot")
    txt, btn = menu(d)
    await e.respond(txt, buttons=btn)

# ================= CALLBACK ================= #

@bot.on(events.CallbackQuery)
async def cb(e):
    uid = e.sender_id
    d = await get_user(uid)
    if d.get("is_banned"):
        return await e.answer("🚫 You are banned")
    data = e.data

    # --- NORMAL USER ---
    if data == b"add":
        user_state[uid] = "phone"
        await e.edit("📱 Send phone number (+91...)")

    elif data == b"msg":
        # show sub-menu for message
        buttons = [
            [Button.inline("Set Message", b"set_msg"), Button.inline("View Message", b"view_msg")],
            [Button.inline("Back", b"back")]
        ]
        await e.edit("✉️ Message Menu", buttons=buttons)

    elif data == b"set_msg":
        user_state[uid] = "msg"
        await e.edit("✉️ Send your message (only 1 message)")

    elif data == b"view_msg":
        msg = d.get("message")
        await e.answer(f"📄 Your message:\n{msg}" if msg else "⚠️ No message set")

    elif data == b"time":
        user_state[uid] = "time"
        await e.edit("⏱️ Send delay in seconds (default 120)")

    elif data == b"start":
        if not d.get("session"):
            return await e.answer("Add account first")
        if not d.get("message"):
            return await e.answer("Set your message first")
        d["running"] = True
        await update_user(uid, d)
        asyncio.create_task(loop_ads(uid))
        await e.answer("🚀 Ads Started")
        await e.respond("✅ Your Ads Started!")

    elif data == b"stop":
        d["running"] = False
        await update_user(uid, d)
        await e.answer("🛑 Ads Stopped")

    elif data == b"logout":
        try:
            temp_client.pop(uid, None)
            await col.delete_one({"_id": uid})
        except Exception as ex:
            await e.answer(f"⚠️ Error: {ex}")
        await e.edit("🚪 Logged out successfully")

    elif data == b"back":
        txt, btn = menu(d)
        await e.edit(txt, buttons=btn)

    # --- TARGET BUTTON ---
    elif data == b"target":
        txt = "🎯 Choose Target Mode"
        btns = [
            [Button.inline("All Groups", b"target_all"), Button.inline("Manual Select", b"target_manual")],
            [Button.inline("Back", b"back")]
        ]
        await e.edit(txt, buttons=btns)

    elif data == b"target_all":
        d["target_mode"] = "All"
        d["selected"] = [str(g["id"]) for g in d.get("groups", [])]
        await update_user(uid, d)
        await e.answer("✅ Target set to All Groups")

    elif data == b"target_manual":
        d["target_mode"] = "Manual"
        await update_user(uid, d)
        buttons = []
        for g in d.get("groups", []):
            sel = "✅" if str(g["id"]) in d.get("selected", []) else "❌"
            buttons.append([Button.inline(f"{sel} {g['title']}", f"group_{g['id']}")])
        buttons.append([Button.inline("Back", b"back")])
        await e.edit("Tap to select/deselect groups:", buttons=buttons)

    elif data.startswith(b"group_"):
        gid = data.decode().split("_")[1]
        if gid in d.get("selected", []):
            d["selected"].remove(gid)
        else:
            d["selected"].append(gid)
        await update_user(uid, d)
        # refresh manual selection buttons
        buttons = []
        for g in d.get("groups", []):
            sel = "✅" if str(g["id"]) in d.get("selected", []) else "❌"
            buttons.append([Button.inline(f"{sel} {g['title']}", f"group_{g['id']}")])
        buttons.append([Button.inline("Back", b"back")])
        await e.edit("Tap to select/deselect groups:", buttons=buttons)

# ================= MESSAGE HANDLER ================= #

@bot.on(events.NewMessage)
async def handler(e):
    uid = e.sender_id
    if uid in user_state:
        state = user_state[uid]
        d = await get_user(uid)

        if state == "phone":
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            await client.send_code_request(e.text)
            temp_client[uid] = client
            d["phone"] = e.text
            await update_user(uid, d)
            user_state[uid] = "otp"
            await e.reply("🔑 Send OTP")

        elif state == "otp":
            client = temp_client[uid]
            try:
                await client.sign_in(d["phone"], e.text)
            except SessionPasswordNeededError:
                user_state[uid] = "2fa"
                return await e.reply("🔐 Send 2FA password")
            await login_done(e, uid, client)

        elif state == "2fa":
            client = temp_client[uid]
            await client.sign_in(password=e.text)
            await login_done(e, uid, client)

        elif state == "msg":
            d["message"] = e.text
            await update_user(uid, d)
            user_state.pop(uid)
            await e.reply("✉️ Message saved ✅")

        elif state == "time":
            try:
                d["delay"] = int(e.text)
            except:
                d["delay"] = 120
            await update_user(uid, d)
            user_state.pop(uid)
            await e.reply(f"⏱️ Delay set to {d['delay']} sec")

# ================= LOGIN DONE ================= #

async def login_done(e, uid, client):
    d = await get_user(uid)
    await set_name(client)
    d["session"] = client.session.save()
    dialogs = await client.get_dialogs()
    groups = [x.entity for x in dialogs if x.is_group]
    d["groups"] = [{"id": g.id, "title": g.title} for g in groups]
    d["selected"] = [str(g["id"]) for g in groups]
    await update_user(uid, d)
    await client.disconnect()
    user_state.pop(uid)
    await e.reply(f"✅ Login success ({len(groups)} groups)")

# ================= ADS LOOP ================= #

async def loop_ads(uid):
    d = await get_user(uid)
    if not d.get("session"):
        return

    client = TelegramClient(StringSession(d["session"]), API_ID, API_HASH)
    await client.start()

    # refresh dialogs for latest groups
    dialogs = await client.get_dialogs()
    groups = [x.entity for x in dialogs if x.is_group]
    d["groups"] = [{"id": g.id, "title": g.title} for g in groups]
    if d["target_mode"] == "All":
        d["selected"] = [str(g["id"]) for g in d["groups"]]
    await update_user(uid, d)

    while d["running"]:
        d = await get_user(uid)
        msg = d.get("message")
        if not msg:
            await bot.send_message(uid, "⚠️ Message not set, stopping ads.")
            d["running"] = False
            await update_user(uid, d)
            break

        selected_groups = [g for g in d["groups"] if str(g["id"]) in d.get("selected", [])]

        for g in selected_groups:
            if not d["running"]:
                break
            try:
                await client.send_message(g["id"], msg)
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception as ex:
                await bot.send_message(uid, f"⚠️ Could not send to {g['title']}: {ex}")
            await asyncio.sleep(d.get("delay", 120))

        d["round"] += 1
        await update_user(uid, d)
        await bot.send_message(uid, f"✅ Round {d['round']} done")

    await client.disconnect()

# ================= MAIN RUN ================= #

async def main():
    await bot.start(bot_token=BOT_TOKEN)
    print("🚀 Bot running on Render...")
    await bot.run_until_disconnected()

asyncio.run(main())
