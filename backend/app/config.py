import os
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "Tax RAG Chatbot"
    DEBUG: bool = True
    GOOGLE_API_KEY: str = ""
    MODEL_NAME: str = "gemini-2.5-flash-lite"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, bool):
            return value

        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug", "dev", "development"}:
            return True
        if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
            return False
        return value

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
