# from pydantic import field_validator
# from pydantic_settings import BaseSettings, SettingsConfigDict
# from functools import lru_cache

# class Settings(BaseSettings):
#     APP_NAME: str = "Tax RAG Chatbot"
#     DEBUG: bool = False
#     RELOAD: bool = False
#     GOOGLE_API_KEY: str = ""
#     MODEL_NAME: str = "gemini-2.5-flash-lite"
#     BACKEND_CORS_ORIGINS: str = "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:3000,http://localhost:3000"
#     BACKEND_CORS_ALLOW_CREDENTIALS: bool = False
#     LOG_LEVEL: str = "INFO"

#     RAG_TOP_K: int = 6
#     RAG_SCORE_THRESHOLD: float = 0.12
#     RAG_CANDIDATE_MULTIPLIER: int = 8
#     RAG_DISK_CACHE: bool = True
#     RAG_WARMUP_ON_STARTUP: bool = True
#     RAG_CACHE_DIR: str = "backend/cache"
#     RAT_ENABLED: bool = True
#     RAT_COMPLEXITY_THRESHOLD: int = 3
#     RAT_MIN_QUESTION_LENGTH: int = 80
#     RAT_MAX_STEPS: int = 4
#     RAT_STEP_TOP_K: int = 3
#     ROUTER_ENABLED: bool = True
#     ROUTER_MAX_OUTPUT_TOKENS: int = 4

#     SELF_RAG_ENABLED: bool = True
#     SELF_RAG_RELEVANCE_THRESHOLD: float = 0.14
#     SELF_RAG_SUPPORT_ENABLED: bool = True
#     SELF_RAG_USEFULNESS_ENABLED: bool = True
#     SELF_RAG_MAX_LOOPS: int = 2
#     SELF_RAG_SUPPORT_MAX_RETRIES: int = 1

#     model_config = SettingsConfigDict(env_file=".env", extra="ignore")

#     @field_validator("DEBUG", mode="before")
#     @classmethod
#     def parse_debug(cls, value):
#         if isinstance(value, bool):
#             return value

#         normalized = str(value).strip().lower()
#         if normalized in {"1", "true", "yes", "on", "debug", "dev", "development"}:
#             return True
#         if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
#             return False
#         return value

#     @property
#     def cors_origins(self) -> list[str]:
#         return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

# @lru_cache()
# def get_settings():
#     return Settings()

# settings = get_settings()


from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "Tax RAG Chatbot"
    DEBUG: bool = False
    RELOAD: bool = False
    LOG_LEVEL: str = "INFO"
    
    # --- API Keys ---
    GOOGLE_API_KEY: str = ""
    MODEL_NAME: str = "gemini-2.0-flash" # Đồng bộ với .env của bạn
    
    # 🔥 Bổ sung cấu hình Groq để Backend có thể sử dụng được
    GROQ_API_KEY: str = ""
    GROQ_MODEL_NAME: str = "llama3-70b-8192"

    # --- Server CORS ---
    BACKEND_CORS_ORIGINS: str = "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:3000,http://localhost:3000"
    BACKEND_CORS_ALLOW_CREDENTIALS: bool = False

    # --- RAG Basic ---
    RAG_TOP_K: int = 6
    RAG_SCORE_THRESHOLD: float = 0.12
    RAG_CANDIDATE_MULTIPLIER: int = 8
    RAG_DISK_CACHE: bool = True
    RAG_WARMUP_ON_STARTUP: bool = True
    RAG_CACHE_DIR: str = "backend/cache"
    
    # --- RAT Configuration (Suy nghĩ nhiều bước) ---
    RAT_ENABLED: bool = True
    RAT_COMPLEXITY_THRESHOLD: int = 3
    RAT_MIN_QUESTION_LENGTH: int = 80
    RAT_MAX_STEPS: int = 2          # 💡 Giảm từ 4 xuống 2 để bớt nghẽn API khi test
    RAT_STEP_TOP_K: int = 3
    
    # --- Router & Self RAG ---
    ROUTER_ENABLED: bool = True
    ROUTER_MAX_OUTPUT_TOKENS: int = 4
    SELF_RAG_ENABLED: bool = True
    SELF_RAG_RELEVANCE_THRESHOLD: float = 0.14
    SELF_RAG_SUPPORT_ENABLED: bool = True
    SELF_RAG_USEFULNESS_ENABLED: bool = True
    SELF_RAG_MAX_LOOPS: int = 1     # 💡 Giảm số vòng lặp sửa lỗi xuống 1 để tối ưu lượt gọi
    SELF_RAG_SUPPORT_MAX_RETRIES: int = 1

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 🔥 Áp dụng validator cho cả DEBUG và RELOAD để ép kiểu chuỗi từ .env chính xác
    @field_validator("DEBUG", "RELOAD", mode="before")
    @classmethod
    def parse_booleans(cls, value):
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