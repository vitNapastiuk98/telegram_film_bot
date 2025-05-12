FilmBot
=======

Telegram bot that:

• Collects every message posted in a configured channel / super‑group (the bot must be admin).  
• Caches text (title on line 1 + unique code on line 2) in Redis for fast look‑ups.  
• Lets authorised users search the cache with `/find <query>` or the passive “write‑to‑bot” search.  
• Provides inline menus for the **owner** to add / remove chats and manage extra admins.  
• Runs under Python 3.10+ with `python‑telegram‑bot 20`, `redis‑py`, and `python‑dotenv`.

-------------------------------------------------------------------------------

1  Quick start (local)
---------------------

    # clone / download this repo, then inside it
    python -m venv .venv
    .venv/Scripts/activate        # Linux/macOS: source .venv/bin/activate
    pip install -r requirements.txt

    # start redis (docker is easiest everywhere)
    docker run --name redis -p 6379:6379 -d redis:latest

Create a `.env` file:

    TELEGRAM_BOT_TOKEN=123456:ABC...      # token from @BotFather
    TARGET_GROUP_ID=-1001234567890        # channel or super‑group ID
    BOT_OWNER_ID=555000111                # your Telegram user ID
    REDIS_URL=redis://localhost:6379/0
    LOG_LEVEL=INFO                        # DEBUG for more details

Run the bot:

    python main.py

-------------------------------------------------------------------------------

2  How it works
---------------

Component          | Purpose
------------------ | ------------------------------------------------------------
Redis hash         | `chat:<id>:texts` → `message_id → text` (title + code)
Message handler    | Saves every incoming post, keeps last 10 000
/find command      | Matches query against *title* **or** *code* exactly
Inline menus       | Owner sees extra buttons for chat/admin management
Admin flow         | Owner presses **Add admin** → sends ID → stored in Redis

-------------------------------------------------------------------------------

3  Commands & buttons
---------------------

Command / Button      | Who | Description
--------------------- | ----| -----------------------------------------------
/start                | all | Shows main menu (owner sees extra button)
/find <keywords>      | auth| Forward cached messages whose title or code match
/chatid               | all | Returns current chat/channel ID
/setowner             | first| Claims ownership if none set
/admin add/remove/list| owner| CLI alternative to buttons
➕/➖/📄 Chat buttons   | owner| (stubs for future)
Add/Remove/List admin | owner| Interactive admin management
🔙 Return back        | owner| Back to main menu

auth = owner + extra admins.

-------------------------------------------------------------------------------

4  Extending
------------

* Multi‑chat support: store each chat ID in Redis and key their hashes separately.  
* Media export: copy photos/docs with `copy_message`.  
* Chronological export: re‑enable list storage and `/export`.

-------------------------------------------------------------------------------

5  Troubleshooting
------------------

Symptom                              | Fix
------------------------------------ | ----------------------------------------
TOKEN not set                        | Check .env and `load_dotenv()`
BadRequest: description empty        | Ensure each command has a docstring
Bot can’t read posts                 | Promote bot to **Administrator**
Owner buttons shown to everyone      | Verify `BOT_OWNER_ID` or run /setowner
Redis connection error               | Check docker `redis` container and URL
Forwarded header visible             | Use `copy_message()` (already applied)

-------------------------------------------------------------------------------

License
-------
MIT
