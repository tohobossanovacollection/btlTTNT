import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "Ứng dụng kỹ thuật RAG xây dựng Chatbot tra cứu văn bản pháp luật Thuế Việt Nam"
    DEBUG: bool = True
    GOOGLE_API_KEY: str = ""
    MODEL_NAME: str = "gemini-1.5-flash"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()