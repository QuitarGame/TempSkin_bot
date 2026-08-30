from aiogram.fsm.state import State, StatesGroup


class OrderForm(StatesGroup):
    gender = State()
    wishes = State()
    description = State()   # свободное текстовое описание
    references = State()    # референсы (фото), опционально
    confirm = State()


class AdminAssignArtist(StatesGroup):
    waiting_username = State()


class AdminAssignAdmin(StatesGroup):
    waiting_username = State()


class ArtistDeliver(StatesGroup):
    waiting_files = State()   # художник прикладывает готовые файлы скина перед завершением заказа


class ArtistAcceptComment(StatesGroup):
    waiting_comment = State()  # необязательный комментарий заказчику при принятии заказа


class ArtistDeclineReason(StatesGroup):
    waiting_reason = State()   # необязательная причина отказа от заказа
