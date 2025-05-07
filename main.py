import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, \
    BotCommand, Bot
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes, CallbackContext, CallbackQueryHandler, MessageHandler, filters,
)

# Load your token (or hard-code for testing)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")

async def secret_command(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    if user_id != ALLOWED_USER_ID:
        await update.message.reply_text("you are not allowed")
        return
    await update.message.reply_text("Welcome master")


async def keyboard_demo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # define rows of buttons
    keyboard = [
        [KeyboardButton("Option 1"), KeyboardButton("Option 2")],
        [KeyboardButton("Option 3")],
    ]
    # resize_keyboard makes buttons fit nicely
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Choose an option:", reply_markup=reply_markup)

async def echo_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # simply echo whatever button text was pressed
    await update.message.reply_text(f"You selected: {update.message.text}")

# async handler signature
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [
            InlineKeyboardButton("👍 Like", callback_data="like"),
            InlineKeyboardButton("👎 Dislike", callback_data="dislike"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Do you like this bot?", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # Acknowledge the callback
    choice = query.data  # “like” or “dislike”
    await query.edit_message_text(f"You clicked: {choice}")


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    # user.id is an integer
    await update.message.reply_text(f"Your Telegram user ID is: {user.id}")



async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cmds = "\n".join(f"/{cmd.command} — {cmd.description}"
                     for cmd in await context.bot.get_my_commands())
    await update.message.reply_text(f"Available commands:\n{cmds}")

# 2️⃣ At startup, register your commands with Telegram
async def set_commands(application):
    commands = [
        BotCommand("start", "Start interacting with the bot"),
        BotCommand("help", "List available commands"),
        BotCommand("myid", "Get your id"),
        BotCommand("test", "Secret command"),
        BotCommand("menu", "Open menu"),
        # add more BotCommand("name", "description") entries here
    ]
    await application.bot.set_my_commands(commands)


def main() -> None:
    # build the application
    application = ApplicationBuilder().token(TOKEN).post_init(set_commands).build()

    # register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myid", myid))
    application.add_handler(CommandHandler("test", secret_command))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.add_handler(CommandHandler("menu", keyboard_demo))
    # catch all text (including button presses) and echo back
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_choice))



    # start polling (this blocks until you press Ctrl+C)
    application.run_polling()

if __name__ == "__main__":
    # On Windows, use asyncio.run()
    main()
