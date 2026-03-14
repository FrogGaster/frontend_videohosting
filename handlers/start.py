from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import get_or_create_user, get_profile_by_user_id, create_profile, get_user_by_telegram_id, update_last_seen
from states import RegistrationStates
from keyboards.reply import get_main_menu, get_skip_keyboard
from keyboards.inline import get_exp_keyboard, ExpCallback

router = Router()


@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки «Я подписался» — продолжаем в start."""
    await state.clear()
    user = await get_or_create_user(callback.from_user.id)
    await update_last_seen(callback.from_user.id)
    profile = await get_profile_by_user_id(user.id)

    await callback.message.edit_text("✅ Подписка подтверждена!")
    await callback.answer("Отлично!")

    if profile:
        await callback.message.answer(
            f"🎖 <b>С возвращением, {profile.nickname}!</b>\n\n"
            "👋 Рады видеть тебя снова! Выбери действие:",
            reply_markup=get_main_menu()
        )
    else:
        await callback.message.answer(
            "🇩🇪 <b>Привет, генерал!</b>\n\n"
            "Добро пожаловать в поиск тиммейтов для <b>Hearts of Iron IV</b>.\n"
            "Создай анкету и находи союзников для великих побед!\n\n"
            "📝 Введи свой ник (Steam / Discord):"
        )
        await state.set_state(RegistrationStates.nickname)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = await get_or_create_user(message.from_user.id)
    await update_last_seen(message.from_user.id)
    profile = await get_profile_by_user_id(user.id)

    if profile:
        await message.answer(
            f"🎖 <b>С возвращением, {profile.nickname}!</b>\n\n"
            "👋 Рады видеть тебя снова! Выбери действие:",
            reply_markup=get_main_menu()
        )
        return

    await message.answer(
        "🇩🇪 <b>Привет, генерал!</b>\n\n"
        "Добро пожаловать в поиск тиммейтов для <b>Hearts of Iron IV</b>.\n"
        "Создай анкету и находи союзников для великих побед!\n\n"
        "📝 Введи свой ник (Steam / Discord):"
    )
    await state.set_state(RegistrationStates.nickname)


@router.message(RegistrationStates.nickname, F.text)
async def reg_nickname(message: Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer("⚠️ Ник слишком длинный. Введи до 50 символов.")
        return
    await state.update_data(nickname=message.text.strip())
    await message.answer(
        "📊 <b>Твой опыт в HoI4</b>\n\n"
        "Выбери уровень (нажми кнопку):",
        reply_markup=get_exp_keyboard()
    )
    await state.set_state(RegistrationStates.world_level)


@router.callback_query(RegistrationStates.world_level, ExpCallback.filter())
async def reg_world_level_btn(callback: CallbackQuery, state: FSMContext, callback_data: ExpCallback):
    await state.update_data(world_level=callback_data.level)
    await callback.message.edit_text("✅ Опыт сохранён!", reply_markup=None)
    await callback.message.answer(
        "🌍 <b>Любимая нация</b>\n\n"
        "Напиши свою любимую страну (например: 🇩🇪 Германия, 🇷🇺 СССР, 🇺🇸 США):"
    )
    await state.set_state(RegistrationStates.main_dps)
    await callback.answer()


@router.message(RegistrationStates.world_level, F.text)
async def reg_world_level(message: Message, state: FSMContext):
    try:
        wl = int(message.text.strip())
        if 1 <= wl <= 5:
            await state.update_data(world_level=wl)
            await message.answer(
                "🌍 <b>Любимая нация</b>\n\n"
                "Напиши свою любимую страну (например: Германия, СССР, США):"
            )
            await state.set_state(RegistrationStates.main_dps)
        else:
            await message.answer("⚠️ Введи число от 1 до 5 или нажми кнопку выше 👆")
    except ValueError:
        await message.answer("⚠️ Введи число от 1 до 5 или нажми кнопку выше 👆")


@router.message(RegistrationStates.main_dps, F.text)
async def reg_main_dps(message: Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer("⚠️ Название слишком длинное. Введи до 50 символов.")
        return
    await state.update_data(main_dps=message.text.strip())
    await message.answer(
        "🎮 <b>Режим и моды</b>\n\n"
        "Напиши, во что любишь играть (Vanilla, Kaiserreich, TNO, RT56 и т.д.):"
    )
    await state.set_state(RegistrationStates.server)


@router.message(RegistrationStates.server, F.text)
async def reg_server(message: Message, state: FSMContext):
    await state.update_data(server=message.text.strip())
    await message.answer(
        "📝 <b>Расскажи о себе</b>\n\n"
        "Краткое описание — за что любишь HoI4, что ищешь в тиммейте.\n\n"
        "Или нажми кнопку ниже 👇",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(RegistrationStates.description)


@router.message(RegistrationStates.description, F.text, F.text.in_({"/skip", "⏭ Пропустить"}))
async def reg_description_skip(message: Message, state: FSMContext):
    await state.update_data(description=None)
    await message.answer(
        "📸 <b>Скрин из игры</b>\n\n"
        "Загрузи фото или нажми кнопку ниже 👇",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(RegistrationStates.photo)


@router.message(RegistrationStates.description, F.text)
async def reg_description(message: Message, state: FSMContext):
    desc = message.text.strip()
    if len(desc) > 300:
        await message.answer("⚠️ Описание слишком длинное (макс 300 символов).")
        return
    await state.update_data(description=desc)
    await message.answer(
        "📸 <b>Скрин из игры</b>\n\n"
        "Загрузи фото или нажми кнопку ниже 👇",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(RegistrationStates.photo)


@router.message(RegistrationStates.photo, F.text, F.text.in_({"/skip", "⏭ Пропустить"}))
async def reg_photo_skip(message: Message, state: FSMContext):
    await state.update_data(photo_file_id=None)
    await finish_registration(message, state)


@router.message(RegistrationStates.photo, F.photo)
async def reg_photo(message: Message, state: FSMContext):
    photo_file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=photo_file_id)
    await finish_registration(message, state)


@router.message(RegistrationStates.photo)
async def reg_photo_wrong(message: Message):
    await message.answer("⚠️ Отправь фото или нажми «⏭ Пропустить»")


async def finish_registration(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    user = await get_or_create_user(message.from_user.id)
    await create_profile(
        user_id=user.id,
        nickname=data["nickname"],
        world_level=data["world_level"],
        main_dps=data["main_dps"],
        server=data["server"],
        description=data.get("description"),
        photo_file_id=data.get("photo_file_id")
    )
    await message.answer(
        "🎉 <b>Анкета создана!</b>\n\n"
        "Теперь можешь искать тиммейтов. Удачи на полях сражений! 🎖\n\n"
        "👇 Выбери действие:",
        reply_markup=get_main_menu()
    )
