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
