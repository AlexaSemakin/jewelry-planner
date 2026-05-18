from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import City, Executor, TransportRoute


async def seed_demo_data(session: AsyncSession) -> None:
    existing_cities = await session.scalar(select(func.count(City.id)))
    if existing_cities:
        return

    cities = {
        "Пермь": City(name="Пермь"),
        "Екатеринбург": City(name="Екатеринбург"),
        "Киров": City(name="Киров"),
        "Москва": City(name="Москва"),
    }
    session.add_all(cities.values())
    await session.flush()

    executors = [
        Executor(name="Мастерская основы Пермь", city=cities["Пермь"], specialization="основа", cost_per_day=6000, duration_days=3),
        Executor(name="Камнерез Екатеринбург", city=cities["Екатеринбург"], specialization="камни", cost_per_day=7500, duration_days=2),
        Executor(name="Закрепщик Екатеринбург", city=cities["Екатеринбург"], specialization="закрепка", cost_per_day=8500, duration_days=2),
        Executor(name="Гравёр Киров", city=cities["Киров"], specialization="гравировка", cost_per_day=5000, duration_days=1),
        Executor(name="Полировка Москва", city=cities["Москва"], specialization="полировка", cost_per_day=6500, duration_days=1),
        Executor(name="Универсальная мастерская Москва", city=cities["Москва"], specialization="универсальный", cost_per_day=11000, duration_days=2),
    ]
    session.add_all(executors)
    await session.flush()

    routes = []
    city_list = list(cities.values())
    for from_city in city_list:
        for to_city in city_list:
            if from_city.id == to_city.id:
                continue
            routes.append(
                TransportRoute(
                    from_city_id=from_city.id,
                    to_city_id=to_city.id,
                    method="тестовый транспорт",
                    cost=2500 + abs(from_city.id - to_city.id) * 900,
                    duration_days=1 + (abs(from_city.id - to_city.id) % 2),
                    handoff_days=1,
                )
            )
    session.add_all(routes)
    await session.commit()
