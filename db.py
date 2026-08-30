"""
Обёртка над Firebase Firestore.

Коллекции:
  users:  {telegram_id: {roles: [str,...], username, full_name, created_at}}
  orders: {order_id (auto): {user_id, description, gender, wishes,
                              references: [file_id,...],
                              status, artist_id, reject_reason,
                              message_ids: {artist_id(str): message_id},
                              declined_by: [artist_id,...],
                              broadcasted: bool,
                              created_at, updated_at}}

ВАЖНО про производительность: firebase-admin — синхронная библиотека, каждый
её вызов (get/set/where...) — это блокирующий сетевой запрос. Если вызывать
её напрямую внутри async-хендлеров aiogram, она блокирует весь event loop бота
на время запроса, и бот "тормозит" — не отвечает другим пользователям, пока
не закончится текущий запрос к Firestore.

Поэтому все публичные функции ниже — async и выполняют реальную (синхронную)
работу в отдельном потоке через asyncio.to_thread. Хендлеры просто добавляют
await перед вызовом db.xxx(...), а event loop в это время свободен и
обрабатывает других пользователей.
"""
import asyncio
import datetime
import functools
import json

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import ArrayUnion

from config import FIREBASE_CREDENTIALS_PATH, FIREBASE_CREDENTIALS_JSON, ROLE_USER, STATUS_NEW

if FIREBASE_CREDENTIALS_JSON:
    # Railway/облако: ключ приходит одной строкой из переменной окружения
    cred = credentials.Certificate(json.loads(FIREBASE_CREDENTIALS_JSON))
else:
    # Локальный запуск: ключ лежит файлом рядом с ботом (не коммитить в git!)
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)

_app = firebase_admin.initialize_app(cred)
db = firestore.client()

users_col = db.collection("users")
orders_col = db.collection("orders")


def _to_async(fn):
    """Оборачивает синхронную функцию так, чтобы она выполнялась в отдельном
    потоке и не блокировала event loop бота."""
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)
    return wrapper


# ---------- Пользователи ----------

def _ensure_user(telegram_id: int, username: str, full_name: str) -> dict:
    doc_ref = users_col.document(str(telegram_id))
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        updates = {}
        if username and data.get("username") != username:
            updates["username"] = username
        if full_name and data.get("full_name") != full_name:
            updates["full_name"] = full_name
        if updates:
            doc_ref.set(updates, merge=True)
            data.update(updates)
        return data
    data = {
        "telegram_id": telegram_id,
        "username": username or "",
        "full_name": full_name or "",
        "roles": [ROLE_USER],
        "created_at": datetime.datetime.utcnow().isoformat(),
    }
    doc_ref.set(data)
    return data


def _get_user(telegram_id: int) -> dict | None:
    doc = users_col.document(str(telegram_id)).get()
    return doc.to_dict() if doc.exists else None


def _add_role(telegram_id: int, role: str):
    users_col.document(str(telegram_id)).set({"roles": ArrayUnion([role])}, merge=True)


def _remove_role(telegram_id: int, role: str):
    doc_ref = users_col.document(str(telegram_id))
    doc = doc_ref.get()
    if not doc.exists:
        return
    roles = [r for r in (doc.to_dict().get("roles") or []) if r != role]
    if not roles:
        roles = [ROLE_USER]
    doc_ref.set({"roles": roles}, merge=True)


def _list_users_by_role(role: str) -> list[dict]:
    docs = users_col.where("roles", "array_contains", role).stream()
    return [d.to_dict() for d in docs]


def _find_user_by_username(username: str) -> dict | None:
    username = username.lstrip("@")
    docs = users_col.where("username", "==", username).limit(1).stream()
    for d in docs:
        return d.to_dict()
    return None


# ---------- Заказы ----------

def _create_order(user_id: int, description: str, gender: str,
                   wishes: str, references: list[str]) -> str:
    now = datetime.datetime.utcnow().isoformat()
    data = {
        "user_id": user_id,
        "description": description,
        "gender": gender,
        "wishes": wishes,
        "references": references or [],
        "status": STATUS_NEW,
        "artist_id": None,          # кто в итоге взял заказ в работу
        "reject_reason": None,
        "message_ids": {},
        "declined_by": [],
        "broadcasted": False,
        "created_at": now,
        "updated_at": now,
    }
    doc_ref = orders_col.document()
    doc_ref.set(data)
    return doc_ref.id


def _list_pending_broadcast_orders() -> list[dict]:
    docs = orders_col.where("broadcasted", "==", False).where("status", "==", STATUS_NEW).stream()
    return [{**d.to_dict(), "id": d.id} for d in docs]


def _get_order(order_id: str) -> dict | None:
    doc = orders_col.document(order_id).get()
    if not doc.exists:
        return None
    d = doc.to_dict()
    d["id"] = doc.id
    return d


def _update_order(order_id: str, **fields):
    fields["updated_at"] = datetime.datetime.utcnow().isoformat()
    orders_col.document(order_id).set(fields, merge=True)


def _list_orders_by_user(user_id: int) -> list[dict]:
    docs = orders_col.where("user_id", "==", user_id).stream()
    result = [{**d.to_dict(), "id": d.id} for d in docs]
    result.sort(key=lambda o: o["created_at"], reverse=True)
    return result


def _list_orders_by_artist(artist_id: int) -> list[dict]:
    docs = orders_col.where("artist_id", "==", artist_id).stream()
    result = [{**d.to_dict(), "id": d.id} for d in docs]
    result.sort(key=lambda o: o["created_at"], reverse=True)
    return result


def _list_orders_by_status(status: str) -> list[dict]:
    docs = orders_col.where("status", "==", status).stream()
    result = [{**d.to_dict(), "id": d.id} for d in docs]
    result.sort(key=lambda o: o["created_at"])
    return result


def _list_all_orders() -> list[dict]:
    docs = orders_col.stream()
    result = [{**d.to_dict(), "id": d.id} for d in docs]
    result.sort(key=lambda o: o["created_at"], reverse=True)
    return result


# ---------- Публичные async-обёртки (используйте эти из хендлеров) ----------

ensure_user = _to_async(_ensure_user)
get_user = _to_async(_get_user)
add_role = _to_async(_add_role)
remove_role = _to_async(_remove_role)
list_users_by_role = _to_async(_list_users_by_role)
find_user_by_username = _to_async(_find_user_by_username)

create_order = _to_async(_create_order)
list_pending_broadcast_orders = _to_async(_list_pending_broadcast_orders)
get_order = _to_async(_get_order)
update_order = _to_async(_update_order)
list_orders_by_user = _to_async(_list_orders_by_user)
list_orders_by_artist = _to_async(_list_orders_by_artist)
list_orders_by_status = _to_async(_list_orders_by_status)
list_all_orders = _to_async(_list_all_orders)


def has_role(user: dict | None, role: str) -> bool:
    return bool(user and role in (user.get("roles") or []))
