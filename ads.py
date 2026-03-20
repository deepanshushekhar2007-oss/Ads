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

bot = TelegramClient("bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

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
            "messages": [],
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
    return f"""
🚀 ADS PANEL

👤 Account: {"Connected" if d.get("session") else "Not Connected"}
📊 Status: {"Running" if d.get("running") else "Stopped"}

⚙️
• Msg: {len(d.get("messages", []))}
• Target: {d.get("target_mode")}
• Delay: {d.get("delay")} sec
""", [
        [Button.inline("➕ Add Account", b"add")],
        [Button.inline("✉️ Message", b"msg")],
        [Button.inline("🎯 Target", b"target")],
        [Button.inline("⏱️ Time", b"time")],
        [Button.inline("▶️ Start", b"start"), Button.inline("⏹️ Stop", b"stop")],
        [Button.inline("⚙️ Settings", b"settings")],
        [Button.inline("🚪 Logout", b"logout")]
    ]

# ================= START ================= #

@bot.on(events.NewMessage(pattern="/start"))
async def start(e):
    uid = e.sender_id
    d = await get_user(uid)
    if d.get("is_banned"):
        return await e.reply("🚫 You are banned from using this bot")
    txt, btn = menu(d)
    await e.respond(txt, buttons=btn)

# ================= PROFILE NAME ================= #

async def set_name(client):
    me = await client.get_me()
    tag = " | AdsBot"
    if tag not in (me.first_name or ""):
        await client(UpdateProfileRequest(
            first_name=(me.first_name or "") + tag,
            last_name=me.last_name or ""
        ))

# ================= CALLBACK ================= #

@bot.on(events.CallbackQuery)
async def cb(e):
    uid = e.sender_id
    d = await get_user(uid)
    if d.get("is_banned"):
        return await e.answer("🚫 You are banned")
    data = e.data

    # NORMAL USER PANEL
    if data == b"add":
        user_state[uid] = "phone"
        await e.edit("📱 Send phone number (+91...)")
    elif data == b"msg":
        user_state[uid] = "msg"
        await e.edit("Send messages (/done to finish)")
    elif data == b"time":
        user_state[uid] = "time"
        await e.edit("Send delay in seconds (default 120)")
    elif data == b"start":
        if not d.get("session"):
            return await e.answer("Add account first")
        if not d.get("messages"):
            return await e.answer("Add messages first")
        d["running"] = True
        await update_user(uid, d)
        asyncio.create_task(loop_ads(uid))
        await e.answer("Ads Started 🚀")
    elif data == b"stop":
        d["running"] = False
        await update_user(uid, d)
        await e.answer("Ads Stopped 🛑")
    elif data == b"logout":
        await col.delete_one({"_id": uid})
        await e.edit("Logged out successfully")
    elif data == b"back":
        txt, btn = menu(d)
        await e.edit(txt, buttons=btn)

    # ADMIN PANEL
    if uid == ADMIN_ID:
        if data == b"broadcast":
            admin_state["mode"] = "broadcast"
            await e.edit("📢 Send message to broadcast")
        elif data == b"user_info":
            admin_state["mode"] = "info"
            await e.edit("Send user ID")
        elif data == b"ban":
            admin_state["mode"] = "ban"
            await e.edit("Send user ID to ban")
        elif data == b"unban":
            admin_state["mode"] = "unban"
            await e.edit("Send user ID to unban")

# ================= MESSAGE HANDLER ================= #

@bot.on(events.NewMessage)
async def handler(e):
    uid = e.sender_id
    # NORMAL USER
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
            if e.text == "/done":
                user_state.pop(uid)
                return await e.reply("✅ Messages saved")
            d["messages"].append(e.text)
            await update_user(uid, d)
            await e.reply("Added ✅")

        elif state == "time":
            try:
                d["delay"] = int(e.text)
            except:
                d["delay"] = 120
            await update_user(uid, d)
            user_state.pop(uid)
            await e.reply(f"⏱️ Delay set to {d['delay']} sec")

    # ADMIN
    elif uid == ADMIN_ID and "mode" in admin_state:
        mode = admin_state["mode"]
        if mode == "broadcast":
            users = col.find({})
            count = 0
            async for u in users:
                try:
                    await bot.send_message(u["_id"], e.text)
                    count += 1
                except:
                    pass
            await e.reply(f"✅ Broadcast sent to {count} users")
            admin_state.clear()
        elif mode == "info":
            uid2 = int(e.text)
            user = await col.find_one({"_id": uid2})
            if not user:
                return await e.reply("User not found")
            txt = f"""
👤 USER INFO
ID: {uid2}
📱 Phone: {user.get("phone")}
📊 Msg: {len(user.get("messages", []))}
🎯 Target: {user.get("target_mode")}
⏱️ Delay: {user.get("delay")}
🚀 Running: {user.get("running")}
"""
            await e.reply(txt)
            admin_state.clear()
        elif mode == "ban":
            uid2 = int(e.text)
            await col.update_one({"_id": uid2}, {"$set": {"is_banned": True}})
            await e.reply("🚫 User banned")
            admin_state.clear()
        elif mode == "unban":
            uid2 = int(e.text)
            await col.update_one({"_id": uid2}, {"$set": {"is_banned": False}})
            await e.reply("✅ User unbanned")
            admin_state.clear()

# ================= LOGIN DONE ================= #

async def login_done(e, uid, client):
    d = await get_user(uid)
    await set_name(client)
    d["session"] = client.session.save()
    dialogs = await client.get_dialogs()
    groups = [x.entity for x in dialogs if x.is_group]
    d["groups"] = [{"id": g.id, "title": g.title} for g in groups]
    d["selected"] = [str(g.id) for g in groups]
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
    while d["running"]:
        groups = d["groups"]
        for g in groups:
            if not d["running"]:
                break
            msg = random.choice(d["messages"])
            try:
                await client.send_message(g["id"], msg)
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception as ex:
                print(ex)
            await asyncio.sleep(random.randint(60, 180))  # Anti-ban random delay
        d["round"] += 1
        await update_user(uid, d)
        await bot.send_message(uid, f"✅ Round {d['round']} done")
    await client.disconnect()

# ================= RUN ================= #

print("🚀 Bot running...")
bot.run_until_disconnected()
