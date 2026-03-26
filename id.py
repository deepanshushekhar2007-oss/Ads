import os
import re
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from telethon import TelegramClient
from telethon.sessions import StringSession
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# ================= ENV VARIABLES =================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")

# ================= INIT =================
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

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
        # Forwarded Chat
        if message.forward_from_chat:
            chat = message.forward_from_chat
            await message.reply(build_msg("📩 Forwarded Chat Found", {"Name": chat.title, "Chat ID": chat.id}))
            return

        # Forwarded User
        if message.forward_from:
            user_id = message.forward_from.id
            await message.reply(build_msg("👤 Forwarded User Found", {"User ID": user_id}))
            return

        # Message Link
        msg_link = re.search(r"t\.me\/c\/(\d+)\/(\d+)", text)
        if msg_link:
            chat_id = f"-100{msg_link.group(1)}"
            await message.reply(build_msg("📊 Message Link Detected", {"Chat ID": chat_id}))
            return

        # Public Link
        public = re.search(r"t\.me\/([A-Za-z0-9_]+)", text)
        if public:
            username = public.group(1)
            try:
                chat = await client.get_entity(username)
                chat_id = getattr(chat, "id", "N/A")
                name = getattr(chat, "title", username)
                await message.reply(build_msg("🔗 Chat Found", {"Name": name, "Chat ID": chat_id}))
            except:
                await message.reply("❌ Unable to fetch chat ID")
            return

        # Username
        if text.startswith("@"):
            try:
                entity = await client.get_entity(text)
                await message.reply(build_msg("👤 User Found", {"User ID": entity.id}))
            except:
                await message.reply("❌ User not found")
            return

        # No match
        await message.reply("❌ Unable to detect ID")

    except Exception as e:
        print("ERROR:", e)
        await message.reply("❌ Something went wrong! Make sure the input is correct.")

# ================= RUN BOT =================
async def main():
    await client.start()
    print("🚀 Bot started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
