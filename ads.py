import asyncio
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

ADMINS = [ADMIN_ID]  # List of admin IDs

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

    # 2-per-row buttons
    buttons = [
        [Button.inline("➕ Add Account", b"add"), Button.inline("✉️ Message Menu", b"msg")],
        [Button.inline("🎯 Target Groups", b"target"), Button.inline("⏱️ Set Delay", b"time")],
        [Button.inline("▶️ Start Ads", b"start"), Button.inline("⏹️ Stop Ads", b"stop")],
        [Button.inline("🚪 Logout", b"logout")]
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
# ================= START & ADMIN COMMANDS ================= #

@bot.on(events.NewMessage(pattern="/start"))
async def start(e):
    uid = e.sender_id
    d = await get_user(uid)
    if d.get("is_banned"):
        return await e.reply("🚫 You are banned from using this bot")
    
    txt, btn = menu(d)
    await e.respond(txt, buttons=btn, parse_mode="html")
    
@bot.on(events.NewMessage(pattern=r'/ban (\d+)'))
async def ban_user(e):
    if e.sender_id not in ADMINS:
        return await e.reply("❌ You are not authorized to use this command")
    
    target_id = int(e.pattern_match.group(1))
    d = await get_user(target_id)
    if not d:
        return await e.reply("⚠️ User not found")
    
    d["is_banned"] = True
    await update_user(target_id, d)
    await e.reply(f"🚫 User {target_id} has been banned")

@bot.on(events.NewMessage(pattern=r'/unban (\d+)'))
async def unban_user(e):
    if e.sender_id not in ADMINS:
        return await e.reply("❌ You are not authorized to use this command")
    
    target_id = int(e.pattern_match.group(1))
    d = await get_user(target_id)
    if not d:
        return await e.reply("⚠️ User not found")
    
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

    elif data == b"logout":
        temp_client.pop(uid, None)
        await col.delete_one({"_id": uid})
        await e.edit("🚪 Logged out successfully")

    elif data == b"back":
        txt, btn = menu(d)
        await e.edit(txt, buttons=btn, parse_mode="html")

    # ---------------- TARGET MENU ---------------- #
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

        # Refresh manual selection menu
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
        return  # No active state, ignore

    state = user_state[uid]
    d = await get_user(uid)

    # --- PHONE NUMBER ENTRY ---
    if state == "phone":
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        try:
            await client.send_code_request(e.text)
        except Exception as ex:
            return await e.reply(f"⚠️ Failed to send code: {ex}")
        
        temp_client[uid] = client
        d["phone"] = e.text
        await update_user(uid, d)
        user_state[uid] = "otp"

        await e.reply(
            "🔑 <b>OTP sent!</b>\n\n"
            "Please send the code you received in one of these formats:\n\n"
            "<b>Examples:</b>\n"
            "1️⃣ 1-2-3-4-5\n"
            "2️⃣ 22-22-2\n"
            "3️⃣ 123-45\n\n"
            "Make sure to enter exactly as received.",
            parse_mode="html"
        )

    # --- OTP ENTRY ---
    elif state == "otp":
        client = temp_client[uid]
        try:
            await client.sign_in(d["phone"], e.text)
        except SessionPasswordNeededError:
            user_state[uid] = "2fa"
            return await e.reply("🔐 <b>2FA required! Send your password</b>", parse_mode="html")
        except Exception as ex:
            return await e.reply(f"⚠️ OTP error: {ex}")
        await login_done(e, uid, client)

    # --- 2FA PASSWORD ENTRY ---
    elif state == "2fa":
        client = temp_client[uid]
        try:
            await client.sign_in(password=e.text)
        except Exception as ex:
            return await e.reply(f"⚠️ 2FA error: {ex}")
        await login_done(e, uid, client)

    # --- SET AD MESSAGE ---
    elif state == "msg":
        d["message"] = e.text
        await update_user(uid, d)
        user_state.pop(uid)
        await e.reply("✉️ <b>Message saved successfully ✅</b>", parse_mode="html")

    # --- SET DELAY TIME ---
    elif state == "time":
        try:
            delay = int(e.text)
            if delay < 1:
                delay = 120
        except:
            delay = 120
        d["delay"] = delay
        await update_user(uid, d)
        user_state.pop(uid)
        await e.reply(f"⏱️ <b>Delay set to {d['delay']} seconds</b>", parse_mode="html")


# ================= LOGIN DONE ================= #
async def login_done(e, uid, client):
    d = await get_user(uid)
    await set_name(client)  # Automatically set bot name in profile

    # Save session
    d["session"] = client.session.save()

    # Fetch user's groups
    dialogs = await client.get_dialogs()
    groups = [x.entity for x in dialogs if x.is_group]
    d["groups"] = [{"id": g.id, "title": g.title} for g in groups]
    d["selected"] = [str(g["id"]) for g in groups]  # default all selected

    await update_user(uid, d)
    await client.disconnect()
    user_state.pop(uid)
    await e.reply(f"✅ <b>Login successful! {len(groups)} groups detected</b>", parse_mode="html")


# ================= ADS LOOP ================= #
async def loop_ads(uid):
    d = await get_user(uid)
    if not d.get("session"):
        return

    client = TelegramClient(StringSession(d["session"]), API_ID, API_HASH)
    await client.start()

    # Refresh dialogs to get latest groups
    dialogs = await client.get_dialogs()
    groups = [x.entity for x in dialogs if x.is_group]
    d["groups"] = [{"id": g.id, "title": g.title} for g in groups]

    if d.get("target_mode") == "All":
        d["selected"] = [str(g["id"]) for g in d["groups"]]

    await update_user(uid, d)

    try:
        while d.get("running"):
            d = await get_user(uid)
            msg = d.get("message")
            if not msg:
                await bot.send_message(uid, "⚠️ Message not set, stopping ads.")
                d["running"] = False
                await update_user(uid, d)
                break

            selected_groups = [g for g in d["groups"] if str(g["id"]) in d.get("selected", [])]
            any_sent = False

            for g in selected_groups:
                d = await get_user(uid)
                if not d.get("running"):
                    await bot.send_message(uid, "🛑 Ads stopped ✅")
                    return
                try:
                    await client.send_message(g["id"], msg)
                    any_sent = True
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception as ex:
                    await bot.send_message(uid, f"⚠️ Could not send to {g['title']}: {ex}")

                await asyncio.sleep(d.get("delay", 120))

            if any_sent:
                d["round"] = d.get("round", 0) + 1
                await update_user(uid, d)
                await bot.send_message(uid, f"✅ Round {d['round']} completed!")
    finally:
        await client.disconnect()


# ================= MAIN RUN ================= #
async def main():
    await bot.start(bot_token=BOT_TOKEN)
    print("🚀 Bot running on Render...")
    await bot.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())