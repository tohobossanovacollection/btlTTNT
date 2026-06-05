from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.sample_api import router as sample_router

app = FastAPI(
    title="Clean FastAPI Boilerplate",
    description="Hệ thống Backend đã được refactor, sẵn sàng phát triển RAG",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các Router
app.include_router(sample_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")