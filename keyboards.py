from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from config import (
    STATUS_NEW, STATUS_REVIEW, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_REJECTED,
)


def main_menu_kb(roles: list[str]) -> ReplyKeyboardMarkup:
    roles = roles or []
    rows = [[KeyboardButton(text="🎨 Заказать скин")], [KeyboardButton(text="📋 Мои заказы")]]
    if "artist" in roles:
        rows.append([KeyboardButton(text="🖌 Кабинет художника")])
    if "admin" in roles:
        rows.append([KeyboardButton(text="⚙️ Кабинет администратора")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def gender_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Мужской"), KeyboardButton(text="Женский")],
            [KeyboardButton(text="Неважно")],
        ],
        resize_keyboard=True, one_time_keyboard=True,
    )


def skip_kb(label: str = "Пропустить ➡️") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label)]], resize_keyboard=True, one_time_keyboard=True,
    )


def references_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Готово, референсов нет/хватит ✅")]],
        resize_keyboard=True, one_time_keyboard=True,
    )


def confirm_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Отправить заказ")],
            [KeyboardButton(text="❌ Отменить")],
        ],
        resize_keyboard=True, one_time_keyboard=True,
    )


def remove_kb() -> ReplyKeyboardMarkup:
    from aiogram.types import ReplyKeyboardRemove
    return ReplyKeyboardRemove()


# ---- Inline-клавиатуры ----

def artist_order_kb(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Взять в работу", callback_data=f"artist_accept:{order_id}")],
        [InlineKeyboardButton(text="🚫 Отклонить", callback_data=f"artist_reject:{order_id}")],
    ])


def artist_progress_kb(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏁 Готово, прикрепить файлы и отправить", callback_data=f"artist_done:{order_id}")],
    ])


def deliver_files_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Завершить и отправить заказчику")],
            [KeyboardButton(text="❌ Отменить")],
        ],
        resize_keyboard=True,
    )


def comment_optional_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Пропустить ➡️")]],
        resize_keyboard=True, one_time_keyboard=True,
    )


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆕 Ждут рассылки (нет художников)", callback_data="list_status:новый")],
        [InlineKeyboardButton(text="🔎 На проверке", callback_data="list_status:на проверке")],
        [InlineKeyboardButton(text="🛠 В работе", callback_data="list_status:в работе")],
        [InlineKeyboardButton(text="✅ Готовые", callback_data="list_status:готово")],
        [InlineKeyboardButton(text="🚫 Отклонённые", callback_data="list_status:отклонено")],
        [InlineKeyboardButton(text="➕ Назначить художника (по юзернейму)", callback_data="admin_new_artist")],
        [InlineKeyboardButton(text="👑 Назначить администратора (по юзернейму)", callback_data="admin_new_admin")],
        [InlineKeyboardButton(text="🎨 Список художников", callback_data="admin_list_artists")],
        [InlineKeyboardButton(text="👑 Список администраторов", callback_data="admin_list_admins")],
    ])
