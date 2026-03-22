import os
import subprocess
import asyncio
from io import BytesIO
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiohttp import web
import base64

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

state = {}
data = {}

# ---------- Render keep alive ----------
async def handle(request):
    return web.Response(text="running")

def start_web():
    app = web.Application()
    app.router.add_get("/", handle)
    port = int(os.environ.get("PORT", 10000))
    web.run_app(app, port=port)

# ---------- menu ----------
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
    await msg.reply("🤖 WhatsApp Automation Panel", reply_markup=menu())

# ---------- buttons ----------
@dp.callback_query_handler(lambda c: True)
async def cb(call: types.CallbackQuery):
    uid = call.from_user.id

    if call.data == "connect":
        # Start Node process
        proc = subprocess.Popen(
            ["node", "wa.js"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.getcwd()
        )
        await call.message.edit_text("Generating QR...")

        # Read QR base64 from Node stdout
        while True:
            line = proc.stdout.readline()
            if not line:
                await asyncio.sleep(0.5)
                continue
            if "QR_BASE64_START" in line:
                qr_data = ""
                while True:
                    qr_line = proc.stdout.readline()
                    if "QR_BASE64_END" in qr_line:
                        break
                    qr_data += qr_line
                # Send QR to Telegram
                qr_bytes = base64.b64decode(qr_data.split(",")[1])
                await bot.send_photo(uid, BytesIO(qr_bytes))
                break

    elif call.data == "bulk":
        state[uid] = "COUNT"
        await call.message.edit_text("How many groups create?")

    elif call.data == "join":
        state[uid] = "JOIN"
        await call.message.edit_text("Send invite link(s) (one per line)")

    elif call.data == "vcf":
        state[uid] = "VCF_FILE"
        await call.message.edit_text("Upload VCF file")

# ---------- text ----------
@dp.message_handler(content_types=['text'])
async def text(msg: types.Message):
    uid = msg.from_user.id
    if uid not in state:
        return

    if state[uid] == "COUNT":
        data[uid] = {"count": int(msg.text)}
        state[uid] = "NAME"
        await msg.reply("Base group name?")

    elif state[uid] == "NAME":
        data[uid]["name"] = msg.text
        state[uid] = "DESC"
        await msg.reply("Description?")

    elif state[uid] == "DESC":
        data[uid]["desc"] = msg.text
        state[uid] = "NUMBERS"
        await msg.reply("Send participants numbers comma separated")

    elif state[uid] == "NUMBERS":
        data[uid]["numbers"] = msg.text
        state[uid] = "DP"
        await msg.reply("Send group DP image")

    elif state[uid] == "JOIN":
        links = msg.text.splitlines()
        for link in links:
            subprocess.Popen(["node", "join.js", link.strip()])
        await msg.reply("Joining groups...")
        state.pop(uid)

    elif state[uid] == "VCF_LINK":
        link = msg.text
        subprocess.Popen(["node", "add.js", link])
        await msg.reply("Adding members from VCF...")
        state.pop(uid)

# ---------- photo ----------
@dp.message_handler(content_types=['photo'])
async def photo(msg: types.Message):
    uid = msg.from_user.id
    if state.get(uid) != "DP":
        return
    await msg.photo[-1].download("dp.jpg")
    subprocess.Popen(["node", "create.js"])
    await msg.reply("Creating groups...")
    state.pop(uid)

# ---------- vcf upload ----------
@dp.message_handler(content_types=['document'])
async def doc(msg: types.Message):
    uid = msg.from_user.id
    if state.get(uid) != "VCF_FILE":
        return
    await msg.document.download("contacts.vcf")
    state[uid] = "VCF_LINK"
    await msg.reply("Send group invite link")

# ---------- start ----------
if __name__ == "__main__":
    from threading import Thread
    Thread(target=start_web).start()
    executor.start_polling(dp, skip_updates=True)
