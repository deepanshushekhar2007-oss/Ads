import os
import re
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import UsernameNotOccupiedError, ChannelInvalidError
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.bot import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

# ================= ENV VARIABLES =================
BOT_TOKEN = os.getenv("BOT_TOKEN")          # Bot token for aiogram interface
API_ID = int(os.getenv("API_ID", 0))        # Telethon API ID
API_HASH = os.getenv("API_HASH")            # Telethon API HASH
SESSION_STRING = os.getenv("SESSION_STRING")# Telethon userbot session string

# ================= TELETHON CLIENT =================
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ================= AIROGRAM BOT =================
default_props = DefaultBotProperties(parse_mode="HTML")
bot = Bot(token=BOT_TOKEN, default=default_props, session=AiohttpSession())
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
            await message.reply(build_msg("Forwarded Chat", {"Name": chat.title, "Chat ID": chat.id}))
            return

        # ---------- Forwarded User ----------
        if message.forward_from:
            user = message.forward_from
            await message.reply(build_msg("Forwarded User", {"User ID": user.id, "Name": f"{user.first_name or ''} {user.last_name or ''}".strip()}))
            return

        # ---------- Message Link t.me/c/... ----------
        msg_link = re.search(r"t\.me\/c\/(\d+)\/(\d+)", text)
        if msg_link:
            try:
                chat_part = int(msg_link.group(1))
                msg_id = int(msg_link.group(2))
                chat_id = -1000000000000 + chat_part  # Convert to proper channel ID
                msg_entity = await client.get_messages(chat_id, ids=msg_id)
                await message.reply(build_msg("Message Link", {"Chat ID": chat_id, "Message ID": msg_id}))
            except Exception as e:
                await message.reply(f"❌ Unable to fetch message link\n<code>{e}</code>")
            return

        # ---------- Public Link t.me/username ----------
        public = re.search(r"t\.me\/([A-Za-z0-9_]+)", text)
        if public:
            username = public.group(1)
            try:
                entity = await client.get_entity(username)
                name = getattr(entity, "title", getattr(entity, "first_name", username))
                eid = getattr(entity, "id", "N/A")
                await message.reply(build_msg("Public Chat/User Found", {"Name": name, "ID": eid}))
            except (UsernameNotOccupiedError, ChannelInvalidError):
                await message.reply("❌ Username / public link not found")
            except Exception as e:
                await message.reply(f"❌ Error fetching public link\n<code>{e}</code>")
            return

        # ---------- Username @username ----------
        if text.startswith("@"):
            try:
                entity = await client.get_entity(text)
                await message.reply(build_msg("User Found", {"User ID": entity.id, "Name": getattr(entity, "first_name", "")}))
            except Exception as e:
                await message.reply(f"❌ User not found\n<code>{e}</code>")
            return

        # ---------- No match ----------
        await message.reply("❌ Unable to detect ID")

    except Exception as e:
        print("ERROR:", e)
        await message.reply(f"❌ Something went wrong!\n<code>{e}</code>")

# ================= RUN BOT =================
async def main():
    await client.start()
    print("🚀 Telethon client started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
