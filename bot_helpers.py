import os
import logging

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes
# -----------------------------
# Global configuration helpers
# -----------------------------
load_dotenv()
TARGET_GROUP_ID: int = int(os.getenv("TARGET_GROUP_ID", ""))

def setup_logging() -> logging.Logger:
    """Initialise the root logger and return a logger for the caller."""
    logging.basicConfig(
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
    return logging.getLogger(__name__)


logger = setup_logging()



# -----------------------------
# Generic utilities
# -----------------------------

def int_or_none(val: str | None):
    """Convert *val* to int or return None if blank/invalid."""
    try:
        return int(val) if val else None
    except ValueError:
        return None


async def check_bot_admin(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True when the bot is admin/owner in *chat_id*."""
    member = await context.bot.get_chat_member(chat_id, context.bot.id)
    return member.status in {"administrator", "creator"}

async def is_authorised(user_id: int, redis_store) -> bool:
    owner = await redis_store.get_owner()
    return user_id == owner or await redis_store.is_admin(user_id)


def is_owner(user_id: int, owner_id: int | None) -> bool:
    return owner_id is not None and user_id == owner_id


async def run_search_and_forward(
    update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, redis_store
) -> None:
    user_id = update.effective_user.id
    logger.info(f"Searching for {query}")
    matches = await redis_store.do_search(query)
    logger.info(f"Found {len(matches)} matches")
    if not matches:
        await update.message.reply_text("No matches found.")
        return

    for mid in sorted(matches):
        try:
            await context.bot.copy_message(user_id, TARGET_GROUP_ID, mid)
        except Exception as exc:
            logger.warning("Search forward %s failed: %s", mid, exc)
            continue
