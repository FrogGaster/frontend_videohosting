from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    nickname = State()
    world_level = State()
    main_dps = State()
    server = State()
    description = State()
    photo = State()


class ReportStates(StatesGroup):
    reason = State()


class DeleteAccountStates(StatesGroup):
    confirm = State()


class EditProfileStates(StatesGroup):
    choosing_field = State()
    nickname = State()
    world_level = State()
    main_dps = State()
    server = State()
    description = State()
    photo = State()
