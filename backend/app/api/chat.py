from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.retrieval_service import retrieve_laws_semantic
from app.services.gemini_service import ask_gemini
from typing import Optional
from app.services.user_service import save_chat_to_db, get_history_from_db

router = APIRouter(prefix="/chat", tags=["Chat"])

class ChatRequest(BaseModel):
    question: str
    user_id: Optional[int] = None
    session_id: Optional[str] = None # Linh hoạt chuỗi hoặc số

@router.post("/")
def chat(req: ChatRequest):
    try:
        # Khởi tạo các giá trị mặc định để trả về và lưu DB
        answer = ""
        laws = []
        chat_id = req.session_id if req.session_id else "generated-session-id"

        # --- ĐẦU VIỆC 1: QUẢN LÝ LỊCH SỬ CHAT (CHAT HISTORY) ---
        history_context = ""
        if req.user_id:
            old_chats = get_history_from_db(req.user_id)
            # Gộp tối đa 4 câu gần nhất làm ngữ cảnh cho Gemini
            for c in old_chats[-4:]:
                history_context += f"{c.get('role')}: {c.get('text')}\n"

        # --- ĐẦU VIỆC 2: ROUTER PHÂN LOẠI CÂU HỎI (Ý TƯỞNG SKILL-RAG) ---
        casual_words = ["chào", "hello", "hi", "tạm biệt", "bạn là ai", "thời tiết"]
        is_casual = any(word in req.question.lower() for word in casual_words) and len(req.question.split()) < 5

        if is_casual:
            # Kỹ năng 1: Chat xã giao (Không cần RAG)
            prompt_casual = f"Người dùng chào: '{req.question}'. Hãy phản hồi ngắn gọn, thân thiện với vai trò trợ lý pháp luật Thuế."
            answer = ask_gemini(prompt_casual, laws=[])
        
        else:
            # --- ĐẦU VIỆC 3: RAG TIÊU CHUẨN KÈM ĐÁNH GIÁ ĐIỂM SỐ TIN CẬY ---
            laws = retrieve_laws_semantic(req.question, top_k=3, threshold=0.35)

            if not laws:
                # Kỹ năng 2: Xử lý trạng thái lỗi (Fallback khi điểm quá thấp)
                answer = (
                    "Hệ thống chưa tìm thấy điều luật hoặc nghị định nào trong cơ sở dữ liệu "
                    "trực tiếp khớp với tình huống thuế bạn vừa nêu. Bạn có thể cung cấp thêm từ khóa cụ thể "
                    "hoặc số hiệu văn bản (nếu có) được không?"
                )
            else:
                # Kỹ năng 3: Trả lời dựa trên luật pháp chính xác
                full_query = f"Ngữ cảnh hội thoại cũ:\n{history_context}\nCâu hỏi hiện tại: {req.question}"
                answer = ask_gemini(full_query, laws)

        # --- ĐẦU VIỆC 4: LƯU LỊCH SỬ THỰC TẾ (Luôn chạy bất kể nhánh nào) ---
        if req.user_id:
            # Lưu câu hỏi của người dùng
            save_chat_to_db(user_id=req.user_id, role="user", text=req.question, session_id=chat_id)
            # Lưu câu trả lời của Gemini / Hệ thống
            save_chat_to_db(user_id=req.user_id, role="model", text=answer, session_id=chat_id)

        # Trả kết quả về cho Frontend
        return {
            "answer": answer,
            "sources": [f"{l['law_name']} - {l['article']}: {l['title']}" for l in laws] if laws else [],
            "highest_score": laws[0]["score"] if laws else 0.0,
            "chat_id": chat_id
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{user_id}")
def get_chat_history(user_id: int):
    return get_history_from_db(user_id)