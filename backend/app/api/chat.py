# import logging

# from fastapi import APIRouter, HTTPException
# from pydantic import BaseModel, Field

# from app.config import settings
# from app.services.chat_orchestrator import handle_chat
# from app.services.gemini_service import GeminiError
# from app.utils.request_context import get_request_id

# router = APIRouter(prefix="/chat", tags=["Chat"])
# logger = logging.getLogger(__name__)


# class ChatRequest(BaseModel):
#     question: str = Field(..., min_length=3, description="Cau hoi cua nguoi dung")


# class ScoreBreakdown(BaseModel):
#     semantic_score: float | None = None
#     keyword_score: float | None = None
#     final_score: float | None = None


# class ChatSource(BaseModel):
#     source: str | None = None
#     law_name: str | None = None
#     article: str | None = None
#     title: str | None = None
#     excerpt: str | None = None
#     score: ScoreBreakdown | None = None
#     matched_steps: list[str] = Field(default_factory=list)


# class ChatResponse(BaseModel):
#     answer: str
#     sources: list[ChatSource]
#     meta: dict


# @router.post("/")
# def chat(req: ChatRequest) -> ChatResponse:
#     try:
#         request_id = get_request_id()
#         question = req.question.strip()
#         result = handle_chat(question, request_id=request_id)
#         return ChatResponse.model_validate(result)

#     except HTTPException:
#         raise
#     except GeminiError as exc:
#         logger.warning("Gemini error: %s", str(exc))
#         raise HTTPException(
#             status_code=503,
#             detail={"error": {"message": str(exc), "code": exc.code}},
#         )
#     except Exception as exc:
#         logger.exception("Chat API gap loi trong qua trinh xu ly cau hoi.")
#         detail = str(exc) if settings.DEBUG else "He thong tam thoi gap su co khi xu ly cau hoi. Vui long thu lai."
#         raise HTTPException(
#             status_code=500,
#             detail=detail,
#         )


import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.services.chat_orchestrator import handle_chat
# CHUYỂN ĐỔI: Import GroqError để bắt đúng ngoại lệ từ Groq API
from groq import GroqError
from app.utils.request_context import get_request_id

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, description="Cau hoi cua nguoi dung")


class ScoreBreakdown(BaseModel):
    semantic_score: float | None = None
    keyword_score: float | None = None
    final_score: float | None = None


class ChatSource(BaseModel):
    source: str | None = None
    law_name: str | None = None
    article: str | None = None
    title: str | None = None
    excerpt: str | None = None
    score: ScoreBreakdown | None = None
    matched_steps: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    meta: dict


@router.post("/")
def chat(req: ChatRequest) -> ChatResponse:
    try:
        request_id = get_request_id()
        question = req.question.strip()
        result = handle_chat(question, request_id=request_id)
        return ChatResponse.model_validate(result)

    except HTTPException:
        raise
    # CHUYỂN ĐỔI: Xử lý lỗi đặc thù phát sinh từ phía Groq
    except GroqError as exc:
        logger.warning("Groq error: %s", str(exc))
        
        # GroqError thường có thuộc tính status_code từ API response (ví dụ: 401, 429, 503,...)
        # Nếu không có, mặc định trả về lỗi hệ thống tích hợp bên thứ ba (503 Service Unavailable)
        status_code = getattr(exc, "status_code", 503)
        
        raise HTTPException(
            status_code=status_code,
            detail={
                "error": {
                    "message": str(exc),
                    "type": getattr(exc, "type", "groq_api_error")
                }
            },
        )
    except Exception as exc:
        logger.exception("Chat API gap loi trong qua trinh xu ly cau hoi.")
        detail = str(exc) if settings.DEBUG else "He thong tam thoi gap su co khi xu ly cau hoi. Vui long thu lai."
        raise HTTPException(
            status_code=500,
            detail=detail,
        )