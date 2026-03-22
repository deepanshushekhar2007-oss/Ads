import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from threading import Thread

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Set this in Render environment
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

state = {}
data = {}

# ---------- Render keep-alive ----------
async def handle(request):
    return web.Response(text="Bot is running ✅")

def start_web():
    app = web.Application()
    app.router.add_get("/", handle)
    port = int(os.environ.get("PORT", 10000))
    web.run_app(app, port=port)

# ---------- Telegram menu ----------
def menu():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🔗 Connect WhatsApp", callback_data="connect"),
        InlineKeyboardButton("⚡ Bulk Group Creator", callback_data="bulk"),
        InlineKeyboardButton("🔗 Join via Link", callback_data="join"),
        InlineKeyboardButton("📂 Add via VCF", callback_data="vcf")
    )
    return kb

@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    await msg.reply(
        "🤖 WhatsApp Automation Panel\n\n"
        "Select an option from the menu below:",
        reply_markup=menu()
    )

# ---------- Button callbacks ----------
@dp.callback_query_handler(lambda c: True)
async def cb(call: types.CallbackQuery):
    uid = call.from_user.id

    if call.data == "connect":
        # Run Node.js WhatsApp bot
        os.system("node wa.js &")
        await call.message.edit_text(
            "🔹 Generating WhatsApp QR code...\n"
            "⚠️ You have 30 seconds to scan the QR code before it expires."
        )

        # Async polling QR & connected status
        for _ in range(30):
            if os.path.exists("qr.png"):
                await bot.send_photo(uid, open("qr.png", "rb"),
                                     caption="📷 Scan this QR with WhatsApp within 30 seconds!")
                os.remove("qr.png")
                break
            await asyncio.sleep(1)

        for _ in range(30):
            if os.path.exists("wa_connected.flag"):
                await bot.send_message(uid, "✅ WhatsApp connected successfully!")
                os.remove("wa_connected.flag")
                break
            await asyncio.sleep(1)

    elif call.data == "bulk":
        state[uid] = "COUNT"
        await call.message.edit_text("Enter the number of groups to create:")

    elif call.data == "join":
        state[uid] = "JOIN"
        await call.message.edit_text("Send invite link(s), one per line:")

    elif call.data == "vcf":
        state[uid] = "VCF_FILE"
        await call.message.edit_text("Upload your VCF file containing participants:")

# ---------- Text messages ----------
@dp.message_handler(content_types=['text'])
async def text(msg: types.Message):
    uid = msg.from_user.id
    if uid not in state:
        return

    if state[uid] == "COUNT":
        try:
            data[uid] = {"count": int(msg.text)}
        except ValueError:
            await msg.reply("❌ Please enter a valid number.")
            return
        state[uid] = "NAME"
        await msg.reply("Enter base group name:")

    elif state[uid] == "NAME":
        data[uid]["name"] = msg.text
        state[uid] = "DESC"
        await msg.reply("Enter group description:")

    elif state[uid] == "DESC":
        data[uid]["desc"] = msg.text
        state[uid] = "NUMBERS"
        await msg.reply("Send participant numbers (comma separated):")

    elif state[uid] == "NUMBERS":
        data[uid]["numbers"] = msg.text
        state[uid] = "DP"
        await msg.reply("Send group DP image:")

    elif state[uid] == "JOIN":
        links = msg.text.splitlines()
        for link in links:
            os.system(f"node join.js {link.strip()}")
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
    Thread(target=start_web, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
