#!/usr/bin/env python3
import os

from dotenv import load_dotenv

# build_resources must run before any strings are used
from build_resources import build_resources

load_dotenv()

# pick the language and build
LANG = os.getenv("BOT_LANG", "en")
build_resources(LANG)

from telegram.ext import ApplicationBuilder
from bot_helpers import logger, STRINGS, TOKEN
from bot_handlers import register

def main() -> None:
    logger.info(f'The bot is running with lang {LANG}'
                f'')
    app = ApplicationBuilder().token(TOKEN).build()
    register(app)
    try:
        app.run_polling()
    finally:
        logger.info(STRINGS["bot_stopped"])

if __name__ == "__main__":
    main()
