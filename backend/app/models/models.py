"""
ORM-модели согласно п.6 ТЗ.

Связи:
  City 1---* Performer 1---* PerformerStage *---1 StageTemplate
  City 1---* Route *---1 City (origin/destination)
  Order 1---* Stage *---1 StageTemplate
  Stage *---* Performer (через StageCandidate)
  Plan 1---* PlanStage, PlanMovement
  Order 1---* OrderHistory
"""
from __future__ import annotations

from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    String, Integer, ForeignKey, Date, DateTime, Float, Boolean, Text, JSON, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


# ---------- Справочники ----------

class City(Base):
    __tablename__ = "cities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)

    performers: Mapped[List["Performer"]] = relationship(back_populates="city")


class StageTemplate(Base):
    """Шаблон типа этапа: 'Изготовление основы', 'Закрепка камней' и т.п."""
    __tablename__ = "stage_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    # JSON-schema атрибутов, специфичных для типа этапа (для гибкого расширения, п.6 ТЗ)
    attributes_schema: Mapped[dict] = mapped_column(JSON, default=dict)


class Performer(Base):
    __tablename__ = "performers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    specialization: Mapped[str] = mapped_column(String(200), default="")
    contact: Mapped[str] = mapped_column(String(200), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Рабочие дни недели: список 0..6 (0 = пн). Хранится как JSON.
    workdays: Mapped[list] = mapped_column(JSON, default=lambda: [0, 1, 2, 3, 4])

    city: Mapped[City] = relationship(back_populates="performers")
    skills: Mapped[List["PerformerStage"]] = relationship(
        back_populates="performer", cascade="all, delete-orphan"
    )


class PerformerStage(Base):
    """Какие типы этапов выполняет исполнитель, по какой цене и в какие сроки."""
    __tablename__ = "performer_stages"
    __table_args__ = (UniqueConstraint("performer_id", "stage_template_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    performer_id: Mapped[int] = mapped_column(ForeignKey("performers.id", ondelete="CASCADE"))
    stage_template_id: Mapped[int] = mapped_column(ForeignKey("stage_templates.id"))
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    duration_hours: Mapped[float] = mapped_column(Float, default=8.0)

    performer: Mapped[Performer] = relationship(back_populates="skills")
    stage_template: Mapped[StageTemplate] = relationship()


class Route(Base):
    """Маршрут между двумя городами (один из вариантов транспорта)."""
    __tablename__ = "routes"
    id: Mapped[int] = mapped_column(primary_key=True)
    origin_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    destination_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    mode: Mapped[str] = mapped_column(String(40))   # "rail" | "air" | "courier"
    cost: Mapped[float] = mapped_column(Float)
    duration_hours: Mapped[float] = mapped_column(Float)
    handover_hours: Mapped[float] = mapped_column(Float, default=1.0)   # передача
    pickup_hours: Mapped[float] = mapped_column(Float, default=1.0)     # получение

    origin: Mapped[City] = relationship(foreign_keys=[origin_id])
    destination: Mapped[City] = relationship(foreign_keys=[destination_id])


# ---------- Заказы ----------

ORDER_STATUSES = ("draft", "estimated", "confirmed", "in_production", "at_risk", "done", "overdue", "cancelled")


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    customer: Mapped[str] = mapped_column(String(200), default="")
    deadline: Mapped[date] = mapped_column(Date)
    material: Mapped[str] = mapped_column(String(120), default="")
    weight_g: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(40), default="draft")
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    actual_cost: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Откуда стартует изделие физически (например, "у клиента" / город приёма)
    start_city_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cities.id"), nullable=True)

    stages: Mapped[List["Stage"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="Stage.order_index"
    )
    plans: Mapped[List["Plan"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    history: Mapped[List["OrderHistory"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderHistory.created_at"
    )
    start_city: Mapped[Optional[City]] = relationship()


class Stage(Base):
    """Конкретный этап в техпроцессе заказа."""
    __tablename__ = "stages"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    stage_template_id: Mapped[int] = mapped_column(ForeignKey("stage_templates.id"))
    order_index: Mapped[int] = mapped_column(Integer)  # порядок выполнения
    name: Mapped[str] = mapped_column(String(200))
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    actual_performer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("performers.id"), nullable=True)

    order: Mapped[Order] = relationship(back_populates="stages")
    template: Mapped[StageTemplate] = relationship()
    candidates: Mapped[List["StageCandidate"]] = relationship(
        back_populates="stage", cascade="all, delete-orphan"
    )


class StageCandidate(Base):
    """Возможный исполнитель для этапа конкретного заказа."""
    __tablename__ = "stage_candidates"
    __table_args__ = (UniqueConstraint("stage_id", "performer_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.id", ondelete="CASCADE"))
    performer_id: Mapped[int] = mapped_column(ForeignKey("performers.id"))

    stage: Mapped[Stage] = relationship(back_populates="candidates")
    performer: Mapped[Performer] = relationship()


# ---------- План ----------

class Plan(Base):
    """Снимок плана, полученный от оптимизатора."""
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    production_cost: Mapped[float] = mapped_column(Float, default=0.0)
    logistics_cost: Mapped[float] = mapped_column(Float, default=0.0)
    completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    feasible: Mapped[bool] = mapped_column(Boolean, default=True)
    explanation: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)  # текущий план заказа

    order: Mapped[Order] = relationship(back_populates="plans")
    plan_stages: Mapped[List["PlanStage"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan",
        order_by="PlanStage.start_at"
    )
    movements: Mapped[List["PlanMovement"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan",
        order_by="PlanMovement.start_at"
    )


class PlanStage(Base):
    __tablename__ = "plan_stages"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"))
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.id"))
    performer_id: Mapped[int] = mapped_column(ForeignKey("performers.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    cost: Mapped[float] = mapped_column(Float)

    plan: Mapped[Plan] = relationship(back_populates="plan_stages")
    stage: Mapped[Stage] = relationship()
    performer: Mapped[Performer] = relationship()


class PlanMovement(Base):
    __tablename__ = "plan_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"))
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"))
    from_stage_id: Mapped[Optional[int]] = mapped_column(ForeignKey("stages.id"), nullable=True)
    to_stage_id: Mapped[Optional[int]] = mapped_column(ForeignKey("stages.id"), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    cost: Mapped[float] = mapped_column(Float)
    courier_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    plan: Mapped[Plan] = relationship(back_populates="movements")
    route: Mapped[Route] = relationship()


# ---------- История ----------

class OrderHistory(Base):
    __tablename__ = "order_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    event_type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str] = mapped_column(Text, default="")

    order: Mapped[Order] = relationship(back_populates="history")
