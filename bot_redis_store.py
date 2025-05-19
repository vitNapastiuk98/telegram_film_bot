import os
import redis.asyncio as redis_lib  # use alias to avoid self‑import confusion

from bot_helpers import TARGET_GROUP_ID, int_or_none

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client: "redis_lib.Redis" = redis_lib.from_url(REDIS_URL, decode_responses=True)

OWNER_KEY = "bot:owner"
ADMINS_KEY = "bot:admins"
CHATS_KEY = "bot:chats"
HASH_KEY = f"chat:{TARGET_GROUP_ID}:texts"
USERS = "bot:users"
MAX_HISTORY = 10_000

# -----------------------------
# Owner / admin helpers
# -----------------------------

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
    return await redis_client.hgetall(CHATS_KEY)

async def get_chat(chat_name: str):
    return await redis_client.hget(CHATS_KEY, chat_name)

async def set_chat(chat_name: str, chat_link: str):
    await redis_client.hset(CHATS_KEY, chat_name, chat_link)

async def del_chat(chat_name: str):
    await redis_client.hdel(CHATS_KEY, chat_name)




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
    texts = await get_all_texts()                       # {msg_id: text}

    for mid, raw in texts.items():
        
        if not raw:
            continue

        # Split into at most two lines; strip whitespace from each
        line1, *rest = [ln.strip().lower() for ln in raw.splitlines()]
        line2 = rest[0] if rest else ""

        if q == line1 or q == line2:
            results.append(int(mid))

    return results


