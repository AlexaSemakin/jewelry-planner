from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)


class Executor(Base):
    __tablename__ = "executors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"), nullable=False)
    specialization: Mapped[str] = mapped_column(String(120), nullable=False)
    cost_per_day: Mapped[float] = mapped_column(Float, nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    working_days: Mapped[list[int]] = mapped_column(JSON, default=lambda: [0, 1, 2, 3, 4])
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    city: Mapped[City] = relationship()


class TransportRoute(Base):
    __tablename__ = "transport_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"), nullable=False)
    to_city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"), nullable=False)
    method: Mapped[str] = mapped_column(String(80), nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    handoff_days: Mapped[int] = mapped_column(Integer, default=1)

    from_city: Mapped[City] = relationship(foreign_keys=[from_city_id])
    to_city: Mapped[City] = relationship(foreign_keys=[to_city_id])


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    materials: Mapped[str] = mapped_column(Text, default="")
    weight_grams: Mapped[float] = mapped_column(Float, default=0)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="estimate")
    current_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    total_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    planned_finish_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    plan_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    stages: Mapped[list[OrderStage]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStage.position",
    )


class OrderStage(Base):
    __tablename__ = "order_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="planned")

    order: Mapped[Order] = relationship(back_populates="stages")


class OrderHistory(Base):
    __tablename__ = "order_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
