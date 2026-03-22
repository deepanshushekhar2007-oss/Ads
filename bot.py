import os, time, json
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from threading import Thread

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

state = {}
data = {}
user_whatsapp = {}
whatsapp_running = False

# ---------- Render keep-alive ----------
async def handle(request):
    return web.Response(text="Bot is running ✅")

def start_web():
    app = web.Application()
    app.router.add_get("/", handle)
    port = int(os.environ.get("PORT", 10000))
    web.run_app(app, port=port)

# ---------- Telegram menu ----------
def menu(uid=None):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🔗 Connect WhatsApp", callback_data="connect"),
        InlineKeyboardButton("⚡ Bulk Group Creator", callback_data="bulk"),
        InlineKeyboardButton("🔗 Join via Link", callback_data="join"),
        InlineKeyboardButton("📂 Add via VCF", callback_data="vcf")
    )
    if uid and user_whatsapp.get(uid):
        kb.add(InlineKeyboardButton("🔒 Logout WhatsApp", callback_data="logout"))
    return kb

# ---------- /start ----------
@dp.message_handler(commands=['start'])
async def start_msg(msg: types.Message):
    uid = msg.from_user.id
    status = f"✅ Connected: {user_whatsapp[uid]}" if uid in user_whatsapp else "❌ Not connected"
    await msg.reply(f"🤖 WhatsApp Automation Panel\nStatus: {status}\nSelect an option:", reply_markup=menu(uid))

# ---------- Button callbacks ----------
@dp.callback_query_handler(lambda c: True)
async def cb(call: types.CallbackQuery):
    global whatsapp_running
    uid = call.from_user.id

    # ---------- WhatsApp connect ----------
    if call.data == "connect":
        if whatsapp_running:
            await call.message.reply("✅ WhatsApp bot already running!")
            return
        if uid in user_whatsapp:
            await call.message.reply(f"✅ WhatsApp already connected: {user_whatsapp[uid]}")
            return
        os.system("node wa.js &")
        whatsapp_running = True
        await call.message.edit_text("🔹 Generating WhatsApp QR code...\n⚠️ You have 30s to scan the QR!")

        # Poll QR
        for _ in range(30):
            if os.path.exists("qr.png"):
                await bot.send_photo(uid, open("qr.png", "rb"), caption="Scan this QR within 30s")
                os.remove("qr.png")
                break
            time.sleep(1)

        # Poll connection
        for _ in range(30):
            if os.path.exists("wa_connected.flag"):
                with open("wa_connected.flag") as f:
                    user_whatsapp[uid] = f.read().strip()
                await bot.send_message(uid, f"✅ WhatsApp connected: {user_whatsapp[uid]}")
                os.remove("wa_connected.flag")
                break
            time.sleep(1)

    # ---------- Logout WhatsApp ----------
    elif call.data == "logout":
        if uid in user_whatsapp:
            os.system("node logout.js")
            await bot.send_message(uid, f"🔓 WhatsApp logged out: {user_whatsapp[uid]}")
            del user_whatsapp[uid]
        else:
            await bot.send_message(uid, "❌ No WhatsApp connected")

    # ---------- Bulk group creator ----------
    elif call.data == "bulk":
        if uid not in user_whatsapp:
            await call.message.reply("❌ Connect WhatsApp first!")
            return
        state[uid] = "COUNT"
        await call.message.edit_text("Enter number of groups to create:")

    # ---------- Join via link ----------
    elif call.data == "join":
        if uid not in user_whatsapp:
            await call.message.reply("❌ Connect WhatsApp first!")
            return
        state[uid] = "JOIN"
        await call.message.edit_text("Send invite link(s), one per line:")

    # ---------- Add via VCF ----------
    elif call.data == "vcf":
        if uid not in user_whatsapp:
            await call.message.reply("❌ Connect WhatsApp first!")
            return
        state[uid] = "VCF_FILE"
        await call.message.edit_text("Upload your VCF file containing participants:")

    # ---------- Description Yes/No ----------
    elif call.data in ["desc_yes", "desc_no"]:
        if call.data == "desc_no":
            data[uid]["desc"] = ""
            state[uid] = "DP_OPTION"
        else:
            state[uid] = "DESC"
        # Ask for DP
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("Yes", callback_data="dp_yes"), InlineKeyboardButton("No", callback_data="dp_no"))
        await call.message.reply("Do you want to add Group DP?", reply_markup=kb)

    # ---------- DP Yes/No ----------
    elif call.data in ["dp_yes", "dp_no"]:
        data[uid]["dp"] = True if call.data == "dp_yes" else False
        # Ask for group settings
        state[uid] = "SETTINGS"
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("Restrict Messages", callback_data="restrict_msg"),
            InlineKeyboardButton("Restrict Invites", callback_data="restrict_invite"),
            InlineKeyboardButton("Restrict Admin Only", callback_data="restrict_admin"),
            InlineKeyboardButton("Restrict Media", callback_data="restrict_media"),
            InlineKeyboardButton("✅ Save & Create Groups", callback_data="save_groups")
        )
        await call.message.reply("Select group settings toggles:", reply_markup=kb)

    # ---------- Toggle settings ----------
    elif call.data.startswith("restrict_"):
        key = call.data.replace("restrict_", "")
        data[uid].setdefault("settings", {})[key] = not data[uid].get("settings", {}).get(key, False)
        await call.answer(f"{key} set to {data[uid]['settings'][key]}")

    # ---------- Save & Create Groups ----------
    elif call.data == "save_groups":
        # Save group_data.json for wa.js to read
        with open("group_data.json", "w") as f:
            json.dump(data[uid], f)
        await call.message.reply("✅ Group creation started...")
        os.system("node create.js")
        state.pop(uid)
        data.pop(uid)

# ---------- Start ----------
if __name__ == "__main__":
    Thread(target=start_web).start()
    executor.start_polling(dp, skip_updates=True)
