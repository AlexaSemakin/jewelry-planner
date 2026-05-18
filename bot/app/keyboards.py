from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать оценку", callback_data="order:create")],
            [InlineKeyboardButton(text="📦 Мои заказы", callback_data="orders:list")],
            [InlineKeyboardButton(text="📊 Дашборд", callback_data="dashboard")],
            [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
        ]
    )


def order_actions(order_id: int, can_start: bool = True) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🔄 Пересчитать план", callback_data=f"order:recalc:{order_id}")]]
    if can_start:
        rows.append([InlineKeyboardButton(text="🚀 Запустить в работу", callback_data=f"order:start:{order_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")]]
    )
