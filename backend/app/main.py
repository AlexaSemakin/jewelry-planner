"""
Точка входа приложения.

На старте: создаём таблицы (если их нет), при SEED_ON_START=true — заливаем демо-данные.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import time
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.db.session import Base, engine, SessionLocal
from app.api.catalog import router as catalog_router
from app.api.orders import router as orders_router
# Гарантируем регистрацию моделей перед create_all
from app.models import models  # noqa: F401
from app.seed.seed import seed_if_empty


app = FastAPI(
    title="Jewelry Production Planner",
    version="1.0.0",
    description="Планирование производства авторских ювелирных изделий с оптимизацией.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog_router, prefix="/api", tags=["catalog"])
app.include_router(orders_router, prefix="/api", tags=["orders"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/settings")
def get_settings():
    return {
        "couriers_total": settings.COURIERS_TOTAL,
        "time_step_min": settings.TIME_STEP_MIN,
        "planning_horizon_days": settings.PLANNING_HORIZON_DAYS,
        "opt_time_limit_sec": settings.OPT_TIME_LIMIT_SEC,
    }


@app.on_event("startup")
def on_startup() -> None:
    # Ждём пока БД будет готова (на случай docker-compose race)
    for attempt in range(40):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            break
        except OperationalError:
            time.sleep(1)
    Base.metadata.create_all(bind=engine)
    if settings.SEED_ON_START:
        with SessionLocal() as db:
            seed_if_empty(db)
