from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

BOT_TOKEN = "8418461342:AAH1NJEMnCnYROk6fZrA1hG-ewaV7v38Ndw"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔗 Connect WhatsApp", callback_data="connect"))
    keyboard.add(types.InlineKeyboardButton("👥 Create Groups", callback_data="groups"))
    keyboard.add(types.InlineKeyboardButton("⚙️ Settings", callback_data="settings"))

    await message.reply("🤖 WhatsApp Manager", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: True)
async def callbacks(call: types.CallbackQuery):
    if call.data == "connect":
        await call.message.edit_text("📱 WhatsApp connect soon...")

    elif call.data == "groups":
        await call.message.edit_text("👥 Group creator soon...")

    elif call.data == "settings":
        await call.message.edit_text("⚙️ Settings soon...")


if name == "main":
    executor.start_polling(dp, skip_updates=True)
