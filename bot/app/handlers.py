import html
import re
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import delete, func, select

from app.config import settings
from app.db import SessionLocal
from app.keyboards import (
    CANCEL_MENU,
    MAIN_MENU,
    ask_expert_keyboard,
    confirm_delete_plant_keyboard,
    delete_me_keyboard,
    followup_keyboard,
    last_watered_keyboard,
    plant_actions_keyboard,
    timezone_keyboard,
)
from app.models import ExpertQuestion, Plant, UserProfile
from app.safe_send import safe_send_message, safe_send_photo, send_message_with_retries
from app.repository import (
    count_user_plants,
    delete_user_data,
    get_or_create_user,
    get_plant_for_telegram_user,
    get_user_plants,
    log_action,
    mark_watered,
    snooze_plant,
)
from app.utils import format_date, parse_time, parse_timezone, user_today, water_status

router = Router()

WELCOME_TEXT = (
    "🌿 Привет! Добро пожаловать в PlantCare Bot — помощника по уходу за комнатными растениями.\n\n"
    "Сейчас у меня есть две главные функции:\n\n"
    "Контроль полива — помогу не забывать, когда пора полить растение, и буду присылать напоминания.\n\n"
    "Связь с экспертом — если появятся вопросы по уходу, передам их специалисту и помогу получить ответ.\n\n"
    "Просто добавь своё растение и начни пользоваться 🌱"
)


class TimezoneState(StatesGroup):
    waiting_for_timezone = State()


class AddPlantState(StatesGroup):
    name = State()
    interval = State()
    last_watered = State()


class ChangeFrequencyState(StatesGroup):
    value = State()


class AskExpertState(StatesGroup):
    collecting = State()


async def ensure_user(message: Message) -> UserProfile:
    async with SessionLocal() as session:
        return await get_or_create_user(
            session=session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )


@router.message(Command("start"))
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await ensure_user(message)
    await message.answer(WELCOME_TEXT, reply_markup=MAIN_MENU)

    if not user.timezone_is_set:
        await state.set_state(TimezoneState.waiting_for_timezone)
        await message.answer(
            "Укажите ваш часовой пояс. Можно выбрать «Москва» или написать город, например: Владивосток.",
            reply_markup=timezone_keyboard(),
        )


@router.callback_query(F.data.startswith("tz:"))
async def set_timezone_callback(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.split(":", 1)[1]
    timezone = "Europe/Moscow" if value == "skip" else value

    async with SessionLocal() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        user.timezone = timezone
        user.timezone_is_set = True
        await session.commit()
        await log_action(session, callback.from_user.id, "timezone_set", timezone)

    await state.clear()
    await callback.message.answer("Готово! Буду ориентироваться на ваш местный часовой пояс 🌿", reply_markup=MAIN_MENU)
    await callback.answer()


@router.message(TimezoneState.waiting_for_timezone)
async def set_timezone_text(message: Message, state: FSMContext) -> None:
    timezone = parse_timezone(message.text)
    if not timezone:
        await message.answer("Не получилось распознать часовой пояс. Напишите город, например: Москва или Владивосток.")
        return

    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        user.timezone = timezone
        user.timezone_is_set = True
        await session.commit()
        await log_action(session, message.from_user.id, "timezone_set", timezone)

    await state.clear()
    await message.answer("Готово! Часовой пояс сохранён 🌿", reply_markup=MAIN_MENU)


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "Я умею напоминать о поливе растений и передавать вопросы эксперту.\n\n"
        "Команды:\n"
        "/add_plant — добавить растение\n"
        "/my_plants — мои растения\n"
        "/watered — отметить полив\n"
        "/ask_expert — спросить эксперта\n"
        "/settings — настройки напоминаний\n"
        "/delete_me — удалить все ваши данные\n"
        "/help — справка",
        reply_markup=MAIN_MENU,
    )


@router.message(Command("settings"))
async def settings_command(message: Message) -> None:
    await ensure_user(message)
    await message.answer(
        "Настройки:\n\n"
        "Чтобы изменить время напоминаний, отправьте команду так:\n"
        "/reminder_time 09:30\n\n"
        "Чтобы изменить часовой пояс, отправьте:\n"
        "/timezone Москва\n"
        "или\n"
        "/timezone Владивосток",
        reply_markup=MAIN_MENU,
    )


@router.message(Command("reminder_time"))
async def reminder_time_command(message: Message) -> None:
    value = (message.text or "").replace("/reminder_time", "", 1).strip()
    parsed = parse_time(value)
    if not parsed:
        await message.answer("Введите время в формате ЧЧ:ММ. Например: /reminder_time 09:30")
        return

    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        user.reminder_time = parsed
        await session.commit()
        await log_action(session, message.from_user.id, "reminder_time_set", value)

    await message.answer(f"Готово! Теперь напоминания будут приходить в {parsed.strftime('%H:%M')} 🌿", reply_markup=MAIN_MENU)


@router.message(Command("timezone"))
async def timezone_command(message: Message) -> None:
    value = (message.text or "").replace("/timezone", "", 1).strip()
    timezone = parse_timezone(value)
    if not timezone:
        await message.answer("Не получилось распознать часовой пояс. Пример: /timezone Москва")
        return

    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        user.timezone = timezone
        user.timezone_is_set = True
        await session.commit()
        await log_action(session, message.from_user.id, "timezone_set", timezone)

    await message.answer("Готово! Часовой пояс обновлён 🌿", reply_markup=MAIN_MENU)


@router.message(Command("add_plant"))
@router.message(F.text == "🌱 Добавить растение")
async def add_plant_start(message: Message, state: FSMContext) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        plants_count = await count_user_plants(session, user.id)

    if plants_count >= 15:
        await message.answer(
            "Вы достигли лимита в 15 растений. Чтобы добавить новое, удалите одно из существующих.",
            reply_markup=MAIN_MENU,
        )
        return

    await state.set_state(AddPlantState.name)
    await message.answer("Как называется растение?", reply_markup=CANCEL_MENU)


@router.message(F.text == "❌ Отмена")
async def cancel_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=MAIN_MENU)


@router.callback_query(F.data == "cancel")
@router.callback_query(F.data == "cancel_inline")
async def cancel_inline(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Действие отменено.", reply_markup=MAIN_MENU)
    await callback.answer()


@router.message(AddPlantState.name)
async def add_plant_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Введите название растения текстом, например: Монстера.")
        return

    await state.update_data(name=name)
    await state.set_state(AddPlantState.interval)
    await message.answer("Как часто его нужно поливать? Введите число дней между поливами.")


@router.message(AddPlantState.interval)
async def add_plant_interval(message: Message, state: FSMContext) -> None:
    try:
        interval = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите именно число дней. Например: 7")
        return

    if not 1 <= interval <= 60:
        await message.answer("Частота должна быть целым числом от 1 до 60 дней.")
        return

    await state.update_data(interval=interval)
    await state.set_state(AddPlantState.last_watered)
    await message.answer("Когда вы поливали его в последний раз?", reply_markup=last_watered_keyboard())


@router.callback_query(AddPlantState.last_watered, F.data.startswith("last_watered:"))
async def add_plant_last_watered(callback: CallbackQuery, state: FSMContext) -> None:
    choice = callback.data.split(":", 1)[1]
    data = await state.get_data()

    async with SessionLocal() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        today = user_today(user.timezone)
        if choice == "today":
            last_watered_on = today
            next_watering_on = today + timedelta(days=data["interval"])
        else:
            last_watered_on = None
            next_watering_on = today

        plant = Plant(
            user_id=user.id,
            name=data["name"],
            watering_interval_days=data["interval"],
            last_watered_on=last_watered_on,
            next_watering_on=next_watering_on,
        )
        session.add(plant)
        await session.commit()
        await log_action(session, callback.from_user.id, "plant_added", data["name"])

    await state.clear()
    await callback.message.answer(f"Готово! Я напомню о поливе {format_date(next_watering_on)}.", reply_markup=MAIN_MENU)
    await callback.answer()


@router.message(Command("my_plants"))
@router.message(F.text == "📋 Мои растения")
async def my_plants(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        plants = await get_user_plants(session, user.id)
        today = user_today(user.timezone)

    if not plants:
        await message.answer("Вы ещё не добавили ни одного растения. Нажмите «Добавить растение», чтобы начать.", reply_markup=MAIN_MENU)
        return

    for plant in plants:
        text = (
            f"🌱 <b>{html.escape(plant.name)}</b>\n"
            f"{water_status(plant.next_watering_on, today)}\n"
            f"Следующий полив: {format_date(plant.next_watering_on)}"
        )
        await message.answer(text, reply_markup=plant_actions_keyboard(plant.id))


@router.message(Command("watered"))
async def watered_command(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        plants = await get_user_plants(session, user.id)
        today = user_today(user.timezone)

    if not plants:
        await message.answer(
            "Вы ещё не добавили ни одного растения. Нажмите «Добавить растение», чтобы начать.",
            reply_markup=MAIN_MENU,
        )
        return

    await message.answer("Выберите растение, которое вы полили 🌿", reply_markup=MAIN_MENU)
    for plant in plants:
        text = (
            f"🌱 <b>{html.escape(plant.name)}</b>\n"
            f"{water_status(plant.next_watering_on, today)}\n"
            f"Следующий полив: {format_date(plant.next_watering_on)}"
        )
        await message.answer(text, reply_markup=plant_actions_keyboard(plant.id))


@router.callback_query(F.data.startswith("water:"))
async def water_callback(callback: CallbackQuery) -> None:
    plant_id = int(callback.data.split(":", 1)[1])
    async with SessionLocal() as session:
        result = await get_plant_for_telegram_user(session, plant_id, callback.from_user.id)
        if not result:
            await callback.message.answer("Растение не найдено.", reply_markup=MAIN_MENU)
            await callback.answer()
            return
        plant, user = result
        next_date = await mark_watered(session, plant, user)
        await log_action(session, callback.from_user.id, "plant_watered", plant.name)

    await callback.message.answer(f"Отметил! Следующий полив — {format_date(next_date)}.", reply_markup=MAIN_MENU)
    await callback.answer()


@router.callback_query(F.data.startswith("snooze:"))
async def snooze_callback(callback: CallbackQuery) -> None:
    _, plant_id_raw, days_raw = callback.data.split(":")
    plant_id = int(plant_id_raw)
    days = int(days_raw)

    async with SessionLocal() as session:
        result = await get_plant_for_telegram_user(session, plant_id, callback.from_user.id)
        if not result:
            await callback.message.answer("Растение не найдено.", reply_markup=MAIN_MENU)
            await callback.answer()
            return
        plant, user = result
        next_date = await snooze_plant(session, plant, user, days)
        await log_action(session, callback.from_user.id, "plant_snoozed", f"{plant.name}: {days}")

    await callback.message.answer(f"Хорошо, напомню {format_date(next_date)} 🌿", reply_markup=MAIN_MENU)
    await callback.answer()


@router.callback_query(F.data.startswith("freq:"))
async def change_frequency_start(callback: CallbackQuery, state: FSMContext) -> None:
    plant_id = int(callback.data.split(":", 1)[1])
    await state.set_state(ChangeFrequencyState.value)
    await state.update_data(plant_id=plant_id)
    await callback.message.answer("Введите новое число дней между поливами.", reply_markup=CANCEL_MENU)
    await callback.answer()


@router.message(ChangeFrequencyState.value)
async def change_frequency_value(message: Message, state: FSMContext) -> None:
    try:
        interval = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите именно число дней. Например: 7")
        return

    if not 1 <= interval <= 60:
        await message.answer("Частота должна быть целым числом от 1 до 60 дней.")
        return

    data = await state.get_data()
    plant_id = data["plant_id"]

    async with SessionLocal() as session:
        result = await get_plant_for_telegram_user(session, plant_id, message.from_user.id)
        if not result:
            await message.answer("Растение не найдено.", reply_markup=MAIN_MENU)
            await state.clear()
            return
        plant, user = result
        plant.watering_interval_days = interval
        base_date = plant.last_watered_on or user_today(user.timezone)
        plant.next_watering_on = base_date + timedelta(days=interval)
        plant.last_reminder_sent_at = None
        plant.repeat_reminder_sent_at = None
        plant.updated_at = datetime.utcnow()
        await session.commit()
        await log_action(session, message.from_user.id, "plant_frequency_changed", f"{plant.name}: {interval}")

    await state.clear()
    await message.answer(f"Готово! Новая частота — раз в {interval} дней.", reply_markup=MAIN_MENU)


@router.callback_query(F.data.startswith("delete_plant:"))
async def delete_plant_start(callback: CallbackQuery) -> None:
    plant_id = int(callback.data.split(":", 1)[1])
    async with SessionLocal() as session:
        result = await get_plant_for_telegram_user(session, plant_id, callback.from_user.id)
        if not result:
            await callback.message.answer("Растение не найдено.")
            await callback.answer()
            return
        plant, _ = result
        name = plant.name

    await callback.message.answer(
        f"Точно удалить «{html.escape(name)}»?",
        reply_markup=confirm_delete_plant_keyboard(plant_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_plant:"))
async def delete_plant_confirm(callback: CallbackQuery) -> None:
    plant_id = int(callback.data.split(":", 1)[1])
    async with SessionLocal() as session:
        result = await get_plant_for_telegram_user(session, plant_id, callback.from_user.id)
        if not result:
            await callback.message.answer("Растение не найдено.", reply_markup=MAIN_MENU)
            await callback.answer()
            return
        plant, _ = result
        name = plant.name
        await session.delete(plant)
        await session.commit()
        await log_action(session, callback.from_user.id, "plant_deleted", name)

    await callback.message.answer("Растение удалено.", reply_markup=MAIN_MENU)
    await callback.answer()


@router.message(Command("ask_expert"))
@router.message(F.text == "🧑‍🌾 Спросить эксперта")
async def ask_expert_start(message: Message, state: FSMContext) -> None:
    await ensure_user(message)
    await state.set_state(AskExpertState.collecting)
    await state.update_data(text="", photos=[], parent_question_id=None)
    await message.answer(
        "Опишите, что происходит с растением. Можно прикрепить до 3 фотографий.",
        reply_markup=CANCEL_MENU,
    )


@router.callback_query(F.data.startswith("expert_followup:"))
async def expert_followup(callback: CallbackQuery, state: FSMContext) -> None:
    question_id = int(callback.data.split(":", 1)[1])

    async with SessionLocal() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        result = await session.execute(
            select(ExpertQuestion)
            .where(ExpertQuestion.id == question_id)
            .where(ExpertQuestion.user_id == user.id)
        )
        question = result.scalars().first()

    if not question:
        await callback.message.answer("Обсуждение не найдено.", reply_markup=MAIN_MENU)
        await callback.answer()
        return

    if question.status == "closed":
        await callback.message.answer("Это обсуждение уже закрыто.", reply_markup=MAIN_MENU)
        await callback.answer()
        return

    await state.set_state(AskExpertState.collecting)
    await state.update_data(text="", photos=[], parent_question_id=question_id)
    await callback.message.answer("Напишите уточняющий вопрос. Можно прикрепить до 3 фотографий.", reply_markup=CANCEL_MENU)
    await callback.answer()


@router.message(AskExpertState.collecting, F.text)
async def collect_expert_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Вопрос отменён.", reply_markup=MAIN_MENU)
        return

    if len(text) > 1000:
        await message.answer("Текст вопроса должен быть до 1000 символов. Сократите, пожалуйста 🌿")
        return

    data = await state.get_data()
    previous_text = data.get("text", "")
    new_text = text if not previous_text else f"{previous_text}\n{text}"
    if len(new_text) > 1000:
        await message.answer("Общий текст вопроса получился длиннее 1000 символов. Сократите, пожалуйста.")
        return

    await state.update_data(text=new_text)
    await message.answer("Добавил текст к вопросу. Можно отправить ещё фото или передать вопрос эксперту.", reply_markup=ask_expert_keyboard())


@router.message(AskExpertState.collecting, F.photo)
async def collect_expert_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    photos = list(data.get("photos", []))

    if len(photos) >= 3:
        await message.answer(
            "Можно прикрепить максимум 3 фотографии к одному вопросу.",
            reply_markup=ask_expert_keyboard(),
        )
        return

    photos.append(message.photo[-1].file_id)

    caption = (message.caption or "").strip()
    current_text = data.get("text", "")

    if caption:
        if len(caption) > 1000:
            await message.answer("Подпись к фото должна быть до 1000 символов. Сократите, пожалуйста 🌿")
            return

        new_text = caption if not current_text else f"{current_text}\n{caption}"

        if len(new_text) > 1000:
            await message.answer("Общий текст вопроса получился длиннее 1000 символов. Сократите, пожалуйста.")
            return

        await state.update_data(photos=photos, text=new_text)
    else:
        await state.update_data(photos=photos)

    await message.answer(
        f"Фото добавлено ({len(photos)}/3). Можно отправить ещё или передать вопрос эксперту.",
        reply_markup=ask_expert_keyboard(),
    )

@router.message(AskExpertState.collecting)
async def collect_expert_unknown(message: Message) -> None:
    await message.answer("Можно отправить текст и до 3 фотографий.", reply_markup=ask_expert_keyboard())


@router.callback_query(F.data == "expert_cancel")
async def expert_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Вопрос отменён.", reply_markup=MAIN_MENU)
    await callback.answer()


@router.callback_query(F.data == "expert_send")
async def expert_send(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    text = data.get("text", "").strip()
    photos = list(data.get("photos", []))
    parent_question_id = data.get("parent_question_id")

    if not text and not photos:
        await callback.message.answer("Опишите, пожалуйста, ваш вопрос.", reply_markup=ask_expert_keyboard())
        await callback.answer()
        return

    if not settings.expert_chat_id:
        await callback.message.answer("Группа эксперта пока не настроена. Укажите EXPERT_CHAT_ID в .env.", reply_markup=MAIN_MENU)
        await callback.answer()
        return

    async with SessionLocal() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        question = ExpertQuestion(
            user_id=user.id,
            parent_question_id=parent_question_id,
            text=text,
            photo_file_ids="\n".join(photos),
            status="sent",
        )
        session.add(question)
        await session.commit()
        await session.refresh(question)

        username = f"@{callback.from_user.username}" if callback.from_user.username else "без username"
        title = f"📩 Новый вопрос #{question.id}" if not parent_question_id else f"📩 Уточнение к вопросу #{parent_question_id} / новое сообщение #{question.id}"
        expert_text = (
            f"{title}\n"
            f"От: {html.escape(username)} (ID {callback.from_user.id})\n\n"
            f"{html.escape(text) if text else '[без текста]'}"
        )

        expert_message = await send_message_with_retries(callback.bot, settings.expert_chat_id, expert_text)
        if not expert_message:
            question.status = "failed"
            await session.commit()
            await callback.message.answer(
                "Не получилось отправить вопрос эксперту после 3 попыток. Попробуйте позже 🌿",
                reply_markup=MAIN_MENU,
            )
            await callback.answer()
            return

        question.expert_message_id = expert_message.message_id
        await session.commit()

        for index, photo_id in enumerate(photos, start=1):
            await safe_send_photo(
                callback.bot,
                settings.expert_chat_id,
                photo=photo_id,
                reply_to_message_id=expert_message.message_id,
                caption=f"Фото {index}/{len(photos)} к вопросу #{question.id}",
            )

        await log_action(session, callback.from_user.id, "expert_question_sent", str(question.id))

    await state.clear()
    await callback.message.answer("Спасибо! Ваш вопрос отправлен. Ответ обычно приходит в течение 24 часов.", reply_markup=MAIN_MENU)
    await callback.answer()


@router.message(lambda message: settings.expert_chat_id is not None and message.chat.id == settings.expert_chat_id and message.reply_to_message is not None)
async def expert_reply(message: Message) -> None:
    answer = (message.text or message.caption or "").strip()
    if not answer:
        await message.reply("Ответ должен быть текстом.")
        return

    reply_id = message.reply_to_message.message_id
    question_id: int | None = None

    async with SessionLocal() as session:
        result = await session.execute(select(ExpertQuestion).where(ExpertQuestion.expert_message_id == reply_id))
        question = result.scalars().first()

        if not question:
            source_text = message.reply_to_message.text or message.reply_to_message.caption or ""
            match = re.search(r"#(\d+)", source_text)
            if match:
                question_id = int(match.group(1))
                result = await session.execute(select(ExpertQuestion).where(ExpertQuestion.id == question_id))
                question = result.scalars().first()

        if not question:
            await message.reply("Не понял, к какому вопросу относится ответ. Ответьте реплаем на сообщение с номером вопроса.")
            return

        if question.status == "closed":
            await message.reply("Это обсуждение уже закрыто.")
            return

        user_result = await session.execute(select(UserProfile).where(UserProfile.id == question.user_id))
        user = user_result.scalars().first()
        if not user:
            await message.reply("Пользователь не найден.")
            return

        question.status = "answered"
        question.answer_text = answer
        question.answered_at = datetime.utcnow()
        await session.commit()
        await log_action(session, user.telegram_id, "expert_answer_delivered", str(question.id))

    delivered = await safe_send_message(
        message.bot,
        user.telegram_id,
        f"🌿 Ответ эксперта:\n\n{html.escape(answer)}",
        reply_markup=followup_keyboard(question.id),
    )
    if delivered:
        await message.reply("✅ Доставлено")
    else:
        await message.reply("Не удалось доставить ответ пользователю после 3 попыток.")


@router.callback_query(F.data.startswith("expert_close:"))
async def expert_close(callback: CallbackQuery) -> None:
    question_id = int(callback.data.split(":", 1)[1])

    async with SessionLocal() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        result = await session.execute(
            select(ExpertQuestion)
            .where(ExpertQuestion.id == question_id)
            .where(ExpertQuestion.user_id == user.id)
        )
        question = result.scalars().first()
        if not question:
            await callback.message.answer("Обсуждение не найдено.", reply_markup=MAIN_MENU)
            await callback.answer()
            return

        question.status = "closed"
        await session.commit()
        await log_action(session, callback.from_user.id, "expert_discussion_closed", str(question.id))

    await callback.message.answer("Обсуждение закрыто 🌿", reply_markup=MAIN_MENU)
    await callback.answer()


@router.message(Command("delete_me"))
async def delete_me_start(message: Message) -> None:
    await message.answer(
        "Это удалит все ваши растения и историю вопросов эксперту. Действие необратимо. Точно продолжить?",
        reply_markup=delete_me_keyboard(),
    )


@router.callback_query(F.data == "delete_me_cancel")
async def delete_me_cancel(callback: CallbackQuery) -> None:
    await callback.message.answer("Удаление отменено.", reply_markup=MAIN_MENU)
    await callback.answer()


@router.callback_query(F.data == "delete_me_confirm")
async def delete_me_confirm(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        await delete_user_data(session, callback.from_user.id)
        await log_action(session, callback.from_user.id, "delete_me_confirmed")

    await callback.message.answer("Все ваши данные удалены. Вы можете начать заново в любой момент через /start.", reply_markup=MAIN_MENU)
    await callback.answer()


@router.message()
async def fallback(message: Message) -> None:
    if message.chat.type != "private":
        return
    await message.answer("Используйте кнопки ниже 👇", reply_markup=MAIN_MENU)
