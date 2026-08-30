from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import db
from config import STATUS_REVIEW, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_REJECTED, ROLE_ARTIST, ROLE_ADMIN
from states import ArtistDeliver
from keyboards import artist_order_kb, artist_progress_kb, deliver_files_kb, main_menu_kb
from handlers.common import order_card_text

router = Router()


async def _is_artist(message_or_call) -> bool:
    user = await db.get_user(message_or_call.from_user.id)
    return db.has_role(user, ROLE_ARTIST)


@router.message(F.text == "🖌 Кабинет художника")
async def artist_cabinet(message: Message):
    if not await _is_artist(message):
        await message.answer("Эта секция доступна только художникам.")
        return

    orders = await db.list_orders_by_artist(message.from_user.id)
    review_orders = await db.list_orders_by_status(STATUS_REVIEW)

    pending = [
        o for o in review_orders
        if str(message.from_user.id) in (o.get("message_ids") or {})
        and message.from_user.id not in (o.get("declined_by") or [])
    ]
    in_progress = [o for o in orders if o["status"] == STATUS_IN_PROGRESS]
    finished = [o for o in orders if o["status"] in (STATUS_DONE, STATUS_REJECTED)]

    if not pending and not in_progress:
        await message.answer("Пока нет заказов, ожидающих твоего решения или уже взятых в работу.")

    for order in pending:
        text = order_card_text(order, with_user=True)
        await message.answer(text, reply_markup=artist_order_kb(order["id"]))

    for order in in_progress:
        text = order_card_text(order, with_user=True)
        await message.answer(text, reply_markup=artist_progress_kb(order["id"]))

    if finished:
        await message.answer(f"Завершённых/отклонённых заказов: {len(finished)} (последние 5):")
        for order in finished[:5]:
            await message.answer(order_card_text(order, with_user=True))


async def _edit_order_message(bot: Bot, chat_id: int, message_id: int, extra_text: str):
    try:
        try:
            await bot.edit_message_caption(chat_id=chat_id, message_id=message_id,
                                            caption=extra_text, reply_markup=None)
        except Exception:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                         text=extra_text, reply_markup=None)
    except Exception:
        pass


@router.callback_query(F.data.startswith("artist_accept:"))
async def artist_accept(call: CallbackQuery, bot: Bot):
    order_id = call.data.split(":")[1]
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заказ не найден.", show_alert=True)
        return
    if order["status"] != STATUS_REVIEW:
        await call.answer("Этот заказ уже недоступен — его взял другой художник или он закрыт.", show_alert=True)
        await _edit_order_message(
            bot, call.from_user.id, call.message.message_id,
            "❌ Заказ уже взят другим художником." if order["status"] == STATUS_IN_PROGRESS
            else f"Заказ больше недоступен (статус: {order['status']}).",
        )
        return

    await db.update_order(order_id, status=STATUS_IN_PROGRESS, artist_id=call.from_user.id)
    order = await db.get_order(order_id)

    await _edit_order_message(
        bot, call.from_user.id, call.message.message_id,
        order_card_text(order, with_user=True) + "\n\n✅ Ты взял этот заказ в работу!",
    )
    try:
        await bot.send_message(call.from_user.id, "Когда закончишь — отметь заказ готовым:",
                                reply_markup=artist_progress_kb(order_id))
    except Exception:
        pass
    await call.answer("Заказ взят в работу")

    for artist_id_str, msg_id in (order.get("message_ids") or {}).items():
        artist_id = int(artist_id_str)
        if artist_id == call.from_user.id:
            continue
        await _edit_order_message(bot, artist_id, msg_id, "❌ Заказ уже взят другим художником.")

    try:
        await bot.send_message(
            order["user_id"],
            f"🎨 Твой заказ #{order_id[:6]} взят художником в работу!",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("artist_done:"))
async def artist_done_start(call: CallbackQuery, state: FSMContext):
    order_id = call.data.split(":")[1]
    order = await db.get_order(order_id)
    if not order or order["artist_id"] != call.from_user.id:
        await call.answer("Заказ недоступен.", show_alert=True)
        return
    if order["status"] != STATUS_IN_PROGRESS:
        await call.answer("Этот заказ уже закрыт.", show_alert=True)
        return

    await state.set_state(ArtistDeliver.waiting_files)
    await state.update_data(order_id=order_id, files=[])
    await call.answer()
    await call.message.answer(
        "Пришли готовый скин заказчику: одно или несколько изображений/файлов "
        "(можно по одному сообщению за раз). Когда закончишь — нажми кнопку ниже.\n"
        "Файлы прикреплять не обязательно, если хочешь просто закрыть заказ без вложений.",
        reply_markup=deliver_files_kb(),
    )


@router.message(ArtistDeliver.waiting_files, F.photo)
async def deliver_add_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    files = data.get("files", [])
    files.append({"type": "photo", "file_id": message.photo[-1].file_id})
    await state.update_data(files=files)
    await message.answer(f"Файл добавлен ({len(files)}). Пришли ещё или нажми «Завершить и отправить заказчику».")


@router.message(ArtistDeliver.waiting_files, F.document)
async def deliver_add_document(message: Message, state: FSMContext):
    data = await state.get_data()
    files = data.get("files", [])
    files.append({"type": "document", "file_id": message.document.file_id})
    await state.update_data(files=files)
    await message.answer(f"Файл добавлен ({len(files)}). Пришли ещё или нажми «Завершить и отправить заказчику».")


@router.message(ArtistDeliver.waiting_files, F.text == "✅ Завершить и отправить заказчику")
async def deliver_finish(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_id = data["order_id"]
    files = data.get("files", [])
    order = await db.get_order(order_id)
    if not order or order["artist_id"] != message.from_user.id:
        await state.clear()
        await message.answer("Заказ недоступен.")
        return

    await db.update_order(order_id, status=STATUS_DONE)
    await state.clear()

    user = await db.get_user(message.from_user.id)
    await message.answer(
        f"🏁 Заказ #{order_id[:6]} завершён, заказчику отправлено файлов: {len(files)}.",
        reply_markup=main_menu_kb(user.get("roles")),
    )

    try:
        await bot.send_message(
            order["user_id"],
            f"🎉 Твой скин по заказу #{order_id[:6]} готов!" + (
                " Файлы ниже 👇" if files else " Художник скоро свяжется с тобой в личных сообщениях."
            ),
        )
        for f in files:
            try:
                if f["type"] == "photo":
                    await bot.send_photo(order["user_id"], f["file_id"])
                else:
                    await bot.send_document(order["user_id"], f["file_id"])
            except Exception:
                pass
    except Exception:
        pass


@router.callback_query(F.data.startswith("artist_reject:"))
async def artist_reject(call: CallbackQuery, bot: Bot):
    order_id = call.data.split(":")[1]
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заказ не найден.", show_alert=True)
        return
    if order["status"] != STATUS_REVIEW:
        await call.answer("Этот заказ уже недоступен.", show_alert=True)
        await _edit_order_message(
            bot, call.from_user.id, call.message.message_id,
            "❌ Заказ уже взят другим художником." if order["status"] == STATUS_IN_PROGRESS
            else f"Заказ больше недоступен (статус: {order['status']}).",
        )
        return

    declined_by = list(order.get("declined_by") or [])
    if call.from_user.id not in declined_by:
        declined_by.append(call.from_user.id)
    await db.update_order(order_id, declined_by=declined_by)
    order = await db.get_order(order_id)

    await _edit_order_message(
        bot, call.from_user.id, call.message.message_id,
        order_card_text(order, with_user=True) + "\n\n🚫 Ты отклонил этот заказ.",
    )
    await call.answer("Заказ отклонён")

    recipients = list((order.get("message_ids") or {}).keys())
    all_declined = recipients and all(int(a) in declined_by for a in recipients)

    if all_declined:
        await db.update_order(order_id, status=STATUS_REJECTED,
                               reject_reason="Все художники отклонили заказ")
        order = await db.get_order(order_id)
        try:
            await bot.send_message(
                order["user_id"],
                f"😔 К сожалению, все художники отклонили заказ #{order_id[:6]}.\n"
                "Как только появится новый художник, можно будет попробовать снова "
                "или дождаться, пока администратор назначит кого-то ещё.",
            )
        except Exception:
            pass
        admins = await db.list_users_by_role(ROLE_ADMIN)
        for admin in admins:
            try:
                await bot.send_message(
                    admin["telegram_id"],
                    f"🚫 Заказ #{order_id[:6]} отклонили все художники — заказ закрыт со статусом «отклонено».",
                )
            except Exception:
                pass
