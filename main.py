"""Entry point – bootstraps the Telegram application and wires handlers.
Run with:  python main.py
"""
import os

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder
from bot_helpers import logger
from bot_functions import register



load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')


def main() -> None:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    logger.info("Starting bot application …")
    logger.info(TOKEN)
    application = ApplicationBuilder().token(TOKEN).build()
    register(application)  # plug in handlers & menus
    try:
        application.run_polling()
    finally:
        logger.info("Bot stopped.")


if __name__ == "__main__":
    main()