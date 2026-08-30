from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

import db
from config import STATUS_NEW, STATUS_REVIEW, ROLE_ADMIN, ROLE_ARTIST
from states import OrderForm
from keyboards import (
    gender_kb, skip_kb, references_kb,
    confirm_kb, main_menu_kb, artist_order_kb, remove_kb,
)
from handlers.common import order_card_text

router = Router()


async def broadcast_order_to_artists(bot: Bot, order_id: str):
    """Рассылает заказ всем текущим художникам. Вызывается при создании заказа
    и повторно администратором, когда появляется первый/новый художник."""
    order = await db.get_order(order_id)
    artists = await db.list_users_by_role(ROLE_ARTIST)
    if not artists:
        return False

    caption = "🆕 Новый заказ на скин! Кто первый примет — тот и берёт в работу.\n\n" + order_card_text(
        order, with_user=True
    )
    message_ids = dict(order.get("message_ids") or {})
    for artist in artists:
        artist_id = artist["telegram_id"]
        if str(artist_id) in message_ids:
            continue  # уже отправляли этому художнику
        try:
            if order["references"]:
                sent = await bot.send_photo(
                    artist_id, order["references"][0], caption=caption,
                    reply_markup=artist_order_kb(order_id),
                )
            else:
                sent = await bot.send_message(artist_id, caption, reply_markup=artist_order_kb(order_id))
            message_ids[str(artist_id)] = sent.message_id
        except Exception:
            pass

    await db.update_order(order_id, status=STATUS_REVIEW, broadcasted=True, message_ids=message_ids)
    return True


@router.message(F.text == "🎨 Заказать скин")
async def start_order(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(OrderForm.gender)
    await message.answer(
        "Отлично! Заполним небольшую анкету — это займёт минуту 🙂\n\n"
        "1️⃣ Какой пол у персонажа скина?",
        reply_markup=gender_kb(),
    )


@router.message(OrderForm.gender)
async def order_gender(message: Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await state.set_state(OrderForm.wishes)
    await message.answer(
        "2️⃣ Есть дополнительные пожелания? (цвета, детали, элементы)\n"
        "Можно пропустить.",
        reply_markup=skip_kb(),
    )


@router.message(OrderForm.wishes)
async def order_wishes(message: Message, state: FSMContext):
    wishes = "" if message.text == "Пропустить ➡️" else message.text
    await state.update_data(wishes=wishes)
    await state.set_state(OrderForm.description)
    await message.answer(
        "3️⃣ Опиши в свободной форме, каким ты видишь скин "
        "(можно подробно — художнику это поможет):",
        reply_markup=remove_kb(),
    )


@router.message(OrderForm.description)
async def order_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text, references=[])
    await state.set_state(OrderForm.references)
    await message.answer(
        "4️⃣ Если есть референсы (картинки для примера) — пришли их сейчас, можно несколько.\n"
        "Когда закончишь — нажми кнопку ниже.",
        reply_markup=references_kb(),
    )


@router.message(OrderForm.references, F.photo)
async def order_add_reference(message: Message, state: FSMContext):
    data = await state.get_data()
    refs = data.get("references", [])
    refs.append(message.photo[-1].file_id)
    await state.update_data(references=refs)
    await message.answer(f"Референс добавлен ({len(refs)}). Пришли ещё или нажми «Готово».")


@router.message(OrderForm.references, F.text == "Готово, референсов нет/хватит ✅")
async def order_references_done(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.set_state(OrderForm.confirm)
    text = (
        "Проверь заявку перед отправкой:\n\n"
        f"Пол: {data.get('gender')}\n"
        f"Пожелания: {data.get('wishes') or '—'}\n"
        f"Описание: {data.get('description')}\n"
        f"Референсов: {len(data.get('references', []))}"
    )
    await message.answer(text, reply_markup=confirm_kb())


@router.message(OrderForm.confirm, F.text == "✅ Отправить заказ")
async def order_confirm(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_id = await db.create_order(
        user_id=message.from_user.id,
        description=data.get("description", ""),
        gender=data.get("gender", ""),
        wishes=data.get("wishes", ""),
        references=data.get("references", []),
    )
    await state.clear()
    user = await db.get_user(message.from_user.id)

    sent_to_artists = await broadcast_order_to_artists(bot, order_id)

    if sent_to_artists:
        await message.answer(
            "✅ Заявка отправлена всем художникам! Как только кто-то из них возьмёт заказ в работу, "
            "мы тебе напишем. Статус можно отслеживать в «📋 Мои заказы».",
            reply_markup=main_menu_kb(user.get("roles")),
        )
    else:
        await message.answer(
            "✅ Заявка создана, но сейчас в боте пока нет ни одного художника — "
            "как только администратор кого-то назначит, заявка автоматически уйдёт им. "
            "Статус можно отслеживать в «📋 Мои заказы».",
            reply_markup=main_menu_kb(user.get("roles")),
        )
        order = await db.get_order(order_id)
        caption = "⚠️ Новый заказ ждёт художников (в боте пока никто не назначен художником):\n\n" + order_card_text(
            order, with_user=True
        )
        admins = await db.list_users_by_role(ROLE_ADMIN)
        for admin in admins:
            try:
                await bot.send_message(admin["telegram_id"], caption)
            except Exception:
                pass


@router.message(F.text == "📋 Мои заказы")
async def my_orders(message: Message):
    orders = await db.list_orders_by_user(message.from_user.id)
    if not orders:
        await message.answer("У тебя пока нет заказов. Нажми «🎨 Заказать скин», чтобы создать первый!")
        return
    for order in orders[:15]:
        await message.answer(order_card_text(order, with_artist=True))
