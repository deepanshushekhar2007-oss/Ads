import os
import time
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from threading import Thread
import subprocess

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

state = {}
data = {}
user_whatsapp = {}  # track which user has connected which WA number

# ---------- Render keep-alive ----------
async def handle(request):
    return web.Response(text="🤖 WhatsApp Automation Bot Running ✅")

def start_web():
    app = web.Application()
    app.router.add_get("/", handle)
    port = int(os.environ.get("PORT", 10000))
    web.run_app(app, port=port)

# ---------- Check if wa.js is running ----------
def is_wa_running():
    result = subprocess.run(["pgrep", "-f", "node wa.js"], capture_output=True, text=True)
    return bool(result.stdout.strip())

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

# ---------- Start command ----------
@dp.message_handler(commands=['start'])
async def start_msg(msg: types.Message):
    uid = msg.from_user.id
    status_text = "❌ Not connected"
    if uid in user_whatsapp:
        status_text = f"✅ Connected: {user_whatsapp[uid]}"
    await msg.reply(
        f"🤖 WhatsApp Automation Panel\n\n"
        f"Status: {status_text}\n"
        f"Select an option from the menu below:",
        reply_markup=menu(uid)
    )

# ---------- Button callbacks ----------
@dp.callback_query_handler(lambda c: True)
async def cb(call: types.CallbackQuery):
    uid = call.from_user.id

    # ---------- WhatsApp connect ----------
    if call.data == "connect":
        if os.path.exists("wa_connected.flag") or is_wa_running():
            number = "unknown"
            if os.path.exists("wa_connected.flag"):
                with open("wa_connected.flag") as f:
                    number = f.read().strip()
                user_whatsapp[uid] = number
            await call.message.reply(f"✅ WhatsApp already connected: {number}")
            return

        # Start WhatsApp bot
        subprocess.Popen(["node", "wa.js"])
        await call.message.edit_text(
            "🔹 Generating WhatsApp QR code...\n"
            "⚠️ You have 30 seconds to scan the QR code before it expires."
        )

        # Poll QR
        for _ in range(30):
            if os.path.exists("qr.png"):
                await bot.send_photo(uid, open("qr.png", "rb"),
                                     caption="Scan this QR with WhatsApp within 30 seconds!")
                os.remove("qr.png")
                break
            time.sleep(1)

        # Poll connection flag
        for _ in range(30):
            if os.path.exists("wa_connected.flag"):
                with open("wa_connected.flag") as f:
                    number = f.read().strip()
                    user_whatsapp[uid] = number
                await bot.send_message(uid, f"✅ WhatsApp connected: {number}")
                os.remove("wa_connected.flag")
                break
            time.sleep(1)

    # ---------- Logout WhatsApp ----------
    elif call.data == "logout":
        if uid in user_whatsapp:
            # Kill running wa.js process
            subprocess.run(["pkill", "-f", "node wa.js"])
            await bot.send_message(uid, f"🔓 WhatsApp logged out: {user_whatsapp[uid]}")
            del user_whatsapp[uid]
        else:
            await bot.send_message(uid, "❌ No WhatsApp connected")

    # ---------- Bulk group creation ----------
    elif call.data == "bulk":
        if uid not in user_whatsapp:
            await call.message.reply("❌ Connect WhatsApp first!")
            return
        state[uid] = "COUNT"
        await call.message.edit_text("Enter the number of groups to create:")

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

# ---------- Start ----------
if __name__ == "__main__":
    Thread(target=start_web).start()
    executor.start_polling(dp, skip_updates=True)
