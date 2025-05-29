from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from bot_helpers import STRINGS

def menu_chats(is_owner) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(STRINGS["btn_add_chat"], callback_data="chat_add")],
        [InlineKeyboardButton(STRINGS["btn_remove_chat"], callback_data="chat_remove")],
        [InlineKeyboardButton(STRINGS["btn_list_chats"], callback_data="chat_list")],
        [InlineKeyboardButton(STRINGS["btn_broadcast_message"], callback_data="chat_notify")],
    ]
    if is_owner:
        rows.append([InlineKeyboardButton(STRINGS["btn_return_back"], callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)

def menu_admins() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(STRINGS["btn_add_chat"].replace("chat", "admin"), callback_data="admin_add")],
        [InlineKeyboardButton(STRINGS["btn_remove_chat"].replace("chat", "admin"), callback_data="admin_remove")],
        [InlineKeyboardButton(STRINGS["btn_list_chats"].replace("chat", "admins"), callback_data="admin_list")],
        [InlineKeyboardButton(STRINGS["btn_return_back"], callback_data="main_menu")],
    ])

def menu_root_owner() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(STRINGS["btn_manage_admins"], callback_data="menu_admins")],
        [InlineKeyboardButton(STRINGS["btn_manage_chats"], callback_data="menu_chats")],
    ])

def chat_list_menu(chats: dict, for_removal: bool = False) -> InlineKeyboardMarkup:
    rows = []
    for name, link in chats.items():
        if for_removal:
            rows.append([InlineKeyboardButton(name, callback_data=name)])
        else:
            rows.append([InlineKeyboardButton(name, url=link)])
    return InlineKeyboardMarkup(rows)
