"""
Логистический модуль (п.9 ТЗ).

Архитектура: интерфейс TransportProvider + конкретные реализации.
Сейчас используется StubTransportProvider, читающий маршруты из БД.
Замена на реальный коннектор (РЖД, Авиа) сводится к замене класса
в TransportAdapter.get_provider() — ядро системы не меняется.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Route, City


@dataclass
class TransportOption:
    """Опция перемещения между двумя городами."""
    route_id: int
    origin_id: int
    destination_id: int
    mode: str
    cost: float
    duration_hours: float          # время в пути
    handover_hours: float          # передача исполнителю
    pickup_hours: float            # получение готового изделия

    @property
    def total_hours(self) -> float:
        return self.duration_hours + self.handover_hours + self.pickup_hours


class TransportProvider(ABC):
    @abstractmethod
    def options(self, db: Session, origin_id: int, destination_id: int) -> List[TransportOption]:
        ...


class StubTransportProvider(TransportProvider):
    """Берёт варианты из таблицы routes — играет роль имитации внешних API."""
    def options(self, db: Session, origin_id: int, destination_id: int) -> List[TransportOption]:
        if origin_id == destination_id:
            return []
        rows = db.query(Route).filter(
            Route.origin_id == origin_id,
            Route.destination_id == destination_id,
        ).all()
        return [
            TransportOption(
                route_id=r.id,
                origin_id=r.origin_id,
                destination_id=r.destination_id,
                mode=r.mode,
                cost=r.cost,
                duration_hours=r.duration_hours,
                handover_hours=r.handover_hours,
                pickup_hours=r.pickup_hours,
            )
            for r in rows
        ]


# Здесь можно подключить RzdApiProvider / AviaApiProvider при их появлении.
class TransportAdapter:
    _provider: TransportProvider = StubTransportProvider()

    @classmethod
    def set_provider(cls, provider: TransportProvider) -> None:
        cls._provider = provider

    @classmethod
    def options(cls, db: Session, origin_id: int, destination_id: int) -> List[TransportOption]:
        return cls._provider.options(db, origin_id, destination_id)
