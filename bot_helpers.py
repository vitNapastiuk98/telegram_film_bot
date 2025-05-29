import asyncio
import os
import logging
import json

from dotenv import load_dotenv
from telegram.ext import ContextTypes

# -----------------------------
# Global configuration helpers
# -----------------------------
load_dotenv()
TARGET_GROUP_ID: int = int(os.getenv("TARGET_GROUP_ID", ""))
TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not TOKEN:
    raise RuntimeError("No TELEGRAM_BOT_TOKEN environment variable set")

def setup_logging() -> logging.Logger:
    """Initialise the root logger and return a logger for the caller."""
    logging.basicConfig(
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
    return logging.getLogger(__name__)


logger = setup_logging()

RES_PATH = os.getenv("RES_JSON_PATH", "res.json")
try:
    with open(RES_PATH, encoding="utf-8") as f:
        STRINGS = json.load(f)
except Exception as e:
    raise RuntimeError(f"Could not load resources: {e}")



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

