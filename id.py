import os
import re
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from telethon import TelegramClient
from telethon.sessions import StringSession
from aiohttp import web

# ================= ENV VARIABLES =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
PORT = int(os.getenv("PORT", 8000))  # Render automatically provides PORT

# ================= TELETHON CLIENT =================
try:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
except Exception as e:
    print("⚠️ Error initializing Telethon client:", e)
    client = None

# ================= AIROGRAM BOT =================
bot = Bot(token=BOT_TOKEN, session=AiohttpSession())
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ================= HELPER FUNCTION =================
def build_msg(title: str, data: dict):
    msg = f"<b>🔹 {title}</b>\n━━━━━━━━━━━━━━━\n"
    for k, v in data.items():
        msg += f"• <b>{k}:</b> <code>{v}</code>\n"
    msg += "━━━━━━━━━━━━━━━\n<i>Made by @SPIDYWS</i>"
    return msg

# ================= START COMMAND =================
@dp.message()
async def start_cmd(message: types.Message):
    if message.text and message.text.lower() == "/start":
        await message.answer(
            "<b>🚀 Ultimate Telegram ID Finder 🚀</b>\n\n"
            "🔎 Detect Chat IDs, User IDs & Message IDs easily!\n\n"
            "<b>Send anything:</b>\n"
            "🔗 Group / Channel Link\n"
            "📊 Message Link\n"
            "📩 Forwarded Message\n"
            "👤 Username\n\n"
            "💡 Example:\nhttps://t.me/python/10\n\n"
            "<i>Made by: @SPIDYWS</i>"
        )

# ================= MAIN HANDLER =================
@dp.message()
async def finder(message: types.Message):
    text = (message.text or "").strip()
    try:
        # ---------- Forwarded Chat ----------
        if message.forward_from_chat:
            chat = message.forward_from_chat
            await message.reply(build_msg("Forwarded Chat Found", {"Name": chat.title, "Chat ID": chat.id}))
            return

        # ---------- Forwarded User ----------
        if message.forward_from:
            user = message.forward_from
            await message.reply(build_msg("Forwarded User Found", {"User ID": user.id, "Username": user.username or "N/A"}))
            return

        # ---------- Message Link ----------
        msg_link = re.search(r"t\.me\/c\/(\d+)\/(\d+)", text)
        if msg_link:
            chat_id = int(f"-100{msg_link.group(1)}")
            await message.reply(build_msg("Message Link Detected", {"Chat ID": chat_id}))
            return

        # ---------- Public Link ----------
        public = re.search(r"t\.me\/([A-Za-z0-9_]+)", text)
        if public and client:
            username = public.group(1)
            try:
                chat = await client.get_entity(username)
                chat_id = getattr(chat, "id", "N/A")
                name = getattr(chat, "title", username)
                await message.reply(build_msg("Chat Found", {"Name": name, "Chat ID": chat_id}))
            except Exception:
                await message.reply("❌ Unable to fetch chat ID")
            return

        # ---------- Username ----------
        if text.startswith("@") and client:
            try:
                entity = await client.get_entity(text)
                await message.reply(build_msg("User Found", {"User ID": entity.id, "Username": getattr(entity, 'username', 'N/A')}))
            except Exception:
                await message.reply("❌ User not found")
            return

        # ---------- No match ----------
        await message.reply("❌ Unable to detect ID")

    except Exception as e:
        print("ERROR:", e)
        await message.reply("❌ Something went wrong! Make sure the input is correct.")

# ================= WEBHOOK SERVER =================
async def handle(request):
    update = await request.json()
    from aiogram.dispatcher.webhook import DispatcherWebhookHandler
    await DispatcherWebhookHandler(dp, update)
    return web.Response(text="OK")

async def on_startup(app):
    if client:
        await client.start()
        print("✅ Telethon client started")
    print("🚀 Bot webhook ready...")

app = web.Application()
app.router.add_post(f"/bot{BOT_TOKEN}", handle)
app.on_startup.append(on_startup)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
