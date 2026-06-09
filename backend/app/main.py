import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.api.chat import router as chat_router
from app.services import retrieval_service
from app.utils.logging_setup import configure_logging
from app.utils.request_context import get_request_id, set_request_id

configure_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.RAG_WARMUP_ON_STARTUP:
        start = time.perf_counter()
        try:
            retrieval_service.warmup()
            logger.info("RAG warmup ok in %.0fms", (time.perf_counter() - start) * 1000.0)
        except Exception:
            logger.exception("RAG warmup failed")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Backend chatbot RAG tinh gọn, chỉ giữ cac endpoint can thiet.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.BACKEND_CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    set_request_id(request_id)

    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000.0
    logger.info("%s %s -> %.0fms", request.method, request.url.path, duration_ms)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{duration_ms:.0f}ms"
    return response


def _error_payload(*, message: str, code: str, request_id: str) -> dict:
    return {"error": {"message": message, "code": code, "request_id": request_id}}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = get_request_id()
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        payload = detail
        payload.setdefault("error", {}).setdefault("request_id", request_id)
    else:
        payload = _error_payload(message=str(detail), code="HTTP_ERROR", request_id=request_id)
    return JSONResponse(status_code=exc.status_code, content=payload, headers={"X-Request-ID": request_id})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = get_request_id()
    logger.warning("Validation error: %s", exc.errors())
    payload = _error_payload(
        message="Dữ liệu gửi lên không hợp lệ.",
        code="VALIDATION_ERROR",
        request_id=request_id,
    )
    if settings.DEBUG:
        payload["error"]["details"] = exc.errors()
    return JSONResponse(status_code=422, content=payload, headers={"X-Request-ID": request_id})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = get_request_id()
    logger.exception("Unhandled error")
    payload = _error_payload(
        message="Hệ thống tạm thời gặp sự cố nội bộ. Vui lòng thử lại.",
        code="INTERNAL_ERROR",
        request_id=request_id,
    )
    if settings.DEBUG:
        payload["error"]["details"] = str(exc)
    return JSONResponse(status_code=500, content=payload, headers={"X-Request-ID": request_id})

# Đăng ký các Router
app.include_router(chat_router, prefix="/api/v1")
