from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/Moscow")
    reminder_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(8, 0))
    timezone_is_set: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    plants: Mapped[list["Plant"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    questions: Mapped[list["ExpertQuestion"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Plant(Base):
    __tablename__ = "plants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    watering_interval_days: Mapped[int] = mapped_column(Integer, nullable=False)
    last_watered_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_watering_on: Mapped[date] = mapped_column(Date, nullable=False)
    last_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    repeat_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    user: Mapped["UserProfile"] = relationship(back_populates="plants")


class ExpertQuestion(Base):
    __tablename__ = "expert_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"), nullable=False)
    parent_question_id: Mapped[int | None] = mapped_column(ForeignKey("expert_questions.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    photo_file_ids: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="sent")
    expert_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    patience_message_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["UserProfile"] = relationship(back_populates="questions")


class ActionLog(Base):
    __tablename__ = "action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("id", name="uq_action_logs_id"),
    )
