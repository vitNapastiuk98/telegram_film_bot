from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv
from telegram import Update, BotCommand, CallbackQuery
from telegram.error import Forbidden, BadRequest, RetryAfter
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters, CallbackQueryHandler,
)

import bot_redis_store
from bot_helpers import TARGET_GROUP_ID, check_bot_admin, is_authorised, is_owner, logger, \
    run_search_and_forward
from bot_menus import menu_admins, menu_chats, menu_root_owner, chat_list_menu

load_dotenv()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greet the user and show quick-action button. Add the user to known hosts"""
    await bot_redis_store.save_user(user_id=update.effective_user.id)
    await update.effective_message.reply_text(
        "Hi! Write me a code, and I will find you the film",
    )


async def setowner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setowner – claim ownership (first run) or confirm env owner."""
    user_id = update.effective_user.id
    current_owner = await bot_redis_store.get_owner()
    if current_owner and current_owner != user_id:
        await update.effective_message.reply_text("Owner already set – you are not the owner.")
        return
    await bot_redis_store.set_owner(user_id)
    await update.effective_message.reply_text("✅ You are now the bot owner.")
    logger.info("Owner set to %s", user_id)


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin – open management menus depending on role."""
    user_id = update.effective_user.id
    owner_id = await bot_redis_store.get_owner()

    if not await is_authorised(user_id, bot_redis_store):
        return

    if is_owner(user_id, owner_id):

        await update.effective_message.reply_text("What would you like to manage?", reply_markup=menu_root_owner())
    else:
        await update.effective_message.reply_text("Chat management:", reply_markup=menu_chats(is_owner(user_id, owner_id)))


async def find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/find <keyword> – search command."""
    if not context.args:
        await update.effective_message.reply_text("Usage: /find <keyword>")
        return

    await run_search_and_forward(update, context, " ".join(context.args), bot_redis_store)


async def broadcast_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Begin a broadcast – owner only."""
    if not is_owner(update.effective_user.id, await bot_redis_store.get_owner()):
        await update.effective_message.reply_text("⛔ Only the owner can use /notify.")
        return

    ctx.user_data["pending_admin_action"] = "broadcast"
    await update.effective_message.reply_text("✅ Send me the message to broadcast:")


async def passive_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Treat any plain text in private chat as a search query (after /start)."""
    chat = update.effective_chat
    if chat.type != "private":
        return

    text = (update.effective_message.text or "").strip()
    if not text or text.startswith("/"):
        return
    logger.info("inputted " + text)
    await run_search_and_forward(update, context, text, bot_redis_store)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/help – show command list."""
    cmds = await context.bot.get_my_commands()
    await update.effective_message.reply_text(
        "Available commands:\n" + "\n".join(f"/{c.command} – {c.description}" for c in cmds)
    )


async def store_incoming(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """store messages in db"""
    chat_id = update.effective_chat.id
    if chat_id != TARGET_GROUP_ID:
        return
    if not await check_bot_admin(chat_id, context):
        return

    msg = update.effective_message
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


async def _broadcast(from_chat: int, msg_id: int, owner_id: int,
                     update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update.effective_user.id, owner_id):
        return

    users = await bot_redis_store.get_users()
    successes = fails = 0

    for uid in users:
        try:
            await ctx.bot.copy_message(
                chat_id=int(uid),
                from_chat_id=from_chat,
                message_id=msg_id,
            )
            successes += 1

        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await ctx.bot.copy_message(int(uid), from_chat, msg_id)
                successes += 1
            except (Forbidden, BadRequest, Exception):
                fails += 1

        except (Forbidden, BadRequest, Exception):
            fails += 1

    await ctx.bot.send_message(
        owner_id,
        text=f"📣 Broadcast done – sent to {successes}, failed for {fails}."
    )


async def handle_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.user_data.pop("pending_admin_action", None):
        return

    src_chat = update.effective_chat.id
    src_msg = update.effective_message.message_id
    owner_id = update.effective_user.id

    asyncio.create_task(_broadcast(src_chat, src_msg, owner_id, update, ctx))
    await update.effective_message.reply_text("📣 Broadcast started… I’ll let you know when it’s done.")



async def handle_chat_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await is_authorised(user_id, bot_redis_store):
        return

    context.user_data["pending_chat_action"] = "add"
    await update.effective_message.reply_text("✅ Send the chat name followed by the link (separated by a space)")


async def handle_chat_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await is_authorised(user_id, bot_redis_store):
        return

    chats = await bot_redis_store.get_chats()

    if not chats:
        await update.effective_message.reply_text("No chats to remove.")
        return
    await update.effective_message.reply_text(
        "🗑️ Select a chat to remove:",
        reply_markup=chat_list_menu(chats, True)
    )


async def handle_chat_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await is_authorised(user_id, bot_redis_store):
        return

    chats = await bot_redis_store.get_chats()
    if not chats:
        await update.effective_message.reply_text("No chats added yet.")
    else:
        await update.effective_message.reply_text("Here are your current chats:", reply_markup=chat_list_menu(chats))


async def handle_chat_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    owner_id = await bot_redis_store.get_owner()

    if not is_owner(user_id, owner_id):
        await update.effective_message.reply_text("Only the owner can manage chats.")
        return


    action = context.user_data.get("pending_chat_action")
    if not action:
        return

    text = (update.effective_message.text or "").strip()
    if not text or " " not in text:
        await update.effective_message.reply_text("Please send the chat name followed by the link, separated by a space.")
        return

    chat_name, chat_link = text.split(" ", 1)

    if action == "add":
        await bot_redis_store.set_chat(chat_name, chat_link)
        await update.effective_message.reply_text(f"✅ Chat '{chat_name}' set to {chat_link}.")
    elif action == "remove":
        await bot_redis_store.del_chat(chat_name)
        await update.effective_message.reply_text(f"🗑️ Chat '{chat_name}' has been removed.")


    context.user_data.pop("pending_chat_action", None)


async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    owner_id = await bot_redis_store.get_owner()
    pending = context.user_data.get("pending_admin_action")
    if not is_owner(user_id, owner_id):
        await update.effective_message.reply_text("Only the owner can manage admins.")
        return

    text = (update.effective_message.text or "").strip()
    if pending == "broadcast":
        await handle_broadcast(update, context)
    elif pending in {'add', 'remove'}:
        if not text.isdigit():
            await update.effective_message.reply_text("Please send a numeric Telegram user ID.")
            return

        target_id = int(text)

        if pending == "add":
            await bot_redis_store.add_admin(target_id)
            await update.effective_message.reply_text(f"✅ {target_id} added as admin.")
        elif pending == "remove":
            await bot_redis_store.remove_admin(target_id)
            await update.effective_message.reply_text(f"✅ {target_id} removed from admins.")
    else:

        await update.effective_message.reply_text("Unknown pending action – please try again.")


    context.user_data.pop("pending_admin_action", None)


async def handle_main_menu(query):
    await query.edit_message_text("Menu management:", reply_markup=menu_root_owner())

async def handle_admin_menu(query):
    await query.edit_message_text("Admin management:", reply_markup=menu_admins())

async def handle_chat_menu(query, user_id, owner_id):
    await query.edit_message_text("Chat management:", reply_markup=menu_chats(is_owner(user_id, owner_id)))


async def handle_chat_action(update: Update, context: ContextTypes.DEFAULT_TYPE, data):
    if data == "chat_notify":
        await broadcast_cmd(update, context)
        return
    if data == "chat_remove":
        await handle_chat_remove(update, context)
        return
    if data == "chat_add":
        await handle_chat_add(update, context)
        return
    if data == "chat_list":
        await handle_chat_list(update, context)
        return

async def handle_admin_action(query, data, owner_id, context):
    action = data.split("_", 1)[1]
    if action == "list":
        admins = await bot_redis_store.list_admins()
        admins_txt = ", ".join(str(a) for a in sorted(admins)) or "(none)"
        await query.edit_message_text(
            f"Current admins (excluding owner {owner_id}): {admins_txt}",
            reply_markup=menu_admins(),
        )
        return

    context.user_data["pending_admin_action"] = action
    await query.edit_message_text(f"Send the user ID to {action} as admin:")


async def delete_chat(data, query: CallbackQuery):
    await bot_redis_store.del_chat(data)
    await query.edit_message_text(f"🗑️ Chat '{data}' has been removed.")
    return


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    owner_id = await bot_redis_store.get_owner()

    await query.answer()

    # Check authorization
    if not await is_authorised(user_id, bot_redis_store):
        return

    data = query.data

    chats = await bot_redis_store.get_chats()
    if data in chats:
        await delete_chat(data, query)

    # Dispatch to specific handlers
    if data == "main_menu":
        await handle_main_menu(query)
    elif data == "menu_admins":
        await handle_admin_menu(query)
    elif data == "menu_chats":
        await handle_chat_menu(query, user_id, owner_id)
    elif data.startswith("chat_"):
        await handle_chat_action(update, context, data)
    elif data.startswith("admin_"):
        await handle_admin_action(query, data, owner_id, context)
    else:
        await query.answer("Unknown action.")

async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process inputs"""

    action = context.user_data.get("pending_chat_action")
    if action:
        await handle_chat_input(update, context)
        return

    pending = context.user_data.get("pending_admin_action")
    if not pending:
        await passive_find(update, context)
        return

    await handle_admin_input(update, context)

def register(application, ):
    """Attach all handlers to *application* and set command menu."""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setowner", setowner))
    application.add_handler(CommandHandler("admin", admin_cmd))
    application.add_handler(CommandHandler("manage", admin_cmd))
    application.add_handler(CommandHandler("broadcast", broadcast_cmd))
    application.add_handler(CommandHandler("find", find))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("chat_add", handle_chat_add))
    application.add_handler(CommandHandler("chat_remove", handle_chat_remove))
    application.add_handler(CommandHandler("chat_list", handle_chat_list))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    application.add_handler(MessageHandler(filters.ALL, store_incoming))
    