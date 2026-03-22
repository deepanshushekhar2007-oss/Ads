import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8418461342:AAH1NJEMnCnYROk6fZrA1hG-ewaV7v38Ndw"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(commands=["start"])
async def start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Connect WhatsApp", callback_data="connect")],
        [InlineKeyboardButton(text="👥 Create Groups", callback_data="groups")],
        [InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")]
    ])
    await message.answer("🤖 WhatsApp Manager", reply_markup=kb)

@dp.callback_query()
async def callbacks(call: types.CallbackQuery):
    if call.data == "connect":
        await call.message.edit_text("📱 WhatsApp connect feature soon...")

    elif call.data == "groups":
        await call.message.edit_text("👥 Group creation feature soon...")

    elif call.data == "settings":
        await call.message.edit_text("⚙️ Settings panel soon...")

async def main():
    await dp.start_polling(bot)

if name == "main":
    asyncio.run(main())
