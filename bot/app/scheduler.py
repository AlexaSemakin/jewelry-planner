import html
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import SessionLocal
from app.keyboards import reminder_keyboard
from app.models import ExpertQuestion, Plant, UserProfile
from app.safe_send import safe_send_message
from app.utils import format_date, user_now, user_today

logger = logging.getLogger(__name__)


async def check_watering_reminders(bot: Bot) -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Plant)
            .options(selectinload(Plant.user))
            .order_by(Plant.id.asc())
        )
        plants = list(result.scalars().all())

        for plant in plants:
            user = plant.user
            if not user:
                continue

            now_local = user_now(user.timezone)
            today = now_local.date()
            reminder_dt_local = now_local.replace(
                hour=user.reminder_time.hour,
                minute=user.reminder_time.minute,
                second=0,
                microsecond=0,
            )

            if plant.next_watering_on > today:
                continue

            first_not_sent = plant.last_reminder_sent_at is None
            reminder_time_has_come = now_local >= reminder_dt_local

            if first_not_sent and reminder_time_has_come:
                sent = await safe_send_message(
                    bot,
                    user.telegram_id,
                    f"🌱 Пора полить <b>{html.escape(plant.name)}</b>!",
                    reply_markup=reminder_keyboard(plant.id),
                )
                if sent:
                    plant.last_reminder_sent_at = datetime.utcnow()
                    await session.commit()
                continue

            if (
                plant.last_reminder_sent_at is not None
                and plant.repeat_reminder_sent_at is None
                and datetime.utcnow() - plant.last_reminder_sent_at >= timedelta(hours=24)
                and plant.next_watering_on < today
            ):
                sent = await safe_send_message(
                    bot,
                    user.telegram_id,
                    f"Привет! Кажется, <b>{html.escape(plant.name)}</b> всё ещё ждёт полива 🌿",
                    reply_markup=reminder_keyboard(plant.id),
                )
                if sent:
                    plant.repeat_reminder_sent_at = datetime.utcnow()
                    await session.commit()


async def check_expert_patience_messages(bot: Bot) -> None:
    async with SessionLocal() as session:
        threshold = datetime.utcnow() - timedelta(hours=24)
        result = await session.execute(
            select(ExpertQuestion)
            .where(ExpertQuestion.status == "sent")
            .where(ExpertQuestion.patience_message_sent == False)  # noqa: E712
            .where(ExpertQuestion.created_at <= threshold)
            .options(selectinload(ExpertQuestion.user))
        )
        questions = list(result.scalars().all())

        for question in questions:
            if not question.user:
                continue
            sent = await safe_send_message(
                bot,
                question.user.telegram_id,
                "Спасибо за терпение! Эксперт скоро ответит на ваш вопрос 🌿",
            )
            if sent:
                question.patience_message_sent = True
                await session.commit()


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(check_watering_reminders, "interval", minutes=1, args=[bot], id="watering_reminders")
    scheduler.add_job(check_expert_patience_messages, "interval", minutes=10, args=[bot], id="expert_patience")
    scheduler.start()
    return scheduler
