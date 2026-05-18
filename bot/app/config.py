from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str = "sqlite+aiosqlite:///./plantcare.db"
    expert_chat_id: int | None = None
    proxy_url: str | None = None
    log_file: str = "plantcare.log"

    @field_validator("expert_chat_id", mode="before")
    @classmethod
    def empty_expert_chat_id_to_none(cls, value):
        if value == "" or value is None:
            return None
        return value

    @field_validator("proxy_url", mode="before")
    @classmethod
    def empty_proxy_url_to_none(cls, value):
        if value == "" or value is None:
            return None
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
