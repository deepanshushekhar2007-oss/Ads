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

# ---------- Render keep-alive ----------
async def handle(request):
    status_msg = "Bot is running ✅\n"
    if os.path.exists("wa_connected.flag"):
        with open("wa_connected.flag", "r") as f:
            ws_number = f.read().strip()
        status_msg += f"WhatsApp connected: {ws_number}"
    else:
        status_msg += "WhatsApp not connected ❌"
    return web.Response(text=status_msg)

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
    if os.path.exists("wa_connected.flag"):
        kb.add(InlineKeyboardButton("❌ Logout WhatsApp", callback_data="logout"))
    return kb

@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    status = "WhatsApp not connected ❌"
    if os.path.exists("wa_connected.flag"):
        with open("wa_connected.flag", "r") as f:
            status = f"WhatsApp connected: {f.read().strip()}"
    await msg.reply(
        f"🤖 WhatsApp Automation Panel\n\nStatus: {status}\n\nSelect an option from the menu below:",
        reply_markup=menu()
    )

# ---------- Button callbacks ----------
@dp.callback_query_handler(lambda c: True)
async def cb(call: types.CallbackQuery):
    uid = call.from_user.id

    # ---------- WhatsApp connect ----------
    if call.data == "connect":
        if os.path.exists("wa_connected.flag"):
            with open("wa_connected.flag", "r") as f:
                ws_number = f.read().strip()
            await call.answer(f"✅ WhatsApp already connected: {ws_number}", show_alert=True)
            return

        os.system("node wa.js &")
        await call.message.edit_text(
            "🔹 Generating WhatsApp QR code...\n"
            "⚠️ Scan QR within 30 seconds or it will expire."
        )

        # Poll QR
        for _ in range(30):
            if os.path.exists("qr.png"):
                await bot.send_photo(uid, open("qr.png", "rb"),
                                     caption="Scan this QR in WhatsApp within 30 seconds!")
                os.remove("qr.png")
                break
            time.sleep(1)

        # Poll WhatsApp connection
        for _ in range(30):
            if os.path.exists("wa_connected.flag"):
                with open("wa_connected.flag", "r") as f:
                    ws_number = f.read().strip()
                await bot.send_message(uid, f"✅ WhatsApp connected: {ws_number}")
                break
            time.sleep(1)

    # ---------- Logout WhatsApp ----------
    elif call.data == "logout":
        if os.path.exists("wa_connected.flag"):
            os.remove("wa_connected.flag")
            if os.path.exists("auth"):
                os.system("rm -rf auth")
            await call.answer("❌ WhatsApp logged out successfully.", show_alert=True)
        else:
            await call.answer("WhatsApp is not connected.", show_alert=True)

    # ---------- Bulk Group Creator ----------
    elif call.data == "bulk":
        if not os.path.exists("wa_connected.flag"):
            await call.answer("❌ WhatsApp not connected. Please connect first.", show_alert=True)
            return
        state[uid] = "COUNT"
        await call.message.edit_text("Enter the number of groups to create:")

    # ---------- Join via link ----------
    elif call.data == "join":
        if not os.path.exists("wa_connected.flag"):
            await call.answer("❌ WhatsApp not connected. Please connect first.", show_alert=True)
            return
        state[uid] = "JOIN"
        await call.message.edit_text("Send invite link(s), one per line:")

    # ---------- Add via VCF ----------
    elif call.data == "vcf":
        if not os.path.exists("wa_connected.flag"):
            await call.answer("❌ WhatsApp not connected. Please connect first.", show_alert=True)
            return
        state[uid] = "VCF_FILE"
        await call.message.edit_text("Upload your VCF file containing participants:")

# ---------- Text messages ----------
@dp.message_handler(content_types=['text'])
async def text(msg: types.Message):
    uid = msg.from_user.id
    if uid not in state:
        return

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
        await msg.reply("Do you want to add a group description?", reply_markup=kb)

    elif state[uid] == "NUMBERS":
        data[uid]["numbers"] = msg.text
        state[uid] = "DP_OPTION"
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("Yes", callback_data="dp_yes"),
            InlineKeyboardButton("No", callback_data="dp_no")
        )
        await msg.reply("Do you want to add a group DP?", reply_markup=kb)

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
    # Ask group settings toggle
    state[uid] = "GROUP_SETTINGS"
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Admin Only", callback_data="setting_admin"),
        InlineKeyboardButton("Invite Link", callback_data="setting_invite"),
        InlineKeyboardButton("Send Messages", callback_data="setting_msg"),
        InlineKeyboardButton("Send Media", callback_data="setting_media"),
        InlineKeyboardButton("Save & Create Group", callback_data="save_group")
    )
    await msg.reply("Configure group settings (toggle buttons):", reply_markup=kb)

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
