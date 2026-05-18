from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🌱 Добавить растение"), KeyboardButton(text="📋 Мои растения")],
        [KeyboardButton(text="🧑‍🌾 Спросить эксперта")],
    ],
    resize_keyboard=True,
)

CANCEL_MENU = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отмена")]],
    resize_keyboard=True,
)


def timezone_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Москва", callback_data="tz:Europe/Moscow")],
            [InlineKeyboardButton(text="Пропустить", callback_data="tz:skip")],
        ]
    )


def last_watered_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сегодня", callback_data="last_watered:today")],
            [InlineKeyboardButton(text="Не помню / только купил", callback_data="last_watered:unknown")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        ]
    )


def plant_actions_keyboard(plant_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я полил(а)", callback_data=f"water:{plant_id}")],
            [InlineKeyboardButton(text="✏️ Изменить частоту", callback_data=f"freq:{plant_id}")],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_plant:{plant_id}")],
        ]
    )


def reminder_keyboard(plant_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я полил(а)", callback_data=f"water:{plant_id}")],
            [InlineKeyboardButton(text="⏰ Отложить на 1 день", callback_data=f"snooze:{plant_id}:1")],
            [InlineKeyboardButton(text="⏰ Отложить на 3 дня", callback_data=f"snooze:{plant_id}:3")],
        ]
    )


def confirm_delete_plant_keyboard(plant_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data=f"confirm_delete_plant:{plant_id}")],
            [InlineKeyboardButton(text="Нет", callback_data="cancel_inline")],
        ]
    )


def ask_expert_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📨 Отправить эксперту", callback_data="expert_send")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="expert_cancel")],
        ]
    )


def followup_keyboard(question_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Задать уточнение", callback_data=f"expert_followup:{question_id}")],
            [InlineKeyboardButton(text="Закрыть обсуждение", callback_data=f"expert_close:{question_id}")],
        ]
    )


def delete_me_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, удалить", callback_data="delete_me_confirm")],
            [InlineKeyboardButton(text="Отмена", callback_data="delete_me_cancel")],
        ]
    )
