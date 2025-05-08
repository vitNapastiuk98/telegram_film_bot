import os
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Load your token and allowed user ID from environment
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))

# In-memory store for messages per chat
chat_messages = {}


async def secret_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Secret command accessible only by allowed user"""
    user_id = update.effective_user.id
    if user_id != ALLOWED_USER_ID:
        await update.message.reply_text("⛔ You are not allowed to use this command.")
        return
    await update.message.reply_text("✅ Welcome, master user!")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start interaction with the bot"""
    keyboard = [[
        InlineKeyboardButton("👍 Like", callback_data="like"),
        InlineKeyboardButton("👎 Dislike", callback_data="dislike"),
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Do you like this bot?", reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button presses"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(f"You clicked: {query.data}")


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply with the user's Telegram ID"""
    await update.message.reply_text(f"Your Telegram user ID is: {update.effective_user.id}")


async def keyboard_demo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show a reply-keyboard menu"""
    keyboard = [
        [KeyboardButton("Option 1"), KeyboardButton("Option 2")],
        [KeyboardButton("Option 3")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Choose an option:", reply_markup=reply_markup)


async def echo_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo back any text message"""
    await update.message.reply_text(f"You selected: {update.message.text}")


async def store_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Store incoming text messages in memory per chat"""
    chat_id = update.effective_chat.id
    text = update.message.text or '<non-text message>'
    chat_messages.setdefault(chat_id, []).append((update.message.message_id, update.effective_user.id, text))


async def list_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List stored messages from this group if the bot is admin"""
    chat = update.effective_chat
    # Check bot admin status
    bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
    if bot_member.status not in ("administrator", "creator"):
        await update.message.reply_text("⛔ I need to be an admin to list messages.")
        return
    msgs = chat_messages.get(chat.id, [])
    if not msgs:
        await update.message.reply_text("No messages stored yet.")
        return
    # Show last 10 messages
    lines = [f"{mid} - User {uid}: {txt}" for mid, uid, txt in msgs[-10:]]
    await update.message.reply_text("\n".join(lines))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List available commands from Telegram menu"""
    cmds = await context.bot.get_my_commands()
    text = "Available commands:\n" + "\n".join(f"/{c.command} — {c.description}" for c in cmds)
    await update.message.reply_text(text)


async def set_commands(application):
    """
    Dynamically register all CommandHandler commands with descriptions
    derived from each handler's docstring.
    """
    commands = []
    for handlers in application.handlers.values():
        for handler in handlers:
            if isinstance(handler, CommandHandler):
                for cmd in handler.commands:
                    desc = handler.callback.__doc__ or "No description"
                    commands.append(BotCommand(cmd, desc
                                               .strip()))
    await application.bot.set_my_commands(commands)


def main() -> None:
    # Build the application and register dynamic command setup
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(set_commands)
        .build()
    )

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CommandHandler("myid", myid))
    application.add_handler(CommandHandler("test", secret_command))
    application.add_handler(CommandHandler("menu", keyboard_demo))
    application.add_handler(CommandHandler("list", list_messages))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_choice))

    # Start polling (blocks until Ctrl+C)
    application.run_polling()


if __name__ == "__main__":
    main()
