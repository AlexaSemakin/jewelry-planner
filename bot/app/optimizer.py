from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Executor, Order, TransportRoute


@dataclass(frozen=True)
class PlanResult:
    feasible: bool
    total_cost: float
    finish_date: date
    items: list[dict]
    explanation: str


def add_working_days(start: date, days: int, working_days: list[int]) -> date:
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() in working_days:
            remaining -= 1
    return current


def normalize_stage_name(name: str) -> str:
    return name.strip().lower()


async def calculate_plan(session: AsyncSession, order: Order) -> PlanResult:
    executors = list(
        await session.scalars(
            select(Executor)
            .options(selectinload(Executor.city))
            .where(Executor.is_active.is_(True))
        )
    )
    routes = list(
        await session.scalars(
            select(TransportRoute)
            .options(selectinload(TransportRoute.from_city), selectinload(TransportRoute.to_city))
        )
    )

    if not order.stages:
        return PlanResult(False, 0, date.today(), [], "У заказа нет этапов производства.")

    current_date = date.today()
    current_city_id: int | None = None
    current_city_name: str | None = None
    total_cost = 0.0
    items: list[dict] = []
    explanation_parts: list[str] = []

    for stage in order.stages:
        normalized = normalize_stage_name(stage.name)
        candidates = [
            executor
            for executor in executors
            if executor.specialization.lower() in normalized
            or normalized in executor.specialization.lower()
            or executor.specialization.lower() == "универсальный"
        ]

        if not candidates:
            return PlanResult(
                False,
                total_cost,
                current_date,
                items,
                f"Для этапа «{stage.name}» нет активных исполнителей.",
            )

        best_variant = None
        for executor in candidates:
            logistics_cost = 0.0
            logistics_days = 0
            route_title = "без перевозки"

            if current_city_id is not None and current_city_id != executor.city_id:
                route = next(
                    (
                        route
                        for route in routes
                        if route.from_city_id == current_city_id and route.to_city_id == executor.city_id
                    ),
                    None,
                )
                if route is None:
                    continue
                logistics_cost = route.cost
                logistics_days = route.duration_days + route.handoff_days
                route_title = f"{route.from_city.name} → {route.to_city.name}, {route.method}"

            start_date = current_date + timedelta(days=logistics_days)
            finish_date = add_working_days(start_date, executor.duration_days, executor.working_days)
            production_cost = executor.duration_days * executor.cost_per_day
            variant_cost = production_cost + logistics_cost

            variant = {
                "executor": executor,
                "route_title": route_title,
                "start_date": start_date,
                "finish_date": finish_date,
                "production_cost": production_cost,
                "logistics_cost": logistics_cost,
                "variant_cost": variant_cost,
            }

            if best_variant is None:
                best_variant = variant
            else:
                if (variant["finish_date"] <= order.due_date, -variant["variant_cost"]) > (
                    best_variant["finish_date"] <= order.due_date,
                    -best_variant["variant_cost"],
                ):
                    best_variant = variant

        if best_variant is None:
            return PlanResult(
                False,
                total_cost,
                current_date,
                items,
                f"Не найден маршрут перевозки для этапа «{stage.name}».",
            )

        executor = best_variant["executor"]
        total_cost += float(best_variant["variant_cost"])
        current_date = best_variant["finish_date"]
        current_city_id = executor.city_id
        current_city_name = executor.city.name

        items.append(
            {
                "stage": stage.name,
                "executor": executor.name,
                "city": executor.city.name,
                "route": best_variant["route_title"],
                "start_date": best_variant["start_date"].isoformat(),
                "finish_date": best_variant["finish_date"].isoformat(),
                "production_cost": best_variant["production_cost"],
                "logistics_cost": best_variant["logistics_cost"],
            }
        )
        explanation_parts.append(
            f"Этап «{stage.name}»: выбран «{executor.name}» ({executor.city.name}), "
            f"так как он подходит по специализации и даёт стоимость {best_variant['variant_cost']:.0f} ₽."
        )

    feasible = current_date <= order.due_date
    if feasible:
        explanation = "План укладывается в срок. " + " ".join(explanation_parts)
    else:
        explanation = (
            f"Срок невыполним: обещанная дата {order.due_date.isoformat()}, "
            f"минимальная расчётная дата {current_date.isoformat()}. "
            "Причина: суммарная длительность этапов и логистики больше доступного окна. "
            + " ".join(explanation_parts)
        )

    return PlanResult(
        feasible=feasible,
        total_cost=total_cost,
        finish_date=current_date,
        items=items,
        explanation=explanation,
    )
