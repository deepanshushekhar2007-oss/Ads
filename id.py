import os
import re
import asyncio
import threading
from flask import Flask

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestUser,
)
from aiogram.enums import ParseMode

from telethon import TelegramClient
from telethon.sessions import StringSession

# ================= ENV VARIABLES =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
PORT = int(os.getenv("PORT", 10000))

# ================= SAFETY CHECK =================
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN missing in environment variables")

# ================= INIT =================
bot = Bot(
    token=BOT_TOKEN,
    default={"parse_mode": ParseMode.HTML}   # ✅ FIXED
)

dp = Dispatcher()

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH
)

# ================= FLASK HEALTH CHECK =================
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "🚀 Telegram ID Finder Bot is running!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

# ⚠️ IMPORTANT: thread yaha start mat karo
# (Render crash avoid karne ke liye niche start karenge)

# ================= UI HELPERS =================

DIVIDER = "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"
FOOTER = "\n\n<i>🤖 <a href='https://t.me/SPIDYWS'>@SPIDYWS</a></i>"

def main_menu_keyboard():
    request_user_btn = KeyboardButtonRequestUser(
        request_id=1,
        user_is_bot=False,
    )

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Select User", request_user=request_user_btn)],
            [
                KeyboardButton(text="ℹ️ Help"),
                KeyboardButton(text="🔗 My ID"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Send a link, @username or forward a message…",
    )
    return keyboard

def format_result(icon: str, title: str, fields: dict) -> str:
    lines = [f"<b>{icon} {title}</b>", DIVIDER]
    for key, value in fields.items():
        lines.append(f"<b>{key}</b>  <code>{value}</code>")
    lines.append(DIVIDER)
    lines.append(FOOTER)
    return "\n".join(lines)

def error_msg(text: str) -> str:
    return f"<b>❌ Error</b>\n{DIVIDER}\n{text}{FOOTER}"

# ================= START COMMAND =================
@dp.message(Command("start"))
async def start(message: types.Message):
    name = message.from_user.first_name or "there"
    await message.answer(
        f"<b>👋 Hello, {name}!</b>\n"
        f"{DIVIDER}\n"
        "<b>🔍 Telegram ID Finder</b> — detect any Telegram ID instantly.\n\n"
        "<b>What I can detect:</b>\n"
        "  🔗  Group / Channel links\n"
        "  📩  Forwarded messages (chat + user)\n"
        "  👤  Usernames  <code>@example</code>\n"
        "  🔗  Message links  <code>t.me/c/…/…</code>\n"
        "  📲  Contact cards (via <b>Select User</b> button)\n\n"
        f"<i>Tap a button below or just send something!</i>{FOOTER}",
        reply_markup=main_menu_keyboard(),
    )

# ================= HELP BUTTON =================
@dp.message(F.text == "ℹ️ Help")
async def help_handler(message: types.Message):
    await message.answer(
        "<b>📖 How to use</b>\n"
        f"{DIVIDER}\n"
        "1️⃣ Forward any message → get sender/chat ID\n"
        "2️⃣ Send a @username → get user ID\n"
        "3️⃣ Send a t.me link → get chat/channel ID\n"
        "4️⃣ Tap 👤 Select User → pick contact\n"
        "5️⃣ Send message link (t.me/c/...)\n"
        f"{DIVIDER}{FOOTER}",
        reply_markup=main_menu_keyboard(),
    )

# ================= MY ID BUTTON =================
@dp.message(F.text == "🔗 My ID")
async def my_id_handler(message: types.Message):
    user = message.from_user

    fields = {
        "🆔 Your User ID": user.id,
        "👤 Name": user.full_name,
    }

    if user.username:
        fields["🔗 Username"] = f"@{user.username}"

    await message.answer(
        format_result("🆔", "Your Telegram ID", fields),
        reply_markup=main_menu_keyboard(),
    )
# ================= USER SHARED (Select User button) =================
@dp.message(F.user_shared)
async def user_shared_handler(message: types.Message):
    """Handles a contact shared via the 'Select User' button."""
    
    shared = message.user_shared
    user_id = shared.user_id

    extra_fields = {}

    try:
        # ✅ Ensure client connected (important for Render)
        if not client.is_connected():
            await client.connect()

        entity = await client.get_entity(user_id)

        name = getattr(entity, "first_name", "") or ""
        last = getattr(entity, "last_name", "") or ""
        full_name = f"{name} {last}".strip() or "Unknown"

        username = getattr(entity, "username", None)

        extra_fields["👤 Name"] = full_name

        if username:
            extra_fields["🔗 Username"] = f"@{username}"

    except Exception as e:
        print("Telethon Error:", e)   # ✅ debug ke liye useful
        # fail silently (bot crash nahi karega)

    fields = {
        "🆔 User ID": user_id,
        **extra_fields
    }

    await message.answer(
        format_result("📲", "Selected User Found", fields),
        reply_markup=main_menu_keyboard(),
    )
# ================= MAIN HANDLER =================
@dp.message()
async def finder(message: types.Message):
    text = (message.text or "").strip()

    try:
        # ✅ Ensure Telethon connected
        if not client.is_connected():
            await client.connect()

        # ── Forwarded from a Chat/Channel ─────────────────────────
        if message.forward_from_chat:
            chat = message.forward_from_chat
            fields = {
                "📛 Name": chat.title or "Unknown",
                "🆔 Chat ID": chat.id,
                "🏷 Type": str(chat.type),
            }
            if getattr(chat, "username", None):
                fields["🔗 Username"] = f"@{chat.username}"

            await message.reply(format_result("📩", "Forwarded Chat", fields),
                                reply_markup=main_menu_keyboard())
            return

        # ── Forwarded from User ───────────────────────────────────
        if message.forward_from:
            user = message.forward_from
            fields = {
                "🆔 User ID": user.id,
                "👤 Name": user.full_name or "Unknown",
            }
            if user.username:
                fields["🔗 Username"] = f"@{user.username}"

            await message.reply(format_result("👤", "Forwarded User", fields),
                                reply_markup=main_menu_keyboard())
            return

        # ── Message Link (PRIVATE) t.me/c/... ─────────────────────
        msg_link = re.search(r"t\.me/c/(\d+)/(\d+)", text)
        if msg_link:
            chat_id = f"-100{msg_link.group(1)}"
            msg_id = msg_link.group(2)

            await message.reply(
                format_result("🔗", "Private Message Link", {
                    "🆔 Chat ID": chat_id,
                    "📨 Message ID": msg_id,
                }),
                reply_markup=main_menu_keyboard(),
            )
            return

        # ── Public / Private Link t.me/... ────────────────────────
        public = re.search(r"(?:https?://)?t\.me/([A-Za-z0-9_]+)", text)
        if public:
            username = public.group(1)

            skip = {"joinchat", "addstickers", "share", "iv", "c"}

            if username.lower() not in skip:
                try:
                    entity = await client.get_entity(username)

                    entity_id = getattr(entity, "id", None)

                    # 🔥 MAIN FIX → force -100 for groups/channels
                    if str(type(entity)).lower().find("channel") != -1:
                        entity_id = int(f"-100{entity_id}")

                    title = getattr(entity, "title", None) or getattr(entity, "first_name", username)
                    entity_type = type(entity).__name__

                    fields = {
                        "📛 Name": title,
                        "🆔 Chat ID": entity_id,
                        "🏷 Type": entity_type,
                    }

                    uname = getattr(entity, "username", None)
                    if uname:
                        fields["🔗 Username"] = f"@{uname}"

                    icon = "👤" if "User" in entity_type else "📢"

                    await message.reply(
                        format_result(icon, "Entity Found", fields),
                        reply_markup=main_menu_keyboard(),
                    )

                except Exception as e:
                    print("Link Error:", e)
                    await message.reply(
                        error_msg("❌ Could not fetch that link. It may be private."),
                        reply_markup=main_menu_keyboard(),
                    )
                return

        # ── @Username ─────────────────────────────────────────────
        if text.startswith("@"):
            username_clean = text.lstrip("@")

            try:
                entity = await client.get_entity(username_clean)

                entity_id = getattr(entity, "id", None)

                if str(type(entity)).lower().find("channel") != -1:
                    entity_id = int(f"-100{entity_id}")

                name = getattr(entity, "first_name", None) or getattr(entity, "title", username_clean)
                last = getattr(entity, "last_name", "") or ""
                full = f"{name} {last}".strip()

                entity_type = type(entity).__name__

                fields = {
                    "🆔 ID": entity_id,
                    "👤 Name": full,
                    "🏷 Type": entity_type,
                }

                uname = getattr(entity, "username", None)
                if uname:
                    fields["🔗 Username"] = f"@{uname}"

                icon = "👤" if "User" in entity_type else "📢"

                await message.reply(
                    format_result(icon, "User Found", fields),
                    reply_markup=main_menu_keyboard(),
                )

            except Exception as e:
                print("Username Error:", e)
                await message.reply(
                    error_msg("User not found."),
                    reply_markup=main_menu_keyboard(),
                )
            return

        # ── Numeric ID ────────────────────────────────────────────
        if text.lstrip("-").isdigit():
            numeric_id = int(text)

            try:
                entity = await client.get_entity(numeric_id)

                name = getattr(entity, "first_name", None) or getattr(entity, "title", str(numeric_id))
                entity_type = type(entity).__name__

                fields = {
                    "🆔 ID": numeric_id,
                    "📛 Name": name,
                    "🏷 Type": entity_type,
                }

                await message.reply(
                    format_result("🔢", "Entity Lookup", fields),
                    reply_markup=main_menu_keyboard(),
                )

            except:
                await message.reply(
                    format_result("🔢", "Numeric ID", {"🆔 ID": numeric_id}),
                    reply_markup=main_menu_keyboard(),
                )
            return

        # ── Fallback ──────────────────────────────────────────────
        await message.reply(
                            error_msg(
                "Send:\n• @username\n• t.me link\n• forward message"
                    ),
                            reply_markup=main_menu_keyboard(),
                        )

                    except Exception as e:
                        print("MAIN ERROR:", e)
                        await message.reply(
                            error_msg("Something went wrong."),
                            reply_markup=main_menu_keyboard(),
                        )

        # ── Numeric ID ────────────────────────────────────────────────────────
        if text.lstrip("-").isdigit():
            numeric_id = int(text)
            try:
                entity = await client.get_entity(numeric_id)
                name = getattr(entity, "first_name", None) or getattr(entity, "title", str(numeric_id))
                entity_type = type(entity).__name__
                fields = {
                    "🆔 ID": numeric_id,
                    "📛 Name": name,
                    "🏷 Type": entity_type,
                }
                uname = getattr(entity, "username", None)
                if uname:
                    fields["🔗 Username"] = f"@{uname}"
                icon = "👤" if "User" in entity_type else "📢"
                await message.reply(
                    format_result(icon, "Entity Lookup", fields),
                    reply_markup=main_menu_keyboard(),
                )
            except Exception:
                await message.reply(
                    format_result("🔢", "Numeric ID", {"🆔 ID": numeric_id}),
                    reply_markup=main_menu_keyboard(),
                )
            return

        # ── Fallback ──────────────────────────────────────────────────────────
        await message.reply(
            error_msg(
                "I couldn't detect any ID from that.\n\n"
                "<b>Try sending:</b>\n"
                "• A <code>@username</code>\n"
                "• A <code>t.me/...</code> link\n"
                "• A forwarded message\n"
                "• Use the <b>👤 Select User</b> button"
            ),
            reply_markup=main_menu_keyboard(),
        )

    except Exception as e:
        print("ERROR:", e)
        await message.reply(
            error_msg("Something went wrong. Please try again."),
            reply_markup=main_menu_keyboard(),
        )

# ================= RUN BOT =================
async def main():
    # ✅ Telethon start
    await client.start()

    print("🚀 Telegram Bot started...")

    # ✅ Start bot polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    # ✅ Flask server thread (IMPORTANT for Render)
    threading.Thread(target=run_flask).start()

    # ✅ Run bot
    asyncio.run(main())