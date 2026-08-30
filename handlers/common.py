from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message

import db
from config import ROLE_ADMIN, ROOT_ADMIN_ID
from keyboards import main_menu_kb

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = await db.ensure_user(message.from_user.id, message.from_user.username, message.from_user.full_name)

    # Первый заход рут-админа — автоматически выдаём роль admin (в дополнение к остальным ролям)
    if ROOT_ADMIN_ID and message.from_user.id == ROOT_ADMIN_ID and not db.has_role(user, ROLE_ADMIN):
        await db.add_role(message.from_user.id, ROLE_ADMIN)
        user = await db.get_user(message.from_user.id)

    text = (
        "Привет! 👋 Это бот для заказа отрисовки скинов.\n\n"
        "Здесь можно бесплатно оформить заявку на создание скина — "
        "просто заполни небольшую анкету, и художник свяжется с тобой через бота.\n\n"
        "Выбирай действие в меню ниже 👇"
    )
    await message.answer(text, reply_markup=main_menu_kb(user.get("roles")))


@router.message(F.text == "❌ Отменить")
async def cancel_any(message: Message, state):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    await message.answer("Действие отменено.", reply_markup=main_menu_kb(user.get("roles") if user else []))


def order_card_text(order: dict, with_user: bool = False, with_artist: bool = False) -> str:
    lines = [f"🧾 Заказ #{order['id'][:6]}", f"Статус: {order['status']}"]
    if with_user:
        lines.append(f"Заказчик: {order['user_id']}")
    if with_artist and order.get("artist_id"):
        lines.append(f"Художник: {order['artist_id']}")
    lines += [
        f"Пол персонажа: {order.get('gender') or '—'}",
        f"Пожелания: {order.get('wishes') or '—'}",
        f"Описание: {order.get('description') or '—'}",
        f"Референсов приложено: {len(order.get('references') or [])}",
    ]
    if order.get("status") == "отклонено" and order.get("reject_reason"):
        lines.append(f"Причина отклонения: {order['reject_reason']}")
    return "\n".join(lines)
