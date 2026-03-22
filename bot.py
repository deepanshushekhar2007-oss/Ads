from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

BOT_TOKEN = "8418461342:AAH1NJEMnCnYROk6fZrA1hG-ewaV7v38Ndw"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)


# START COMMAND
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=1)

    keyboard.add(
        InlineKeyboardButton("🔗 Connect WhatsApp", callback_data="connect"),
        InlineKeyboardButton("👥 Create Groups", callback_data="groups"),
        InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
        InlineKeyboardButton("📊 My Groups", callback_data="mygroups")
    )

    await message.reply(
        "🤖 WhatsApp Automation Manager\n\nChoose option:",
        reply_markup=keyboard
    )


# CALLBACK HANDLER
@dp.callback_query_handler(lambda c: True)
async def callbacks(call: types.CallbackQuery):

    if call.data == "connect":
        await call.message.edit_text(
            "📱 WhatsApp Connect\n\nQR system will be added next step..."
        )

    elif call.data == "groups":
        await call.message.edit_text(
            "👥 Group Creator\n\nSend group name:"
        )

    elif call.data == "settings":
        await call.message.edit_text(
            "⚙️ Settings Panel\n\nComing soon..."
        )

    elif call.data == "mygroups":
        await call.message.edit_text(
            "📊 Your created groups will appear here"
        )


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
    
