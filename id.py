import re
import asyncio
import os
from threading import Thread
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.bot import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from flask import Flask

# ===================== CONFIG =====================
BOT_TOKEN = "8355502020:AAHhZda0HyVe0pf-GHWFZcFHurZVtlz6snA"
API_ID = 34316889
API_HASH = "c902c878591621a436b1d24798121234"
SESSION_STRING = "1BVtsOK8Bu2ByB2lvcoDb9GVtRcf20R2QqnqVQIOQSqBkRCzvOqbHzsP623aIcs_yO-qcbE3nZLlf17O-Y9YFlH6S8AZBOKbBrPXLDnnjfl6w4Xrd2GU5plXNAmC9TpBwTlPJSTr2VwORZpK6i0kXO7s9izbPsU2mlcOYy_kLnp8oUkB4UFIWv3YM3zKGS0Tnx8ZnpQ55dFTwNujBKmmZaUJwx1gwY2j2TM68mnAFUslLjCJHrcpK7uZ9KJHc-XlU6lvlSYX3TPS06IrQcCvIF59z9nYDSWG8ihkBLnGgHWudw6t258JyCFKtbMopimtZP6xChj7z2MK_JaZgV3SwSfAF6QRJuHY="

# ===================== TELETHON CLIENT =====================
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ===================== AIROGRAM BOT =====================
default_props = DefaultBotProperties(parse_mode="HTML")
bot = Bot(token=BOT_TOKEN, default=default_props, session=AiohttpSession())
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===================== HELPERS =====================
def build_msg(title: str, data: dict):
    msg = f"<b>🔹 {title}</b>\n━━━━━━━━━━━━━━━\n"
    for k, v in data.items():
        msg += f"• <b>{k}:</b> <code>{v}</code>\n"
    msg += "━━━━━━━━━━━━━━━\n<i>Made by @SPIDYWS</i>"
    return msg

# ===================== START COMMAND =====================
@dp.message(Command("start"))
async def start(message: types.Message):
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

# ===================== MAIN HANDLER =====================
@dp.message()
async def finder(message: types.Message):
    text = (message.text or "").strip()
    try:
        if message.forward_from_chat:
            chat = message.forward_from_chat
            await message.reply(build_msg("📩 Forwarded Chat Found", {"Name": chat.title, "Chat ID": chat.id}))
            return
        if message.forward_from:
            user_id = message.forward_from.id
            await message.reply(build_msg("👤 Forwarded User Found", {"User ID": user_id}))
            return

        msg_link = re.search(r"t\.me\/c\/(\d+)\/(\d+)", text)
        if msg_link:
            chat_id = f"-100{msg_link.group(1)}"
            await message.reply(build_msg("📊 Message Link Detected", {"Chat ID": chat_id}))
            return

        public = re.search(r"t\.me\/([A-Za-z0-9_]+)", text)
        if public and client:
            username = public.group(1)
            try:
                chat = await client.get_entity(username)
                chat_id = getattr(chat, "id", "N/A")
                name = getattr(chat, "title", username)
                await message.reply(build_msg("🔗 Chat Found", {"Name": name, "Chat ID": chat_id}))
            except Exception:
                await message.reply("❌ Unable to fetch chat ID")
            return

        if text.startswith("@") and client:
            try:
                entity = await client.get_entity(text)
                await message.reply(build_msg("👤 User Found", {"User ID": entity.id}))
            except Exception:
                await message.reply("❌ User not found")
            return

        await message.reply("❌ Unable to detect ID")

    except Exception as e:
        print("ERROR:", e)
        await message.reply("❌ Something went wrong! Make sure the input is correct.")

# ===================== TELETHON AUTO-RECONNECT =====================
async def start_telethon():
    while True:
        try:
            print("🔌 Connecting to Telegram...")
            await client.start()
            print("✅ Telethon connected!")
            await client.run_until_disconnected()
        except Exception as e:
            print(f"⚠️ Telethon disconnected! Retrying in 5s... Error: {e}")
            await asyncio.sleep(5)

# ===================== FLASK KEEP-ALIVE =====================
app = Flask("keep_alive")

@app.route("/")
def home_flask():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Keep-alive running on port {port}")
    app.run(host="0.0.0.0", port=port)

# ===================== MAIN RUN =====================
async def main():
    # Start Telethon in background task
    telethon_task = asyncio.create_task(start_telethon())
    # Start Aiogram bot polling
    print("🚀 Aiogram Bot started...")
    await dp.start_polling(bot)
    # Keep Telethon alive
    await telethon_task

if __name__ == "__main__":
    # Start Flask for Render
    Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
