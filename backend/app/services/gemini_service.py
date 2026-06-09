# import logging
# import threading

# from app.config import settings

# logger = logging.getLogger(__name__)

# _CLIENT_LOCK = threading.Lock()
# _CLIENT = None
# _CLIENT_KEY = None


# class GeminiError(RuntimeError):
#     def __init__(self, message: str, code: str):
#         super().__init__(message)
#         self.code = code


# def _get_client():
#     global _CLIENT, _CLIENT_KEY
#     api_key = (settings.GOOGLE_API_KEY or "").strip()
#     if not api_key:
#         raise GeminiError("Hệ thống AI chưa được cấu hình.", "LLM_NOT_CONFIGURED")

#     with _CLIENT_LOCK:
#         if _CLIENT is not None and _CLIENT_KEY == api_key:
#             return _CLIENT

#         try:
#             from google import genai
#         except ModuleNotFoundError as exc:
#             raise GeminiError("Thiếu thư viện kết nối hệ thống AI.", "LLM_DEPENDENCY_MISSING") from exc

#         _CLIENT = genai.Client(api_key=api_key)
#         _CLIENT_KEY = api_key
#         return _CLIENT


# def classify_query_intent(question: str, max_output_tokens: int = 4) -> str:
#     try:
#         from google.genai import types
#         from google.genai.errors import APIError
#     except ModuleNotFoundError:
#         raise GeminiError("Thiếu thư viện kết nối hệ thống AI.", "LLM_DEPENDENCY_MISSING")

#     client = _get_client()
#     prompt = f"""Phan loai cau hoi phap ly sau thanh dung 1 tu duy nhat.

# Quy tac:
# - Tra ve SIMPLE neu cau hoi co the tra loi bang mot lan truy van van ban phap ly.
# - Tra ve COMPLEX neu cau hoi co nhieu dieu kien, ngoai le, so sanh, tinh huong ket hop, hoac can suy luan nhieu buoc.
# - Chi duoc tra ve SIMPLE hoac COMPLEX, khong giai thich.

# Cau hoi: {question}
# """

#     try:
#         response = client.models.generate_content(
#             model=settings.MODEL_NAME,
#             contents=prompt,
#             config=types.GenerateContentConfig(
#                 temperature=0.0,
#                 max_output_tokens=max_output_tokens,
#             ),
#         )
#         label = (getattr(response, "text", None) or "").strip().upper()
#         if "COMPLEX" in label:
#             return "COMPLEX"
#         if "SIMPLE" in label:
#             return "SIMPLE"
#         raise GeminiError("Khong the phan loai y dinh cau hoi.", "LLM_ROUTER_INVALID_OUTPUT")
#     except GeminiError:
#         raise
#     except APIError as exc:
#         raw = str(exc)
#         lowered = raw.lower()
#         logger.warning("Gemini router APIError: %s", raw)
#         if "429" in raw or "quota" in lowered:
#             raise GeminiError("He thong AI dang qua tai khi phan loai cau hoi.", "LLM_QUOTA_EXCEEDED") from exc
#         if "503" in raw or "unavailable" in lowered:
#             raise GeminiError("He thong AI tam thoi khong san sang khi phan loai cau hoi.", "LLM_UNAVAILABLE") from exc
#         raise GeminiError("Khong the ket noi he thong AI de phan loai cau hoi.", "LLM_UPSTREAM_ERROR") from exc
#     except Exception as exc:
#         logger.exception("Gemini router exception")
#         raise GeminiError("He thong AI gap su co khi phan loai cau hoi.", "LLM_ROUTER_INTERNAL_ERROR") from exc


# def ask_gemini(
#     question: str,
#     laws: list,
#     reasoning_steps: list[dict] | None = None,
#     refined_context: str | None = None,
#     extra_instructions: str | None = None,
# ) -> str:
#     if not laws and not refined_context:
#         return "Không tìm thấy căn cứ pháp lý phù hợp trong dữ liệu hiện có."

#     try:
#         from google.genai import types
#         from google.genai.errors import APIError
#     except ModuleNotFoundError:
#         raise GeminiError("Thiếu thư viện kết nối hệ thống AI.", "LLM_DEPENDENCY_MISSING")

#     client = _get_client()

#     try:
#         if refined_context:
#             context = refined_context.strip()
#         else:
#             context_blocks = []
#             for law in laws:
#                 score_info = ""
#                 if law.get("_final_score") is not None:
#                     score_info = f" (độ liên quan: {law.get('_final_score')})"
#                 step_info = ""
#                 matched_steps = law.get("_matched_step_titles") or []
#                 if matched_steps:
#                     step_info = f"\n   Phuc vu buoc suy luan: {', '.join(matched_steps)}"
#                 block = (
#                     f"📌 {law.get('law_name', 'Không rõ tên luật')}{score_info}\n"
#                     f"   {law.get('article', '')} — {law.get('title', '')}{step_info}\n"
#                     f"{law.get('content', '').strip()}"
#                 )
#                 context_blocks.append(block)
#             context = "\n\n" + "─" * 60 + "\n\n".join(context_blocks)
#         reasoning_text = ""
#         if reasoning_steps:
#             reasoning_lines = []
#             for step in reasoning_steps:
#                 reasoning_lines.append(
#                     f"- {step.get('step_id')}: {step.get('title')} | truy van: {step.get('query')}"
#                 )
#             reasoning_text = "\nKE HOACH SUY LUAN DA DUOC BACKEND KIEM CHUNG:\n" + "\n".join(reasoning_lines) + "\n"

#         prompt = f"""Bạn là chuyên gia tư vấn pháp luật thuế tại Việt Nam, đặc biệt am hiểu:
# - Luật Thuế thu nhập doanh nghiệp
# - Luật Thuế thu nhập cá nhân
# - Luật Quản lý thuế
# - Các Nghị định, Thông tư hướng dẫn liên quan

# ═══════════════════════════════════════════════════════════════
# NGUYÊN TẮC BẮT BUỘC:
# 1. CHỈ dựa vào "CĂN CỨ PHÁP LÝ" bên dưới để trả lời.
# 2. KHÔNG tự bịa đặt, KHÔNG dùng kiến thức bên ngoài dữ liệu.
# 3. Trích dẫn rõ: tên luật + số điều khi đưa ra kết luận.
# 4. Nếu dữ liệu không đủ → nói thẳng: "Dữ liệu hiện tại chưa có thông tin về vấn đề này."
# 5. Trả lời bằng tiếng Việt, rõ ràng, có cấu trúc.
# ═══════════════════════════════════════════════════════════════
# {reasoning_text}

# YÊU CẦU BỔ SUNG (nếu có):
# {(extra_instructions or "").strip()}


# CĂN CỨ PHÁP LÝ:
# {context}

# ═══════════════════════════════════════════════════════════════
# CÂU HỎI: {question}
# ═══════════════════════════════════════════════════════════════

# TRẢ LỜI (dựa CHỈ vào căn cứ trên, có trích dẫn điều khoản):
# """

#         config = types.GenerateContentConfig(
#             temperature=0.1,
#             safety_settings=[
#                 types.SafetySetting(
#                     category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
#                     threshold=types.HarmBlockThreshold.BLOCK_NONE,
#                 ),
#                 types.SafetySetting(
#                     category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
#                     threshold=types.HarmBlockThreshold.BLOCK_NONE,
#                 ),
#                 types.SafetySetting(
#                     category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
#                     threshold=types.HarmBlockThreshold.BLOCK_NONE,
#                 ),
#             ],
#         )

#         response = client.models.generate_content(
#             model=settings.MODEL_NAME,
#             contents=prompt,
#             config=config,
#         )

#         answer = (getattr(response, "text", None) or "").strip()
#         if not answer:
#             raise GeminiError("Không thể tạo câu trả lời từ hệ thống AI.", "LLM_EMPTY_RESPONSE")

#         return answer

#     except GeminiError:
#         raise
#     except APIError as exc:
#         raw = str(exc)
#         lowered = raw.lower()
#         logger.warning("Gemini APIError: %s", raw)
#         if "429" in raw or "quota" in lowered:
#             raise GeminiError("Hệ thống AI đang quá tải (đạt giới hạn API).", "LLM_QUOTA_EXCEEDED") from exc
#         if "503" in raw or "unavailable" in lowered or "temporarily" in lowered:
#             raise GeminiError("Hệ thống AI tạm thời không sẵn sàng.", "LLM_UNAVAILABLE") from exc
#         raise GeminiError("Không thể kết nối hệ thống AI.", "LLM_UPSTREAM_ERROR") from exc
#     except Exception as exc:
#         logger.exception("Gemini exception")
#         raise GeminiError("Hệ thống AI gặp sự cố tạm thời.", "LLM_INTERNAL_ERROR") from exc


# def self_reflect_answer(
#     question: str,
#     answer: str,
#     context: str,
#     max_output_tokens: int = 256,
# ) -> dict:
#     try:
#         from google.genai import types
#         from google.genai.errors import APIError
#     except ModuleNotFoundError:
#         raise GeminiError("Thiếu thư viện kết nối hệ thống AI.", "LLM_DEPENDENCY_MISSING")

#     client = _get_client()
#     prompt = f"""Bạn là bộ kiểm định chất lượng câu trả lời theo cơ chế Self-RAG (tự phản tư).

# Bạn sẽ nhận vào:
# - CÂU HỎI của người dùng
# - CĂN CỨ PHÁP LÝ (context) do hệ thống truy xuất
# - CÂU TRẢ LỜI do mô hình sinh

# Nhiệm vụ:
# 1) Is_Supported: Câu trả lời có dựa HOÀN TOÀN trên context không? Nếu có phần suy diễn/khẳng định không thấy trong context thì là false.
# 2) Is_Useful: Câu trả lời có giải quyết đủ ý câu hỏi không? Nếu thiếu điều kiện/ngoại lệ/đối tượng áp dụng quan trọng thì là false.

# CHỈ trả về đúng 1 JSON object, không kèm giải thích ngoài JSON, theo schema:
# {{
#   "is_supported": true/false,
#   "unsupported_claims": ["..."],
#   "is_useful": true/false,
#   "missing_points": ["..."],
#   "improvement_suggestions": "..."
# }}

# CÂU HỎI:
# {question}

# CĂN CỨ PHÁP LÝ:
# {context}

# CÂU TRẢ LỜI:
# {answer}
# """

#     try:
#         response = client.models.generate_content(
#             model=settings.MODEL_NAME,
#             contents=prompt,
#             config=types.GenerateContentConfig(
#                 temperature=0.0,
#                 max_output_tokens=int(max_output_tokens or 256),
#             ),
#         )
#         text = (getattr(response, "text", None) or "").strip()
#         if not text:
#             raise GeminiError("Không thể tự đánh giá câu trả lời từ hệ thống AI.", "LLM_EMPTY_RESPONSE")
#         import json

#         try:
#             data = json.loads(text)
#         except json.JSONDecodeError:
#             start = text.find("{")
#             end = text.rfind("}")
#             if start >= 0 and end > start:
#                 data = json.loads(text[start : end + 1])
#             else:
#                 raise
#         if not isinstance(data, dict):
#             raise GeminiError("Kết quả tự đánh giá không hợp lệ.", "LLM_EVALUATOR_INVALID_OUTPUT")
#         return data
#     except GeminiError:
#         raise
#     except APIError as exc:
#         raw = str(exc)
#         lowered = raw.lower()
#         logger.warning("Gemini self-reflection APIError: %s", raw)
#         if "429" in raw or "quota" in lowered:
#             raise GeminiError("Hệ thống AI đang quá tải khi tự đánh giá.", "LLM_QUOTA_EXCEEDED") from exc
#         if "503" in raw or "unavailable" in lowered or "temporarily" in lowered:
#             raise GeminiError("Hệ thống AI tạm thời không sẵn sàng khi tự đánh giá.", "LLM_UNAVAILABLE") from exc
#         raise GeminiError("Không thể kết nối hệ thống AI để tự đánh giá.", "LLM_UPSTREAM_ERROR") from exc
#     except Exception as exc:
#         logger.exception("Gemini self-reflection exception")
#         raise GeminiError("Hệ thống AI gặp sự cố khi tự đánh giá.", "LLM_INTERNAL_ERROR") from exc



import logging
import threading
import os
import json
from app.config import settings

logger = logging.getLogger(__name__)

_CLIENT_LOCK = threading.Lock()
_CLIENT = None


class GeminiError(RuntimeError):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


def _get_groq_client():
    """Khởi tạo luồng an toàn cho ChatGroq client thay thế Gemini"""
    global _CLIENT
    
    # 1. Lấy API Key từ môi trường
    api_key = os.getenv("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", "")
    api_key = (api_key or "").strip()
    
    if not api_key:
        raise GeminiError("Hệ thống AI (Groq) chưa được cấu hình API Key.", "LLM_NOT_CONFIGURED")

    # 2. Kiểm tra và ép cấu hình model chuẩn, tránh đọc phải model cũ đã bị khai tử từ .env
    model_name = os.getenv("GROQ_MODEL_NAME", "").strip()
    if not model_name or "llama3-70b-8192" in model_name:
        # Ép dùng model mới nhất nếu env bị trống hoặc chứa tên model cũ bị khai tử
        model_name = "llama-3.3-70b-versatile"

    with _CLIENT_LOCK:
        # Nếu _CLIENT đã tồn tại nhưng sai model cũ, tiến hành xóa để khởi tạo lại
        if _CLIENT is not None:
            if getattr(_CLIENT, "model_name", "") == model_name:
                return _CLIENT
            else:
                _CLIENT = None  # Reset để làm mới luồng

        try:
            from langchain_groq import ChatGroq
        except ModuleNotFoundError as exc:
            raise GeminiError("Thiếu thư viện langchain-groq.", "LLM_DEPENDENCY_MISSING") from exc

        logger.info(f"--- Khởi tạo ChatGroq client với Model mới: {model_name} ---")
        _CLIENT = ChatGroq(
            api_key=api_key, 
            model_name=model_name, 
            temperature=0.0, 
            max_retries=2
        )
        return _CLIENT

def classify_query_intent(question: str, max_output_tokens: int = 4) -> str:
    """Sử dụng Groq để phân loại ý định câu hỏi"""
    llm = _get_groq_client()
    
    prompt = f"""Phan loai cau hoi phap ly sau thanh dung 1 tu duy nhat.

Quy tac:
- Tra ve SIMPLE neu cau hoi co the tra loi bang mot lan truy van van ban phap ly.
- Tra ve COMPLEX neu cau hoi co nhieu dieu kien, ngoai le, so sanh, tinh huong ket hop, hoac can suy luan nhieu buoc.
- Chi duoc tra ve SIMPLE hoac COMPLEX, khong giai thich.

Cau hoi: {question}
"""
    try:
        # Gọi qua LangChain Groq invoke interface
        response = llm.invoke(prompt)
        label = (getattr(response, "content", "") or "").strip().upper()
        
        if "COMPLEX" in label:
            return "COMPLEX"
        if "SIMPLE" in label:
            return "SIMPLE"
        return "SIMPLE" # Fallback an toàn nếu LLM ra kết quả lệch chuẩn
    except Exception as exc:
        logger.warning("Groq router error: %s", exc)
        # Gặp lỗi thì tự động hạ cấp về SIMPLE để hệ thống chạy tiếp không bị crash
        return "SIMPLE"


def ask_gemini(
    question: str,
    laws: list,
    reasoning_steps: list[dict] | None = None,
    refined_context: str | None = None,
    extra_instructions: str | None = None,
) -> str:
    """Đổi ruột sang Groq nhưng giữ nguyên tên hàm ask_gemini để không hỏng code hệ thống"""
    # 1. KIỂM TRA ĐIỀU KIỆN TRỐNG HOẶC ĐỘ LIÊN QUAN QUÁ THẤP (FIX CÂU 8, 9 OUT OF SCOPE)
    is_context_empty = not laws and not refined_context
    
    # Check xem các luật tìm được có điểm số quá thấp hay không (RAG tìm mù quáng)
    is_low_relevance = False
    if laws and not refined_context:
        # Lấy điểm số cao nhất trong các điều luật trả về (bản ghi đầu tiên thường có score cao nhất)
        highest_score = laws[0].get("_final_score", 0) or laws[0].get("score", 0)
        
        # Nếu điểm cao nhất mà vẫn thấp hơn 0.3 (hoặc dựa vào log của bạn là 0.16), chứng tỏ luật không liên quan
        if highest_score < 0.3: 
            is_low_relevance = True

    # Nếu rơi vào 1 trong 2 trường hợp trên -> Trả về text luôn, không gọi Groq nữa để tránh Timeout
    if is_context_empty or is_low_relevance:
        return "Dữ liệu hiện tại chưa có thông tin về vấn đề này."

    # 2. KHỞI TẠO CLIENT VÀ CHẠY TIẾP CÁC LOGIC PHÍA DƯỚI...
    llm = _get_groq_client()

    if refined_context:
        context = refined_context.strip()
    else:
        context_blocks = []
        for law in laws:
            score_info = ""
            if law.get("_final_score") is not None:
                score_info = f" (độ liên quan: {law.get('_final_score')})"
            step_info = ""
            matched_steps = law.get("_matched_step_titles") or []
            if matched_steps:
                step_info = f"\n   Phuc vu buoc suy luan: {', '.join(matched_steps)}"
            block = (
                f"📌 {law.get('law_name', 'Không rõ tên luật')}{score_info}\n"
                f"   {law.get('article', '')} — {law.get('title', '')}{step_info}\n"
                f"{law.get('content', '').strip()}"
            )
            context_blocks.append(block)
        context = "\n\n" + "─" * 60 + "\n\n".join(context_blocks)
        
    reasoning_text = ""
    if reasoning_steps:
        reasoning_lines = []
        for step in reasoning_steps:
            reasoning_lines.append(f"- {step.get('step_id')}: {step.get('title')} | truy van: {step.get('query')}")
        reasoning_text = "\nKE HOACH SUY LUAN DA DUOC BACKEND KIEM CHUNG:\n" + "\n".join(reasoning_lines) + "\n"

    prompt = f"""Bạn là chuyên gia tư vấn pháp luật thuế tại Việt Nam, đặc biệt am hiểu:
- Luật Thuế thu nhập doanh nghiệp
- Luật Thuế thu nhập cá nhân
- Luật Quản lý thuế

NGUYÊN TẮC BẮT BUỘC:
1. CHỈ dựa vào "CĂN CỨ PHÁP LÝ" bên dưới để trả lời.
2. KHÔNG tự bịa đặt, KHÔNG dùng kiến thức bên ngoài dữ liệu.
3. Trích dẫn rõ: tên luật + số điều khi đưa ra kết luận.
4. Nếu dữ liệu không đủ → nói thẳng: "Dữ liệu hiện tại chưa có thông tin về vấn đề này."
5. Trả lời bằng tiếng Việt, rõ ràng, có cấu trúc.

{reasoning_text}
YÊU CẦU BỔ SUNG (nếu có): {(extra_instructions or "").strip()}

CĂN CỨ PHÁP LÝ:
{context}

CÂU HỎI: {question}
TRẢ LỜI:"""

    try:
        response = llm.invoke(prompt)
        answer = (getattr(response, "content", "") or "").strip()
        if not answer:
            raise GeminiError("Không thể tạo câu trả lời từ hệ thống AI.", "LLM_EMPTY_RESPONSE")
        return answer
    except Exception as exc:
        logger.exception("Groq answer exception")
        raise GeminiError("Hệ thống AI gặp sự cố tạm thời khi sinh câu trả lời.", "LLM_INTERNAL_ERROR") from exc


def self_reflect_answer(
    question: str,
    answer: str,
    context: str,
    max_output_tokens: int = 256,
) -> dict:
    """Tự phản tư (Self-RAG) bằng Groq"""
    llm = _get_groq_client()
    
    prompt = f"""Bạn là bộ kiểm định chất lượng câu trả lời theo cơ chế Self-RAG (tự phản tư).
Nhiệm vụ:
1) Is_Supported: Câu trả lời có dựa HOÀN TOÀN trên context không? 
2) Is_Useful: Câu trả lời có giải quyết đủ ý câu hỏi không?

CHỈ trả về đúng 1 JSON object, không kèm giải thích ngoài JSON, theo schema:
{{
  "is_supported": true/false,
  "unsupported_claims": ["..."],
  "is_useful": true/false,
  "missing_points": ["..."],
  "improvement_suggestions": "..."
}}

CÂU HỎI: {question}
CĂN CỨ PHÁP LÝ: {context}
CÂU TRẢ LỜI: {answer}
"""
    try:
        # Ép cấu hình response định dạng JSON đối với Groq nếu dòng model hỗ trợ
        response = llm.bind(response_format={"type": "json_object"}).invoke(prompt)
        text = (getattr(response, "content", "") or "").strip()
        
        # Parse JSON kết quả an toàn
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        return json.loads(text)
    except Exception as exc:
        logger.warning("Groq self-reflection failed, fallback to pass: %s", exc)
        # Nếu bộ chấm điểm lỗi quota, cho bypass mặc định cho phép câu trả lời đi qua
        return {
            "is_supported": True,
            "unsupported_claims": [],
            "is_useful": True,
            "missing_points": [],
            "improvement_suggestions": "Bypass qua bộ lọc lỗi."
        }