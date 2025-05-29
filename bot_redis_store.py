import os

import redis
import redis.asyncio as redis_lib  # use alias to avoid self‑import confusion
from redis.commands import json
from redis.commands.json.path import Path
from redis.commands.search.field import TextField, NumericField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query

from bot_helpers import TARGET_GROUP_ID, int_or_none, logger

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client: "redis_lib.Redis" = redis_lib.from_url(REDIS_URL, decode_responses=True)

OWNER_KEY = "bot:owner"
ADMINS_KEY = "bot:admins"
CHATS_KEY = "hash-idx:marketing"
HASH_KEY = f"chat:{TARGET_GROUP_ID}:texts"
USERS = "bot:users"
MAX_HISTORY = 10_000

# -----------------------------
# Owner / admin helpers
# -----------------------------
schema = (
    TextField("name"),
    TextField("link"),
    NumericField("chat_id")
)

index_created = redis_client.ft(CHATS_KEY).create_index(
    schema, definition=IndexDefinition(prefix=["marketing:"],
                                       index_type=IndexType.HASH)
)


async def get_owner() -> int | None:
    env_owner = int_or_none(os.getenv("BOT_OWNER_ID"))
    if env_owner:
        return env_owner
    return int_or_none(await redis_client.get(OWNER_KEY))


async def set_owner(user_id: int):
    await redis_client.set(OWNER_KEY, user_id)


async def save_user(user_id: int):
    await redis_client.sadd(USERS, user_id)


async def get_users() -> set[str]:
    return await redis_client.smembers(USERS)


async def is_admin(user_id: int) -> bool:
    return bool(await redis_client.sismember(ADMINS_KEY, str(user_id)))


async def add_admin(user_id: int):
    await redis_client.sadd(ADMINS_KEY, user_id)


async def remove_admin(user_id: int):
    await redis_client.srem(ADMINS_KEY, user_id)


async def list_admins():
    return await redis_client.smembers(ADMINS_KEY)


async def get_chats():
    result = await redis_client.ft(CHATS_KEY).search(Query("*"))
    logger.info(f"Got {len(result.docs)} {result} {result.docs} chats")
    return {doc.id.replace('chat:', ''): {
        'name': doc.name,
        'chat_id': int(doc.chat_id),
        'link': doc.link
    } for doc in result.docs}


async def set_chat(chat_name: str, chat_id: int, chat_link: str):
    chat_data = {
        "name": chat_name,
        "chat_id": chat_id,
        "link": chat_link
    }
    # Store chat data as JSON
    await redis_client.hset(f"marketing:{chat_name}", mapping=chat_data)

async def del_chat(chat_name: str):
    await redis_client.delete(f"marketing:{chat_name}")




# -----------------------------
# Message caching helpers
# -----------------------------

async def save_message(msg_id: int, text: str):
    """Store *msg_id* in list + hash with *text* (trims list to MAX_HISTORY)."""
    await redis_client.hset(HASH_KEY, str(msg_id), text)


async def get_all_texts():
    return await redis_client.hgetall(HASH_KEY)


async def do_search(query: str) -> list[int]:
    """
    Search by *film title*  or *unique code*.
    """
    q = query.strip().lower()
    if not q:
        return []

    results: list[int] = []
    texts = await get_all_texts()  # {msg_id: text}

    for mid, raw in texts.items():

        if not raw:
            continue

        # Split into at most two lines; strip whitespace from each
        line1, *rest = [ln.strip().lower() for ln in raw.splitlines()]
        line2 = rest[0] if rest else ""

        if q == line1 or q == line2:
            results.append(int(mid))

    return results
