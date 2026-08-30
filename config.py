import os

# Токен бота, полученный у @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_BOT_TOKEN_HERE")

# Способ №1 (для Railway/облака): весь JSON ключа сервисного аккаунта Firebase
# одной строкой в переменной окружения FIREBASE_CREDENTIALS_JSON.
# Способ №2 (для локального запуска): путь к файлу с ключом.
# Если задана FIREBASE_CREDENTIALS_JSON — она в приоритете.
FIREBASE_CREDENTIALS_JSON = os.getenv("FIREBASE_CREDENTIALS_JSON", "")
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-key.json")

# Telegram ID первого администратора (чтобы было кому назначать остальных)
# Узнать свой ID можно у бота @userinfobot
ROOT_ADMIN_ID = int(os.getenv("ROOT_ADMIN_ID", "0"))

# Статусы заказа
STATUS_NEW = "новый"            # только что создан, ещё не разослан художникам (например, их пока нет)
STATUS_REVIEW = "на проверке"   # разослан художникам, ждём, пока кто-то примет
STATUS_IN_PROGRESS = "в работе"
STATUS_DONE = "готово"
STATUS_REJECTED = "отклонено"

ALL_STATUSES = [STATUS_NEW, STATUS_REVIEW, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_REJECTED]

# Роли (пользователь может иметь сразу несколько: user + artist + admin)
ROLE_USER = "user"
ROLE_ARTIST = "artist"
ROLE_ADMIN = "admin"
