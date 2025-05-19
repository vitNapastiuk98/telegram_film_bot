# ---------------------------------------------------------------------------
# Inline keyboards
# ---------------------------------------------------------------------------
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from bot_helpers import logger


def menu_chats(is_owner) -> InlineKeyboardMarkup:
    rows = [

            [InlineKeyboardButton("➕ Add chat", callback_data="chat_add")],
            [InlineKeyboardButton("➖ Remove chat", callback_data="chat_remove")],
            [InlineKeyboardButton("📄 List chats", callback_data="chat_list")],
            [InlineKeyboardButton("📣 Broadcast message", callback_data="chat_notify")],
        ]
    if is_owner:
        rows.append([InlineKeyboardButton("🔙 Return back", callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)


def menu_admins() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Add admin", callback_data="admin_add")],
            [InlineKeyboardButton("➖ Remove admin", callback_data="admin_remove")],
            [InlineKeyboardButton("📄 List admins", callback_data="admin_list")],
            [InlineKeyboardButton("🔙 Return back", callback_data="main_menu")],
        ]
    )


def menu_root_owner() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👥 Manage admins", callback_data="menu_admins")],
            [InlineKeyboardButton("💬 Manage chats", callback_data="menu_chats")],
        ]
    )


def chat_list_menu(chats: dict, for_removal: bool = False) -> InlineKeyboardMarkup:
    rows = []
    for chat_name, chat_link in chats.items():
        if for_removal:
            callback_data = chat_name
            rows.append([InlineKeyboardButton(chat_name, callback_data=callback_data)])
        else:
            rows.append([InlineKeyboardButton(chat_name, url=chat_link)])
    return InlineKeyboardMarkup(rows)