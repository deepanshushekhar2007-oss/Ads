import os
import time
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from threading import Thread

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

state = {}
data = {}
user_whatsapp = {}  # Track which user has connected which WhatsApp

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
    if uid in user_whatsapp:
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
        if uid in user_whatsapp:
            await call.message.reply(f"✅ WhatsApp already connected: {user_whatsapp[uid]}")
            return

        os.system("node wa.js &")
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

        # Poll WhatsApp connection flag
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
            os.system("node logout.js")  # Must handle logout in wa.js
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

# ---------- Text messages ----------
@dp.message_handler(content_types=['text'])
async def text(msg: types.Message):
    uid = msg.from_user.id
    if uid not in state:
        return

    # Bulk group creation flow
    if state[uid] == "COUNT":
        data[uid] = {"count": int(msg.text)}
        state[uid] = "NAME"
        await msg.reply("Enter base group name:")

    elif state[uid] == "NAME":
        data[uid]["name"] = msg.text
        state[uid] = "DESC_OPTION"
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("Yes", callback_data="desc_yes"),
            InlineKeyboardButton("No", callback_data="desc_no")
        )
        await msg.reply("Do you want to add description?", reply_markup=kb)

    elif state[uid] == "DESC":
        data[uid]["desc"] = msg.text
        state[uid] = "NUMBERS"
        await msg.reply("Send participant numbers (comma separated):")

    elif state[uid] == "JOIN":
        links = msg.text.splitlines()
        os.system(f"node join.js '{','.join(links)}'")
        await msg.reply("Joining groups via link(s)...")
        state.pop(uid)

    elif state[uid] == "VCF_LINK":
        link = msg.text
        os.system(f"node add.js {link}")
        await msg.reply("Adding members from VCF...")
        state.pop(uid)

# ---------- Photo handler ----------
@dp.message_handler(content_types=['photo'])
async def photo(msg: types.Message):
    uid = msg.from_user.id
    if state.get(uid) != "DP":
        return
    await msg.photo[-1].download("dp.jpg")
    os.system("node create.js")
    await msg.reply("Creating groups...")
    state.pop(uid)

# ---------- Document handler (VCF) ----------
@dp.message_handler(content_types=['document'])
async def doc(msg: types.Message):
    uid = msg.from_user.id
    if state.get(uid) != "VCF_FILE":
        return
    await msg.document.download("contacts.vcf")
    state[uid] = "VCF_LINK"
    await msg.reply("Send the WhatsApp group invite link to add members:")

# ---------- Start ----------
if __name__ == "__main__":
    Thread(target=start_web).start()
    executor.start_polling(dp, skip_updates=True)
