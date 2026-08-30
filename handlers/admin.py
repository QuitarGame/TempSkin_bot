from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import db
from config import ROLE_ADMIN, ROLE_ARTIST, STATUS_REVIEW
from states import AdminAssignArtist, AdminAssignAdmin
from keyboards import admin_panel_kb, artist_order_kb
from handlers.common import order_card_text
from handlers.user import broadcast_order_to_artists

router = Router()


async def _is_admin(message_or_call) -> bool:
    user = await db.get_user(message_or_call.from_user.id)
    return db.has_role(user, ROLE_ADMIN)


@router.message(F.text == "⚙️ Кабинет администратора")
async def admin_cabinet(message: Message):
    if not await _is_admin(message):
        await message.answer("Эта секция доступна только администраторам.")
        return
    await message.answer("Панель администратора:", reply_markup=admin_panel_kb())


@router.callback_query(F.data.startswith("list_status:"))
async def admin_list_status(call: CallbackQuery):
    if not await _is_admin(call):
        await call.answer("Недоступно.", show_alert=True)
        return
    status = call.data.split(":", 1)[1]
    orders = await db.list_orders_by_status(status)
    await call.answer()
    if not orders:
        label = "ждут рассылки художникам" if status == "новый" else f"со статусом «{status}»"
        await call.message.answer(f"Заказов, которые {label}, нет.")
        return
    for order in orders[:15]:
        await call.message.answer(order_card_text(order, with_user=True, with_artist=True))


async def _grant_role_flow(message: Message, state: FSMContext, bot: Bot, role: str, role_label: str):
    username = message.text.strip()
    target = await db.find_user_by_username(username)
    await state.clear()
    if not target:
        await message.answer(
            "Пользователь не найден. Убедись, что он написал боту /start хотя бы раз, "
            "и что username указан верно (с @ или без)."
        )
        return

    already_had = db.has_role(target, role)
    await db.add_role(target["telegram_id"], role)
    await message.answer(f"✅ Пользователь @{target.get('username')} теперь {role_label}.")
    try:
        await bot.send_message(
            target["telegram_id"],
            f"👑 Тебе выдана роль «{role_label}»! Открой меню — там появится новый раздел.",
        )
    except Exception:
        pass
    return target, already_had


@router.callback_query(F.data == "admin_new_artist")
async def admin_new_artist_start(call: CallbackQuery, state: FSMContext):
    if not await _is_admin(call):
        await call.answer("Недоступно.", show_alert=True)
        return
    await state.set_state(AdminAssignArtist.waiting_username)
    await call.answer()
    await call.message.answer(
        "Пришли @username пользователя, которого нужно сделать художником "
        "(он должен хотя бы раз написать боту /start).\n"
        "Можно указать и свой собственный @username, чтобы назначить себя "
        "(роли не исключают друг друга — можно быть и художником, и админом одновременно)."
    )


@router.message(AdminAssignArtist.waiting_username)
async def admin_new_artist_finish(message: Message, state: FSMContext, bot: Bot):
    if not await _is_admin(message):
        await state.clear()
        return

    result = await _grant_role_flow(message, state, bot, ROLE_ARTIST, "художник")
    if not result:
        return
    target, already_had = result
    if already_had:
        return

    # Рассылаем этому (и любым другим ещё не разосланным) заказам художников —
    # актуально, если это первый художник в боте вообще.
    pending = await db.list_pending_broadcast_orders()
    sent_count = 0
    for order in pending:
        if await broadcast_order_to_artists(bot, order["id"]):
            sent_count += 1

    # довозим этому новому художнику и те заказы, что уже разосланы другим,
    # но ещё ждут решения (на проверке)
    review_orders = await db.list_orders_by_status(STATUS_REVIEW)
    for order in review_orders:
        message_ids = order.get("message_ids") or {}
        if str(target["telegram_id"]) in message_ids:
            continue
        caption = "🆕 Новый заказ на скин! Кто первый примет — тот и берёт в работу.\n\n" + order_card_text(
            order, with_user=True
        )
        try:
            if order["references"]:
                sent = await bot.send_photo(
                    target["telegram_id"], order["references"][0], caption=caption,
                    reply_markup=artist_order_kb(order["id"]),
                )
            else:
                sent = await bot.send_message(
                    target["telegram_id"], caption, reply_markup=artist_order_kb(order["id"])
                )
            message_ids[str(target["telegram_id"])] = sent.message_id
            await db.update_order(order["id"], message_ids=message_ids)
        except Exception:
            pass

    if sent_count:
        await message.answer(f"📬 Заказов, ждавших художника, разослано: {sent_count}.")


@router.callback_query(F.data == "admin_new_admin")
async def admin_new_admin_start(call: CallbackQuery, state: FSMContext):
    if not await _is_admin(call):
        await call.answer("Недоступно.", show_alert=True)
        return
    await state.set_state(AdminAssignAdmin.waiting_username)
    await call.answer()
    await call.message.answer(
        "Пришли @username пользователя, которого нужно сделать администратором "
        "(он должен хотя бы раз написать боту /start). Роль добавится в дополнение "
        "к уже имеющимся у него ролям."
    )


@router.message(AdminAssignAdmin.waiting_username)
async def admin_new_admin_finish(message: Message, state: FSMContext, bot: Bot):
    if not await _is_admin(message):
        await state.clear()
        return
    await _grant_role_flow(message, state, bot, ROLE_ADMIN, "администратор")


@router.callback_query(F.data == "admin_list_artists")
async def admin_list_artists(call: CallbackQuery):
    if not await _is_admin(call):
        await call.answer("Недоступно.", show_alert=True)
        return
    artists = await db.list_users_by_role(ROLE_ARTIST)
    await call.answer()
    if not artists:
        await call.message.answer("Художников пока нет.")
        return
    lines = [f"• @{a.get('username') or '—'} (id {a['telegram_id']})" for a in artists]
    await call.message.answer("🎨 Художники:\n" + "\n".join(lines))


@router.callback_query(F.data == "admin_list_admins")
async def admin_list_admins(call: CallbackQuery):
    if not await _is_admin(call):
        await call.answer("Недоступно.", show_alert=True)
        return
    admins = await db.list_users_by_role(ROLE_ADMIN)
    await call.answer()
    lines = [f"• @{a.get('username') or '—'} (id {a['telegram_id']})" for a in admins]
    await call.message.answer("👑 Администраторы:\n" + "\n".join(lines))
