from __future__ import annotations

from datetime import date, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db import SessionLocal
from app.keyboards import back_to_menu, main_menu, order_actions
from app.models import Order, OrderHistory, OrderStage
from app.optimizer import calculate_plan

router = Router()


class CreateOrder(StatesGroup):
    title = State()
    due_days = State()
    weight = State()
    materials = State()
    stages = State()


@router.message(F.text == "/start")
async def start(message: Message) -> None:
    await message.answer(
        "Ювелирный планировщик готов. Здесь можно создать оценку, рассчитать план производства и запустить заказ в работу.",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "menu")
async def menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Сценарий: создать оценку → указать срок, вес, материалы и этапы → получить план.\n\n"
        "Пример этапов: Основа, Камни, Закрепка, Гравировка, Полировка",
        reply_markup=back_to_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "order:create")
async def create_order_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CreateOrder.title)
    await callback.message.edit_text("Введите название изделия, например: Кольцо с сапфиром")
    await callback.answer()


@router.message(CreateOrder.title)
async def create_order_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(CreateOrder.due_days)
    await message.answer("Через сколько дней заказ должен быть готов? Например: 14")


@router.message(CreateOrder.due_days)
async def create_order_due_days(message: Message, state: FSMContext) -> None:
    try:
        due_days = int(message.text.strip())
        if due_days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительное число дней, например: 14")
        return

    await state.update_data(due_days=due_days)
    await state.set_state(CreateOrder.weight)
    await message.answer("Введите примерный вес изделия в граммах, например: 8.5")


@router.message(CreateOrder.weight)
async def create_order_weight(message: Message, state: FSMContext) -> None:
    try:
        weight = float(message.text.replace(",", ".").strip())
        if weight < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите число, например: 8.5")
        return

    await state.update_data(weight=weight)
    await state.set_state(CreateOrder.materials)
    await message.answer("Введите материалы, например: золото 585, сапфир, бриллианты")


@router.message(CreateOrder.materials)
async def create_order_materials(message: Message, state: FSMContext) -> None:
    await state.update_data(materials=message.text.strip())
    await state.set_state(CreateOrder.stages)
    await message.answer(
        "Введите этапы производства через запятую.\n"
        "Пример: Основа, Камни, Закрепка, Гравировка, Полировка"
    )


@router.message(CreateOrder.stages)
async def create_order_stages(message: Message, state: FSMContext) -> None:
    stages = [part.strip() for part in message.text.split(",") if part.strip()]
    if not stages:
        await message.answer("Нужно указать хотя бы один этап.")
        return

    data = await state.get_data()
    telegram_user_id = message.from_user.id
    due_date = date.today() + timedelta(days=int(data["due_days"]))

    async with SessionLocal() as session:
        order = Order(
            telegram_user_id=telegram_user_id,
            title=data["title"],
            materials=data["materials"],
            weight_grams=float(data["weight"]),
            due_date=due_date,
            status="estimate",
        )
        session.add(order)
        await session.flush()

        for index, stage_name in enumerate(stages, start=1):
            session.add(OrderStage(order_id=order.id, position=index, name=stage_name))

        session.add(OrderHistory(order_id=order.id, message="Создана предварительная оценка заказа."))
        await session.commit()

        order = await load_order(session, order.id, telegram_user_id)
        result = await calculate_plan(session, order)
        order.total_cost = result.total_cost
        order.planned_finish_date = result.finish_date
        order.plan_explanation = result.explanation
        order.plan_json = result.items
        session.add(OrderHistory(order_id=order.id, message="Рассчитан производственный план."))
        await session.commit()

        text = format_order_plan(order, result.feasible)

    await state.clear()
    await message.answer(text, reply_markup=order_actions(order.id, can_start=result.feasible))


@router.callback_query(F.data == "orders:list")
async def list_orders(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        orders = list(
            await session.scalars(
                select(Order)
                .where(Order.telegram_user_id == callback.from_user.id)
                .order_by(Order.created_at.desc())
                .limit(10)
            )
        )

    if not orders:
        await callback.message.edit_text("Заказов пока нет.", reply_markup=back_to_menu())
        await callback.answer()
        return

    lines = ["Последние заказы:"]
    for order in orders:
        finish = order.planned_finish_date.isoformat() if order.planned_finish_date else "не рассчитано"
        cost = f"{order.total_cost:.0f} ₽" if order.total_cost else "не рассчитано"
        lines.append(f"#{order.id} — {order.title}\nСтатус: {order.status}; готовность: {finish}; стоимость: {cost}")

    await callback.message.edit_text("\n\n".join(lines), reply_markup=back_to_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("order:recalc:"))
async def recalc_order(callback: CallbackQuery) -> None:
    order_id = int(callback.data.split(":")[-1])

    async with SessionLocal() as session:
        order = await load_order(session, order_id, callback.from_user.id)
        if order is None:
            await callback.answer("Заказ не найден", show_alert=True)
            return

        result = await calculate_plan(session, order)
        order.total_cost = result.total_cost
        order.planned_finish_date = result.finish_date
        order.plan_explanation = result.explanation
        order.plan_json = result.items
        session.add(OrderHistory(order_id=order.id, message="План пересчитан."))
        await session.commit()
        text = format_order_plan(order, result.feasible)

    await callback.message.edit_text(text, reply_markup=order_actions(order.id, can_start=result.feasible))
    await callback.answer()


@router.callback_query(F.data.startswith("order:start:"))
async def start_order(callback: CallbackQuery) -> None:
    order_id = int(callback.data.split(":")[-1])

    async with SessionLocal() as session:
        order = await load_order(session, order_id, callback.from_user.id)
        if order is None:
            await callback.answer("Заказ не найден", show_alert=True)
            return

        order.status = "in_progress"
        session.add(OrderHistory(order_id=order.id, message="Заказ запущен в производство."))
        await session.commit()

    await callback.message.edit_text("Заказ запущен в производство.", reply_markup=back_to_menu())
    await callback.answer()


@router.callback_query(F.data == "dashboard")
async def dashboard(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user_id = callback.from_user.id
        total = await session.scalar(select(func.count(Order.id)).where(Order.telegram_user_id == user_id))
        in_progress = await session.scalar(
            select(func.count(Order.id)).where(Order.telegram_user_id == user_id, Order.status == "in_progress")
        )
        estimates = await session.scalar(
            select(func.count(Order.id)).where(Order.telegram_user_id == user_id, Order.status == "estimate")
        )
        risky = await session.scalar(
            select(func.count(Order.id)).where(
                Order.telegram_user_id == user_id,
                Order.planned_finish_date.is_not(None),
                Order.planned_finish_date > Order.due_date,
            )
        )

    await callback.message.edit_text(
        "Дашборд:\n"
        f"Всего заказов: {total or 0}\n"
        f"Оценки: {estimates or 0}\n"
        f"В работе: {in_progress or 0}\n"
        f"С риском срыва срока: {risky or 0}",
        reply_markup=back_to_menu(),
    )
    await callback.answer()


async def load_order(session, order_id: int, telegram_user_id: int) -> Order | None:
    return await session.scalar(
        select(Order)
        .options(selectinload(Order.stages))
        .where(Order.id == order_id, Order.telegram_user_id == telegram_user_id)
    )


def format_order_plan(order: Order, feasible: bool) -> str:
    status = "✅ срок реалистичен" if feasible else "⚠️ срок невыполним"
    lines = [
        f"Заказ #{order.id}: {order.title}",
        f"Статус расчёта: {status}",
        f"Материалы: {order.materials}",
        f"Вес: {order.weight_grams:g} г",
        f"Клиентский срок: {order.due_date.isoformat()}",
        f"Расчётная готовность: {order.planned_finish_date.isoformat() if order.planned_finish_date else 'не рассчитано'}",
        f"Стоимость: {order.total_cost:.0f} ₽" if order.total_cost is not None else "Стоимость: не рассчитано",
        "",
        "План:",
    ]

    for item in order.plan_json or []:
        lines.append(
            f"• {item['stage']} → {item['executor']} ({item['city']})\n"
            f"  {item['start_date']} — {item['finish_date']}; "
            f"логистика: {item['route']}; "
            f"стоимость: {item['production_cost'] + item['logistics_cost']:.0f} ₽"
        )

    lines.extend(["", "Объяснение:", order.plan_explanation or "Нет объяснения."])
    return "\n".join(lines)
