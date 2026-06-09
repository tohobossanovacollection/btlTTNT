from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

BASE_DIR = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    APP_NAME: str = "Tax RAG Chatbot"
    DEBUG: bool = False
    RELOAD: bool = False
    GOOGLE_API_KEY: str = ""
    MODEL_NAME: str = "gemini-2.5-flash-lite"
    BACKEND_CORS_ORIGINS: str = "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:3000,http://localhost:3000"
    BACKEND_CORS_ALLOW_CREDENTIALS: bool = False
    LOG_LEVEL: str = "INFO"
    
    #LLM_MAX_OUTPUT_TOKENS: int = 700

    RAG_TOP_K: int = 6
    RAG_SCORE_THRESHOLD: float = 0.12
    RAG_CANDIDATE_MULTIPLIER: int = 8
    RAG_DISK_CACHE: bool = True
    RAG_WARMUP_ON_STARTUP: bool = True
    RAG_CACHE_DIR: str = "backend/cache"
    RAT_ENABLED: bool = True
    RAT_COMPLEXITY_THRESHOLD: int = 3
    RAT_MIN_QUESTION_LENGTH: int = 80
    RAT_MAX_STEPS: int = 4
    RAT_STEP_TOP_K: int = 3
    ROUTER_ENABLED: bool = True
    ROUTER_MAX_OUTPUT_TOKENS: int = 4

    SELF_RAG_ENABLED: bool = True
    SELF_RAG_RELEVANCE_THRESHOLD: float = 0.14
    SELF_RAG_SUPPORT_ENABLED: bool = True
    SELF_RAG_USEFULNESS_ENABLED: bool = True
    SELF_RAG_MAX_LOOPS: int = 2
    SELF_RAG_SUPPORT_MAX_RETRIES: int = 1

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

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

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
