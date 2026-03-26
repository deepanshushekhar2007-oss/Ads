import os
import re
import asyncio
from aiogram import types, Dispatcher
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.bot import Bot
from aiogram.client.bot_api import DefaultBotProperties
from telethon import TelegramClient
from telethon.sessions import StringSession

# ================= ENV VARIABLES =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")

# ================= TELETHON CLIENT =================
try:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
except Exception as e:
    print("⚠️ Error initializing Telethon client:", e)
    client = None

# ================= AIROGRAM BOT =================
default_props = DefaultBotProperties(parse_mode="HTML")
bot = Bot(token=BOT_TOKEN, default=default_props, session=AiohttpSession())
dp = Dispatcher()

# ================= HELPER FUNCTION =================
def build_msg(title: str, data: dict):
    msg = f"<b>🔹 {title}</b>\n━━━━━━━━━━━━━━━\n"
    for k, v in data.items():
        msg += f"• <b>{k}:</b> <code>{v}</code>\n"
    msg += "━━━━━━━━━━━━━━━\n<i>Made by @SPIDYWS</i>"
    return msg

# ================= START COMMAND =================
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

# ================= MAIN HANDLER =================
@dp.message()
async def finder(message: types.Message):
    text = (message.text or "").strip()
    try:
        # ---------- Forwarded Chat ----------
        if message.forward_from_chat:
            chat = message.forward_from_chat
            await message.reply(
                f"<b>📩 Forwarded Chat Found</b>\n"
                "━━━━━━━━━━━━━━━\n"
                f"• <b>Name:</b> {chat.title}\n"
                f"• <b>Chat ID:</b> <code>{chat.id}</code>\n"
                "━━━━━━━━━━━━━━━\n"
                "<i>Made by @SPIDYWS</i>"
            )
            return

        # ---------- Forwarded User ----------
        if message.forward_from:
            user_id = message.forward_from.id
            await message.reply(
                f"<b>👤 Forwarded User Found</b>\n"
                "━━━━━━━━━━━━━━━\n"
                f"• <b>User ID:</b> <code>{user_id}</code>\n"
                "━━━━━━━━━━━━━━━\n"
                "<i>Made by @SPIDYWS</i>"
            )
            return

        # ---------- Message Link ----------
        msg_link = re.search(r"t\.me\/c\/(\d+)\/(\d+)", text)
        if msg_link:
            chat_id = f"-100{msg_link.group(1)}"
            await message.reply(
                f"<b>📊 Message Link Detected</b>\n"
                "━━━━━━━━━━━━━━━\n"
                f"• <b>Chat ID:</b> <code>{chat_id}</code>\n"
                "━━━━━━━━━━━━━━━\n"
                "<i>Made by @SPIDYWS</i>"
            )
            return

        # ---------- Public Link ----------
        public = re.search(r"t\.me\/([A-Za-z0-9_]+)", text)
        if public and client:
            username = public.group(1)
            try:
                chat = await client.get_entity(username)
                chat_id = getattr(chat, "id", "N/A")
                name = getattr(chat, "title", username)
                await message.reply(
                    f"<b>🔗 Chat Found</b>\n"
                    "━━━━━━━━━━━━━━━\n"
                    f"• <b>Name:</b> {name}\n"
                    f"• <b>Chat ID:</b> <code>{chat_id}</code>\n"
                    "━━━━━━━━━━━━━━━\n"
                    "<i>Made by @SPIDYWS</i>"
                )
            except Exception:
                await message.reply("❌ Unable to fetch chat ID")
            return

        # ---------- Username ----------
        if text.startswith("@") and client:
            try:
                entity = await client.get_entity(text)
                await message.reply(
                    f"<b>👤 User Found</b>\n"
                    "━━━━━━━━━━━━━━━\n"
                    f"• <b>User ID:</b> <code>{entity.id}</code>\n"
                    "━━━━━━━━━━━━━━━\n"
                    "<i>Made by @SPIDYWS</i>"
                )
            except Exception:
                await message.reply("❌ User not found")
            return

        # ---------- No match ----------
        await message.reply("❌ Unable to detect ID")

    except Exception as e:
        print("ERROR:", e)
        await message.reply("❌ Something went wrong! Make sure the input is correct.")

# ================= RUN BOT =================
async def main():
    if client:
        await client.start()
    print("🚀 Bot started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
