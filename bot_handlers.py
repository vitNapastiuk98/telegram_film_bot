
import asyncio

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters, CallbackQueryHandler,
)

import bot_redis_store
from bot_functions import check_membership, delete_chat, _broadcast, passive_find, add_chat, request_chat_link, \
    add_admin, remove_admin, send_chat_list, request_forward_chat
from bot_helpers import TARGET_GROUP_ID, check_bot_admin, is_authorised, is_owner, logger, STRINGS
from bot_menus import menu_admins, menu_chats, menu_root_owner, chat_list_menu

load_dotenv()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greet the user and show quick-action button. Add the user to known hosts"""
    await bot_redis_store.save_user(user_id=update.effective_user.id)
    is_member = await check_membership(update.effective_user.id, context,)
    if not is_member:
        return
    await update.effective_message.reply_text(STRINGS["start_greeting"])

async def setowner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setowner – claim ownership (first run) or confirm env owner."""
    user_id = update.effective_user.id
    current_owner = await bot_redis_store.get_owner()
    if current_owner and current_owner != user_id:
        await update.effective_message.reply_text(STRINGS["owner_already_set"])
        return
    await bot_redis_store.set_owner(user_id)
    await update.effective_message.reply_text(STRINGS["owner_set_success"])
    logger.info("Owner set to %s", user_id)


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin – open management menus depending on role."""
    user_id = update.effective_user.id
    owner_id = await bot_redis_store.get_owner()

    if not await is_authorised(user_id, bot_redis_store):
        return

    if is_owner(user_id, owner_id):

        await update.effective_message.reply_text(STRINGS["admin_manage_prompt"], reply_markup=menu_root_owner())
    else:
        await update.effective_message.reply_text(STRINGS["chat_manage_prompt"], reply_markup=menu_chats(is_owner(user_id, owner_id)))


async def broadcast_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Begin a broadcast – owner only."""
    if not is_owner(update.effective_user.id, await bot_redis_store.get_owner()):
        await update.effective_message.reply_text(STRINGS["notify_not_owner"])
        return

    ctx.user_data["pending_admin_action"] = "broadcast"
    await update.effective_message.reply_text(STRINGS["broadcast_prompt"])

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




async def handle_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.user_data.pop("pending_admin_action", None):
        return

    src_chat = update.effective_chat.id
    src_msg = update.effective_message.message_id
    owner_id = update.effective_user.id

    asyncio.create_task(_broadcast(src_chat, src_msg, owner_id, update, ctx))
    await update.effective_message.reply_text(STRINGS["broadcast_started"])



async def handle_chat_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await is_authorised(user_id, bot_redis_store):
        return

    context.user_data["pending_chat_action"] = "add_name"
    await update.effective_message.reply_text(STRINGS["chat_name_prompt"])


async def handle_chat_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await is_authorised(user_id, bot_redis_store):
        return

    chats = await bot_redis_store.get_chats()

    if not chats:
        await update.effective_message.reply_text(STRINGS["no_chats_to_remove"])
        return
    await update.effective_message.reply_text(
         STRINGS["select_chat_to_remove"],
        reply_markup=chat_list_menu(chats, True)
    )

async def handle_chat_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get("pending_chat_action")
    logger.info(f'action = {action} chat_name = {context.user_data.get("pending_chat_name")} chat_link = {context.user_data.get("pending_chat_link")}')
    if not action:
        return

    text = (update.effective_message.text or "").strip()

    if action == "add_name":
        await request_chat_link(text, update, context)
        return
    if action == "add_link":
        await request_forward_chat(text, update, context)
        return
    if action == "add_forward":
        await add_chat( context, update)
        return
    context.user_data.pop("pending_chat_action", None)


async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    owner_id = await bot_redis_store.get_owner()
    if not is_owner(user_id, owner_id):
        await update.effective_message.reply_text(STRINGS["only_owner_manage_admins"])
        return

    pending = context.user_data.get("pending_admin_action")

    text = (update.effective_message.text or "").strip()
    if pending == "broadcast":
        await handle_broadcast(update, context)
    elif pending in {'add', 'remove'}:
        if not text.isdigit():
            await update.effective_message.reply_text(STRINGS["send_numeric_user_id"])
            return

        target_id = int(text)

        if pending == "add":
            await add_admin(target_id, update)
        elif pending == "remove":
            await remove_admin(target_id, update)
    else:

        await update.effective_message.reply_text(STRINGS["unknown_pending_action"])


    context.user_data.pop("pending_admin_action", None)


async def handle_main_menu(query):
    await query.edit_message_text(STRINGS["menu_management"], reply_markup=menu_root_owner())

async def handle_admin_menu(query):
    await query.edit_message_text(STRINGS["admin_management"], reply_markup=menu_admins())

async def handle_chat_menu(query, user_id, owner_id):
    await query.edit_message_text(STRINGS["chat_management"], reply_markup=menu_chats(is_owner(user_id, owner_id)))


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
        await send_chat_list(update, context)
        return

async def handle_admin_action(query, data, owner_id, context):
    action = data.split("_", 1)[1]
    if action == "list":
        admins = await bot_redis_store.list_admins()
        admins_txt = ", ".join(str(a) for a in sorted(admins)) or "(none)"
        await query.edit_message_text(
            STRINGS["current_admins"].format(owner_id=owner_id,
                                             admins=admins_txt),
            reply_markup=menu_admins(),
        )
        return

    context.user_data["pending_admin_action"] = action
    await query.edit_message_text(STRINGS["send_user_id_prompt"].format(action))



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
        await query.answer(STRINGS["unknown_action"])

async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process inputs"""
    logger.info(f'context.user_data = {context.user_data}')
    if context.user_data is None :
        logger.info(f'context.user_data is empty')
        return

    action = context.user_data.get("pending_chat_action")
    if action:
        await handle_chat_input(update, context)
        return

    pending = context.user_data.get("pending_admin_action")
    if not pending:
        is_member = await check_membership(update.effective_user.id, context, )
        if not is_member:
            return
        await passive_find(update, context)
        return

    await handle_admin_input(update, context)

def register(application, ):
    """Attach all handlers to *application* and set command menu."""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setowner", setowner))
    application.add_handler(CommandHandler("admin", admin_cmd))
    application.add_handler(CommandHandler("manage", admin_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    application.add_handler(MessageHandler(filters.FORWARDED, handle_input))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    application.add_handler(MessageHandler(filters.ALL, store_incoming))
    