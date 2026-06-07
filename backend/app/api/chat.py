from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.retrieval_service import retrieve_laws_semantic
from app.services.gemini_service import ask_gemini

from typing import Optional
from app.services.user_service import save_chat_to_db, get_history_from_db
router = APIRouter(prefix="/chat", tags=["Chat"])

class ChatRequest(BaseModel):
    question: str
    user_id: Optional[int] = None    # Cho phép để trống
    session_id: Optional[int] = None # Cho phép để trống
class RatingRequest(BaseModel):
    user_id: int
    score: int
@router.post("/")
def chat(req: ChatRequest):
    try:
        # 1. Tìm kiếm luật
        laws = retrieve_laws_semantic(req.question, top_k = 5)

        # 2. Xử lý khi không thấy luật
        if not laws:
            answer = "Không tìm thấy căn cứ pháp lý phù hợp trong dữ liệu hiện có."
            
            return {"answer": answer, "sources": []}

        # 3. Hỏi Gemini
        answer = ask_gemini(req.question, laws)

        # 4. Lưu lịch sử
        chat_id = "sample-session-id" # Placeholder
        return {
            "answer": answer,
            "sources": [l['content'] for l in laws] if laws else [],
            "chat_id": chat_id
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Thêm endpoint này để app.js tải lại lịch sử
@router.get("/history/{user_id}")
def get_chat_history(user_id: int):
    return get_history_from_db(user_id)

class RateRequest(BaseModel):
    user_id: int
    score: int

@router.post("/rate")
def rate_chat(data: RateRequest):
    return {"message": "Rating feature is currently disabled (No DB)"}

@router.put("/rename")
def rename_chat(data: dict):
    return {"message": "Rename feature is currently disabled"}

@router.delete("/delete/{chat_id}")
def delete_chat(chat_id:int):
    return {"message": "Delete feature is currently disabled"}

@router.put("/pin")
def pin_chat(data:dict):
    return {"message": "Pin feature is currently disabled"}