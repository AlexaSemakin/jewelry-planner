from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://jewelry:jewelry@db:5432/jewelry"
    SEED_ON_START: bool = True
    COURIERS_TOTAL: int = 3
    # Лимит времени работы оптимизатора (сек.)
    OPT_TIME_LIMIT_SEC: int = 20
    # Шаг планирования в минутах (минимальная единица времени для CP-SAT)
    TIME_STEP_MIN: int = 30
    # Горизонт планирования в днях (от "сегодня")
    PLANNING_HORIZON_DAYS: int = 180


settings = Settings()
