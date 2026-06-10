import json
import logging
import os
import threading
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_CLIENT_LOCK = threading.Lock()
_CLIENT: Any | None = None
_CLIENT_MODEL_NAME = ""


class GroqServiceError(RuntimeError):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


def _resolve_model_name() -> str:
    model_name = (os.getenv("GROQ_MODEL_NAME") or settings.GROQ_MODEL_NAME or "").strip()
    if model_name in {"", "llama3-70b-8192", "groq/compound", "groq/compound-mini"}:
        return "llama-3.3-70b-versatile"
    return model_name


def _get_groq_client() -> Any:
    global _CLIENT, _CLIENT_MODEL_NAME

    api_key = (os.getenv("GROQ_API_KEY") or settings.GROQ_API_KEY or "").strip()
    if not api_key:
        raise GroqServiceError("Hệ thống AI (Groq) chưa được cấu hình API key.", "LLM_NOT_CONFIGURED")

    model_name = _resolve_model_name()

    with _CLIENT_LOCK:
        if _CLIENT is not None and _CLIENT_MODEL_NAME == model_name:
            return _CLIENT

        try:
            from langchain_groq import ChatGroq
        except ModuleNotFoundError as exc:
            raise GroqServiceError("Thiếu thư viện `langchain-groq`.", "LLM_DEPENDENCY_MISSING") from exc

        logger.info("Khoi tao ChatGroq client voi model=%s", model_name)
        _CLIENT = ChatGroq(
            api_key=api_key,
            model_name=model_name,
            temperature=0.0,
            max_retries=2,
        )
        _CLIENT_MODEL_NAME = model_name
        return _CLIENT


def classify_query_intent(question: str, max_output_tokens: int = 4) -> str:
    del max_output_tokens
    llm = _get_groq_client()
    prompt = f"""Phan loai cau hoi phap ly sau thanh dung 1 tu duy nhat.

Quy tac:
- Tra ve SIMPLE neu cau hoi co the tra loi bang mot lan truy van van ban phap ly.
- Tra ve COMPLEX neu cau hoi co nhieu dieu kien, ngoai le, so sanh, tinh huong ket hop, hoac can suy luan nhieu buoc.
- Chi duoc tra ve SIMPLE hoac COMPLEX, khong giai thich.

Cau hoi: {question}
"""
    try:
        response = llm.invoke(prompt)
        label = (getattr(response, "content", "") or "").strip().upper()
        if "COMPLEX" in label:
            return "COMPLEX"
        if "SIMPLE" in label:
            return "SIMPLE"
        return "SIMPLE"
    except Exception as exc:
        logger.warning("Groq router error: %s", exc)
        return "SIMPLE"


def _has_low_relevance_context(laws: list[dict], refined_context: str | None) -> bool:
    if not laws or refined_context:
        return False
    highest_score = laws[0].get("_final_score", 0) or laws[0].get("score", 0)
    return float(highest_score or 0) < 0.3


def _build_context(laws: list[dict]) -> str:
    context_blocks: list[str] = []
    for law in laws:
        score_info = ""
        if law.get("_final_score") is not None:
            score_info = f" (do lien quan: {law.get('_final_score')})"

        step_info = ""
        matched_steps = law.get("_matched_step_titles") or []
        if matched_steps:
            step_info = f"\n   Phuc vu buoc suy luan: {', '.join(matched_steps)}"

        block = (
            f"{law.get('law_name', 'Khong ro ten luat')}{score_info}\n"
            f"{law.get('article', '')} - {law.get('title', '')}{step_info}\n"
            f"{(law.get('content') or '').strip()}"
        )
        context_blocks.append(block)

    return "\n\n" + ("\n" + ("-" * 60) + "\n\n").join(context_blocks)


def ask_groq(
    question: str,
    laws: list,
    reasoning_steps: list[dict] | None = None,
    refined_context: str | None = None,
    extra_instructions: str | None = None,
) -> str:
    if (not laws and not refined_context) or _has_low_relevance_context(laws, refined_context):
        return "Dữ liệu hiện tại chưa có thông tin về vấn đề này."

    llm = _get_groq_client()
    context = refined_context.strip() if refined_context else _build_context(laws)

    reasoning_text = ""
    if reasoning_steps:
        reasoning_lines = [
            f"- {step.get('step_id')}: {step.get('title')} | truy van: {step.get('query')}"
            for step in reasoning_steps
        ]
        reasoning_text = (
            "\nKE HOACH SUY LUAN DA DUOC BACKEND KIEM CHUNG:\n"
            + "\n".join(reasoning_lines)
            + "\n"
        )

    prompt = f"""Bạn là chuyên gia tư vấn pháp luật thuế tại Việt Nam, đặc biệt am hiểu:
- Luật Thuế thu nhập doanh nghiệp
- Luật Thuế thu nhập cá nhân
- Luật Quản lý thuế

NGUYÊN TẮC BẮT BUỘC:
1. CHỈ dựa vào "CĂN CỨ PHÁP LÝ" bên dưới để trả lời.
2. KHÔNG tự bịa đặt, KHÔNG dùng kiến thức bên ngoài dữ liệu.
3. Trích dẫn rõ: tên luật + số điều khi đưa ra kết luận.
4. Nếu dữ liệu không đủ thì nói rõ: "Dữ liệu hiện tại chưa có thông tin về vấn đề này."
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
            raise GroqServiceError("Không thể tạo câu trả lời từ hệ thống AI.", "LLM_EMPTY_RESPONSE")
        return answer
    except GroqServiceError:
        raise
    except Exception as exc:
        logger.exception("Groq answer exception")
        raise GroqServiceError(
            "Hệ thống AI gặp sự cố tạm thời khi sinh câu trả lời.",
            "LLM_INTERNAL_ERROR",
        ) from exc


def self_reflect_answer(
    question: str,
    answer: str,
    context: str,
    max_output_tokens: int = 256,
) -> dict:
    del max_output_tokens
    llm = _get_groq_client()
    prompt = f"""Bạn là bộ kiểm định chất lượng câu trả lời theo cơ chế Self-RAG.
Nhiệm vụ:
1) Is_Supported: Câu trả lời có dựa hoàn toàn trên context không?
2) Is_Useful: Câu trả lời có giải quyết đủ ý câu hỏi không?

Chỉ trả về đúng 1 JSON object theo schema:
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
        response = llm.bind(response_format={"type": "json_object"}).invoke(prompt)
        text = (getattr(response, "content", "") or "").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        return json.loads(text)
    except Exception as exc:
        logger.warning("Groq self-reflection failed, fallback to pass: %s", exc)
        return {
            "is_supported": True,
            "unsupported_claims": [],
            "is_useful": True,
            "missing_points": [],
            "improvement_suggestions": "Bypass qua bo loc loi.",
        }
