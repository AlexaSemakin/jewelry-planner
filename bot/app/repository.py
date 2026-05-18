from datetime import date, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ActionLog, ExpertQuestion, Plant, UserProfile
from app.utils import user_today


async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None) -> UserProfile:
    result = await session.execute(select(UserProfile).where(UserProfile.telegram_id == telegram_id))
    user = result.scalars().first()
    if user:
        user.username = username
        await session.commit()
        return user

    user = UserProfile(telegram_id=telegram_id, username=username)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def log_action(session: AsyncSession, telegram_id: int | None, action: str, details: str = "") -> None:
    session.add(ActionLog(telegram_id=telegram_id, action=action, details=details))
    await session.commit()


async def count_user_plants(session: AsyncSession, user_id: int) -> int:
    return int(await session.scalar(select(func.count(Plant.id)).where(Plant.user_id == user_id)) or 0)


async def get_user_plants(session: AsyncSession, user_id: int) -> list[Plant]:
    result = await session.execute(select(Plant).where(Plant.user_id == user_id).order_by(Plant.id.asc()))
    return list(result.scalars().all())


async def get_plant_for_telegram_user(session: AsyncSession, plant_id: int, telegram_id: int) -> tuple[Plant, UserProfile] | None:
    result = await session.execute(
        select(Plant)
        .join(UserProfile, Plant.user_id == UserProfile.id)
        .where(Plant.id == plant_id)
        .where(UserProfile.telegram_id == telegram_id)
        .options(selectinload(Plant.user))
    )
    plant = result.scalars().first()
    if not plant:
        return None
    return plant, plant.user


async def mark_watered(session: AsyncSession, plant: Plant, user: UserProfile) -> date:
    today = user_today(user.timezone)
    plant.last_watered_on = today
    plant.next_watering_on = today + timedelta(days=plant.watering_interval_days)
    plant.last_reminder_sent_at = None
    plant.repeat_reminder_sent_at = None
    plant.updated_at = datetime.utcnow()
    await session.commit()
    return plant.next_watering_on


async def snooze_plant(session: AsyncSession, plant: Plant, user: UserProfile, days: int) -> date:
    today = user_today(user.timezone)
    plant.next_watering_on = today + timedelta(days=days)
    plant.last_reminder_sent_at = None
    plant.repeat_reminder_sent_at = None
    plant.updated_at = datetime.utcnow()
    await session.commit()
    return plant.next_watering_on


async def delete_user_data(session: AsyncSession, telegram_id: int) -> None:
    user_result = await session.execute(select(UserProfile).where(UserProfile.telegram_id == telegram_id))
    user = user_result.scalars().first()
    if not user:
        return

    await session.execute(delete(Plant).where(Plant.user_id == user.id))
    await session.execute(delete(ExpertQuestion).where(ExpertQuestion.user_id == user.id))
    await session.delete(user)
    await session.commit()
