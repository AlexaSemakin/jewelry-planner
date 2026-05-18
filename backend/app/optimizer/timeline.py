"""
Утилиты для работы с временем планирования.

В CP-SAT всё работает в дискретных шагах (минутах от horizon_start).
Здесь — конверторы и расчёт «запрещённых интервалов» из календарей.
"""
from __future__ import annotations
from datetime import datetime, timedelta, date, time
from typing import List, Tuple

from app.core.config import settings


def horizon_start() -> datetime:
    """Начало горизонта планирования: сегодня, 00:00 UTC."""
    today = datetime.utcnow().date()
    return datetime.combine(today, time(0, 0))


def horizon_end() -> datetime:
    return horizon_start() + timedelta(days=settings.PLANNING_HORIZON_DAYS)


def to_steps(dt: datetime) -> int:
    """datetime -> номер шага от horizon_start (в шагах TIME_STEP_MIN)."""
    delta = dt - horizon_start()
    return int(delta.total_seconds() // 60 // settings.TIME_STEP_MIN)


def from_steps(steps: int) -> datetime:
    return horizon_start() + timedelta(minutes=steps * settings.TIME_STEP_MIN)


def hours_to_steps(hours: float) -> int:
    """Часы -> шаги, округление вверх."""
    minutes = hours * 60
    step = settings.TIME_STEP_MIN
    return max(1, int((minutes + step - 1) // step))


def total_horizon_steps() -> int:
    return hours_to_steps(settings.PLANNING_HORIZON_DAYS * 24)


def offwork_intervals(workdays: List[int]) -> List[Tuple[int, int]]:
    """
    Возвращает список (start_step, end_step_exclusive) для интервалов,
    в которые исполнитель НЕ работает (выходные дни в пределах горизонта).
    Используется как forbidden intervals в CP-SAT.
    """
    if not workdays:
        # На всякий случай — если работает 0 дней, считаем "всегда работает"
        workdays = list(range(7))
    workdays_set = set(workdays)
    intervals: List[Tuple[int, int]] = []
    start = horizon_start()
    steps_per_day = hours_to_steps(24)
    # weekday: 0=пн, 6=вс
    cur = None
    for d in range(settings.PLANNING_HORIZON_DAYS):
        day = start + timedelta(days=d)
        if day.weekday() not in workdays_set:
            day_start = d * steps_per_day
            day_end = (d + 1) * steps_per_day
            if cur is None:
                cur = [day_start, day_end]
            elif cur[1] == day_start:
                cur[1] = day_end
            else:
                intervals.append((cur[0], cur[1]))
                cur = [day_start, day_end]
    if cur is not None:
        intervals.append((cur[0], cur[1]))
    return intervals
