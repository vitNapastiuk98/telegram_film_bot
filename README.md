FilmBot
=======

Telegram bot for caching and searching “film-code” posts across multiple channels, with full localization support.

Features
--------
- **Multi-channel message caching**: collects every post in configured channels/super-groups and stores the first line as title + second line as unique code in Redis for instant look-ups.  
- **Exact-match search**: `/find <query>` forwards any cached messages whose title or code exactly matches.  
- **Passive search**: in a 1:1 chat, any non-command text is treated as a search query once you’ve run `/start`.  
- **Membership gating**: users must join all configured chats before searching; missing channels are presented as join links.  
- **Role-based access**:  
  - **Owner** can manage admins & chats, reassign ownership, and broadcast to all users.  
  - **Admins** can manage chats.  
  - **Regular users** can search only.  
- **Interactive inline menus** for admin/chat management and broadcast flows.  
- **Broadcast messaging**: owner can broadcast a message to all known users and receive success/failure stats.  
- **Full localization** via `res.<lang>.json` → `res.json` (auto-built).  
- **Dynamic command registration**: command list populated from handler docstrings at startup.  
- **Built with**: Python 3.10+, `python-telegram-bot 20`, `redis.asyncio`, `python-dotenv`.

Quick Start (local)
-------------------
```bash
# 1. clone & enter repo
git clone <repo_url>
cd <repo_dir>
python -m venv .venv
source .venv/bin/activate    # macOS/Linux
# or .\.venv\Scripts\activate # Windows

# 2. install dependencies
pip install -r requirements.txt

# 3. prepare your .env:
#    TELEGRAM_BOT_TOKEN=...
#    TARGET_GROUP_ID=-100...
#    BOT_OWNER_ID=...
#    REDIS_URL=redis://localhost:6379/0
#    LOG_LEVEL=INFO
#    BOT_LANG=en       # or "ru" for Russian

# 4. build localized resources
python build_resources.py

# 5. run the bot
python main.py
```

Configuration
-------------
Place your environment variables in a `.env` file or export them:

- `TELEGRAM_BOT_TOKEN` — token from BotFather  
- `TARGET_GROUP_ID` — primary channel/super-group ID for caching  
- `BOT_OWNER_ID` — initial owner’s Telegram user ID  
- `REDIS_URL` — e.g. `redis://localhost:6379/0`  
- `LOG_LEVEL` — `INFO` or `DEBUG`  
- `BOT_LANG` — two-letter code matching `res.<lang>.json` (e.g. `en`, `ru`)  
- `RES_JSON_PATH` (optional) — path to generated `res.json` (default: `res.json`)

Building Resources
------------------
All user-facing strings live in `res.en.json`, `res.ru.json`, etc. Before starting, the helper script merges the chosen language file into `res.json`:

```bash
python build_resources.py [lang]
```

If `lang` is omitted, it reads `BOT_LANG` (default `en`).

Commands & Buttons
------------------
| Command          | Role          | Description                                   |
| ---------------- | ------------- | --------------------------------------------- |
| `/start`         | all           | Register & check membership, then greet.      |
| `/find <query>`  | owner+admins  | Exact-match search by title or code.          |
| `/setowner`      | owner setup   | Claim or confirm bot ownership.               |
| `/admin` or `/manage` | owner/admin | Open the management menu.                 |
| `/broadcast`     | owner         | Begin broadcast to all known users.           |
| `/help`          | all           | Show available commands.                      |

Inline-menu buttons are all pulled from `res.json`, including:
- ➕ Add chat  
- ➖ Remove chat  
- 📄 List chats  
- 📣 Broadcast message  
- 🔙 Return back  
- 👥 Manage admins  
- 💬 Manage chats  

How It Works
------------
1. **Redis Store** (`bot_redis_store.py`)  
   - Hashes per-chat: `chat:<id>:texts` mapping `message_id → text`.  
   - Trims to last 10 000 entries per chat.  
2. **Message Handler**  
   - Watches configured chats; caches when bot is admin.  
3. **Membership Check**  
   - Validates all required channels before allowing searches.  
4. **Search & Forward**  
   - `do_search(query)` returns message IDs; bot copies them to the user.  
5. **Menus & Callbacks**  
   - InlineKeyboardMarkup driven by `bot_menus.py`.  
6. **Broadcast Engine**  
   - Gathers user list, copies broadcast, reports successes/failures.  
7. **Localization Loader**  
   - `build_resources.py` → `res.json` → loaded in `bot_helpers.py`.  

Extending & Customization
-------------------------
- **Media export**: handle photos/documents in `store_incoming`.  
- **Batch export**: re-enable message lists and add an `/export` command.  
- **Advanced searches**: extend `do_search` for substrings or regex.  

Troubleshooting
---------------
| Symptom                         | Remedy                                                         |
| ------------------------------- | -------------------------------------------------------------- |
| Bot fails to start              | Ensure you ran `build_resources.py` and `BOT_LANG` is set.     |
| `TELEGRAM_BOT_TOKEN` not set    | Verify `.env` or environment.                                  |
| Bot missing admin rights        | Promote the bot to Admin in each target chat.                 |
| Redis connection refused        | Check Docker/container is running and `REDIS_URL` is correct. |
| `/find` returns no matches      | Confirm messages follow the two-line `title
code` format.     |

License
-------
MIT
