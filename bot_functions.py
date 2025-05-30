import asyncio

from telegram import Update, CallbackQuery
from telegram.error import Forbidden, BadRequest, RetryAfter
from telegram.ext import ContextTypes

import bot_menus
import bot_redis_store
from bot_helpers import logger, STRINGS, is_owner, TARGET_GROUP_ID, is_authorised


async def run_search_and_forward(
    update: Update, context: ContextTypes.DEFAULT_TYPE, query: str,
) -> None:
    user_id = update.effective_user.id
    logger.info(f"Searching for {query}")
    matches = await bot_redis_store.do_search(query)
    logger.info(f"Found {len(matches)} matches")
    if not matches:
        await update.message.reply_text(STRINGS["no_matches"])
        return

    for mid in sorted(matches):
        try:
            await context.bot.copy_message(user_id, TARGET_GROUP_ID, mid)
        except Exception as exc:
            logger.warning("Search forward %s failed: %s", mid, exc)
            continue


async def check_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE, ) -> bool:
    chats = await bot_redis_store.get_chats()
    logger.info(f'chats {chats}')
    missing_chats = {}

    for chat_name, chat in chats.items():
        try:
            # Attempt to check membership
            logger.info(f'chat_name {chat_name} chat {chat} {user_id}')
            status = await context.bot.get_chat_member(chat_id=chat['chat_id'], user_id=user_id)
            logger.info(f'status {status}')
            if status.status not in {"member", "administrator", "creator"}:
                missing_chats[chat_name] = chat['link']
        except Forbidden:
            # Bot is not an admin in the channel, assume the user is not a member
            logger.warning(f"Bot is not an admin in {chat_name}. Assuming user is not a member.")
            missing_chats[chat_name] = chat['link']
        except Exception as e:
            # Other errors (e.g., bot banned from the group, join request needed)
            logger.warning(f"Failed to check membership for {chat_name}: {e}")
            missing_chats[chat_name] = chat['link']

    if missing_chats:
        reply_markup = bot_menus.chat_list_menu(missing_chats)
        await context.bot.send_message(
            user_id,
            STRINGS["join_channels"] + "\n" + STRINGS["join_channels_suffix"],
            reply_markup=reply_markup
        )
        return False
    return True



async def delete_chat(data, query: CallbackQuery):
    await bot_redis_store.del_chat(data)
    await query.edit_message_text(STRINGS["chat_removed"].format(chat_name=data))
    return


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
        text=STRINGS["broadcast_done"].format(successes=successes, fails=fails),
    )

async def passive_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Treat any plain text in private chat as a search query (after /start)."""
    chat = update.effective_chat
    if chat.type != "private":
        return

    text = (update.effective_message.text or "").strip()
    if not text or text.startswith("/"):
        return
    logger.info("inputted " + text)
    await run_search_and_forward(update, context, text,)

async def add_chat( context: ContextTypes.DEFAULT_TYPE, update: Update):
    chat_id = update.effective_message.api_kwargs['forward_from_chat']['id']
    logger.info(f'chat_id {chat_id} ')
    chat_name = context.user_data.get("pending_chat_name")
    chat_link = context.user_data.get("pending_chat_link")
    logger.info(f'chat_name {chat_name} chat_link {chat_link} chat_id {chat_id}')
    if not chat_name:
        await update.effective_message.reply_text(STRINGS["invalid_chat_name_link"])
    else:
        await bot_redis_store.set_chat(chat_name, chat_id, chat_link)
        await update.effective_message.reply_text(
            STRINGS["chat_set_success"].format(
                chat_name=chat_name, chat_link=chat_link
            )
        )
    context.user_data.pop("pending_chat_action", None)
    context.user_data.pop("pending_chat_link", None)
    context.user_data.pop("pending_chat_name", None)

async def request_chat_link(text, update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pending_chat_name"] = text
    context.user_data["pending_chat_action"] = "add_link"
    await update.effective_message.reply_text(STRINGS["chat_link_prompt"])

async def request_forward_chat(text, update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pending_chat_link"] = text
    context.user_data["pending_chat_action"] = "add_forward"
    await update.effective_message.reply_text(STRINGS["forward_chat_prompt"])



async def send_chat_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await is_authorised(user_id, bot_redis_store):
        return

    chats  = {chat_name: chat['link'] for chat_name, chat in (await bot_redis_store.get_chats()).items()}

    if not chats:
        await update.effective_message.reply_text(STRINGS["no_chats_added"])
    else:
        await update.effective_message.reply_text(STRINGS["current_chats"], reply_markup=bot_menus.chat_list_menu(chats))


async def add_admin(target_id: int, update: Update):
    await bot_redis_store.add_admin(target_id)
    await update.effective_message.reply_text(STRINGS["admin_added"])


async def remove_admin(target_id: int, update: Update):
    await bot_redis_store.remove_admin(target_id)
    await update.effective_message.reply_text(STRINGS["admin_removed"])

