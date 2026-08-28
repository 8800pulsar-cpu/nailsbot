from aiogram.fsm.state import State, StatesGroup


class AdminServiceAdd(StatesGroup):
    name = State()
    duration = State()
    price = State()


class AdminServiceEdit(StatesGroup):
    waiting_value = State()


class AdminScheduleEdit(StatesGroup):
    waiting_hours = State()


class AdminClosedAdd(StatesGroup):
    waiting_date = State()
    waiting_reason = State()


class AdminMasterEdit(StatesGroup):
    waiting_value = State()
