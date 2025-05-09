from __future__ import annotations

import os

from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters, CallbackQueryHandler,
)

import bot_redis_store
from bot_helpers import TARGET_GROUP_ID, check_bot_admin, is_authorised, is_owner, logger, \
    run_search_and_forward
from bot_menus import menu_admins, menu_chats, menu_root_owner

load_dotenv()


# -----------------------------
# Authorisation wrappers
# -----------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greet the user and show quick-action button."""
    await update.message.reply_text(
        "Hi! Write me a code, and I will find you the film",
    )


async def setowner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setowner – claim ownership (first run) or confirm env owner."""
    user_id = update.effective_user.id
    current_owner = await bot_redis_store.get_owner()
    if current_owner and current_owner != user_id:
        await update.message.reply_text("Owner already set – you are not the owner.")
        return
    await bot_redis_store.set_owner(user_id)
    await update.message.reply_text("✅ You are now the bot owner.")
    logger.info("Owner set to %s", user_id)


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin – open management menus depending on role."""
    user_id = update.effective_user.id
    owner_id = await bot_redis_store.get_owner()

    if not await is_authorised(user_id, bot_redis_store):
        return

    if is_owner(user_id, owner_id):

        await update.message.reply_text("What would you like to manage?", reply_markup=menu_root_owner())
    else:
        await update.message.reply_text("Chat management:", reply_markup=menu_chats(is_owner(user_id, owner_id)))


async def find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/find <keyword> – search command."""
    if not context.args:
        await update.message.reply_text("Usage: /find <keyword>")
        return

    await run_search_and_forward(update, context, " ".join(context.args), bot_redis_store)


async def passive_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Treat any plain text in private chat as a search query (after /start)."""
    chat = update.effective_chat
    if chat.type != "private":
        return  # only react in DM with the bot

    text = (update.message.text or "").strip()
    if not text or text.startswith("/"):
        return  # ignore empty or commands
    logger.info("inputted " + text)
    await run_search_and_forward(update, context, text, bot_redis_store)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/help – show command list."""
    cmds = await context.bot.get_my_commands()
    await update.message.reply_text(
        "Available commands:\n" + "\n".join(f"/{c.command} – {c.description}" for c in cmds)
    )


async def store_incoming(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """store messages in db"""
    chat_id = update.effective_chat.id
    if chat_id != TARGET_GROUP_ID:
        return
    if not await check_bot_admin(chat_id, context):
        return

    msg = update.message
    msg_id = msg.message_id
    text = msg.text or msg.caption or ""
    sender = msg.from_user.id if msg.from_user else "<unknown>"

    logger.info("New message %s from %s: %s", msg_id, sender, text.replace("\n", " ")[:100])
    await bot_redis_store.save_message(msg_id, text)

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


# ---------------------------------------------------------------------------
# CallbackQuery handler
# ---------------------------------------------------------------------------

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    owner_id = await bot_redis_store.get_owner()

    await query.answer()

    # Ensure only authorised users can use any management callback
    if not await is_authorised(user_id, bot_redis_store):
        return

    data = query.data

    # ===== root menus =====
    if data == "main_menu":
        await query.edit_message_text("Menu management:", reply_markup=menu_root_owner())
    if data == "menu_admins":
        await query.edit_message_text("Admin management:", reply_markup=menu_admins())
        return
    if data == "menu_chats":
        await query.edit_message_text("Chat management:", reply_markup=menu_chats(is_owner(user_id, owner_id)))
        return

    # ===== stub actions =====
    if data in {"chat_add", "chat_remove", "chat_list"}:
        await query.answer("Chat-management action not yet implemented.")
        return

        # ===== admin management (owner only) =====
    if data.startswith("admin_"):
        if not is_owner(user_id, owner_id):
            await query.answer("Only the owner can manage admins.", show_alert=True)
            return

        action = data.split("_", 1)[1]  # add / remove / list
        if action == "list":
            admins = await bot_redis_store.list_admins()
            admins_txt = ", ".join(str(a) for a in sorted(admins)) or "(none)"
            await query.edit_message_text(
                f"Current admins (excluding owner {owner_id}): {admins_txt}",
                reply_markup=menu_admins(),
            )
            return

        # For add/remove → ask for numeric ID next
        context.user_data["pending_admin_action"] = action  # "add" or "remove"
        await query.edit_message_text(
            f"Send the user ID to {action} as admin:"
        )
        return

    await query.answer("Unknown action.")

    await query.answer("Unknown action.")



# ---------------------------------------------------------------------------
# Owner ID entry handler (after admin_add / admin_remove button)
# ---------------------------------------------------------------------------

async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the numeric user‑ID the owner sends after pressing *Add* or *Remove* admin."""
    user_id = update.effective_user.id
    owner_id = await bot_redis_store.get_owner()

    # Only act if this user is the owner and we have a pending action
    pending = context.user_data.get("pending_admin_action")
    if not (pending and user_id == owner_id):
        await passive_find(update, context)
        return  # ignore – not part of the admin flow

    text = (update.message.text or "").strip()
    if not text.isdigit():
        await update.message.reply_text("Please send a numeric Telegram user ID.")
        return

    target_id = int(text)
    if pending == "add":
        await bot_redis_store.add_admin(target_id)
        await update.message.reply_text(f"✅ {target_id} added as admin.")
    elif pending == "remove":
        await bot_redis_store.remove_admin(target_id)
        await update.message.reply_text(f"✅ {target_id} removed from admins.")
    else:
        await update.message.reply_text("Unknown pending action – please try again.")

    # Clear pending flag
    context.user_data.pop("pending_admin_action", None)



# -----------------------------
# Registration helper
# -----------------------------

def register(application,):
    """Attach all handlers to *application* and set command menu."""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setowner", setowner))
    application.add_handler(CommandHandler("admin", admin_cmd))
    application.add_handler(CommandHandler("find", find))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    application.add_handler(MessageHandler(filters.ALL, store_incoming))

