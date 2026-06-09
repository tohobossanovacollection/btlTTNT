import logging
import threading

from app.config import settings

logger = logging.getLogger(__name__)

_CLIENT_LOCK = threading.Lock()
_CLIENT = None
_CLIENT_KEY = None


class GeminiError(RuntimeError):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


def _get_client():
    global _CLIENT, _CLIENT_KEY
    api_key = (settings.GOOGLE_API_KEY or "").strip()
    if not api_key:
        raise GeminiError("Hệ thống AI chưa được cấu hình.", "LLM_NOT_CONFIGURED")

    with _CLIENT_LOCK:
        if _CLIENT is not None and _CLIENT_KEY == api_key:
            return _CLIENT

        try:
            from google import genai
        except ModuleNotFoundError as exc:
            raise GeminiError("Thiếu thư viện kết nối hệ thống AI.", "LLM_DEPENDENCY_MISSING") from exc

        _CLIENT = genai.Client(api_key=api_key)
        _CLIENT_KEY = api_key
        return _CLIENT


def classify_query_intent(question: str, max_output_tokens: int = 4) -> str:
    try:
        from google.genai import types
        from google.genai.errors import APIError
    except ModuleNotFoundError:
        raise GeminiError("Thiếu thư viện kết nối hệ thống AI.", "LLM_DEPENDENCY_MISSING")

    client = _get_client()
    prompt = f"""Phan loai cau hoi phap ly sau thanh dung 1 tu duy nhat.

Quy tac:
- Tra ve SIMPLE neu cau hoi co the tra loi bang mot lan truy van van ban phap ly.
- Tra ve COMPLEX neu cau hoi co nhieu dieu kien, ngoai le, so sanh, tinh huong ket hop, hoac can suy luan nhieu buoc.
- Chi duoc tra ve SIMPLE hoac COMPLEX, khong giai thich.

Cau hoi: {question}
"""

    try:
        response = client.models.generate_content(
            model=settings.MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=max_output_tokens,
            ),
        )
        label = (getattr(response, "text", None) or "").strip().upper()
        if "COMPLEX" in label:
            return "COMPLEX"
        if "SIMPLE" in label:
            return "SIMPLE"
        raise GeminiError("Khong the phan loai y dinh cau hoi.", "LLM_ROUTER_INVALID_OUTPUT")
    except GeminiError:
        raise
    except APIError as exc:
        raw = str(exc)
        lowered = raw.lower()
        logger.warning("Gemini router APIError: %s", raw)
        if "429" in raw or "quota" in lowered:
            raise GeminiError("He thong AI dang qua tai khi phan loai cau hoi.", "LLM_QUOTA_EXCEEDED") from exc
        if "503" in raw or "unavailable" in lowered:
            raise GeminiError("He thong AI tam thoi khong san sang khi phan loai cau hoi.", "LLM_UNAVAILABLE") from exc
        raise GeminiError("Khong the ket noi he thong AI de phan loai cau hoi.", "LLM_UPSTREAM_ERROR") from exc
    except Exception as exc:
        logger.exception("Gemini router exception")
        raise GeminiError("He thong AI gap su co khi phan loai cau hoi.", "LLM_ROUTER_INTERNAL_ERROR") from exc


def ask_gemini(
    question: str,
    laws: list,
    reasoning_steps: list[dict] | None = None,
    refined_context: str | None = None,
    extra_instructions: str | None = None,
) -> str:
    if not laws and not refined_context:
        return "Không tìm thấy căn cứ pháp lý phù hợp trong dữ liệu hiện có."

    try:
        from google.genai import types
        from google.genai.errors import APIError
    except ModuleNotFoundError:
        raise GeminiError("Thiếu thư viện kết nối hệ thống AI.", "LLM_DEPENDENCY_MISSING")

    client = _get_client()

    try:
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
                reasoning_lines.append(
                    f"- {step.get('step_id')}: {step.get('title')} | truy van: {step.get('query')}"
                )
            reasoning_text = "\nKE HOACH SUY LUAN DA DUOC BACKEND KIEM CHUNG:\n" + "\n".join(reasoning_lines) + "\n"

        prompt = f"""Bạn là chuyên gia tư vấn pháp luật thuế tại Việt Nam, đặc biệt am hiểu:
- Luật Thuế thu nhập doanh nghiệp
- Luật Thuế thu nhập cá nhân
- Luật Quản lý thuế
- Các Nghị định, Thông tư hướng dẫn liên quan

═══════════════════════════════════════════════════════════════
NGUYÊN TẮC BẮT BUỘC:
1. CHỈ dựa vào "CĂN CỨ PHÁP LÝ" bên dưới để trả lời.
2. KHÔNG tự bịa đặt, KHÔNG dùng kiến thức bên ngoài dữ liệu.
3. Trích dẫn rõ: tên luật + số điều khi đưa ra kết luận.
4. Nếu dữ liệu không đủ → nói thẳng: "Dữ liệu hiện tại chưa có thông tin về vấn đề này."
5. Trả lời bằng tiếng Việt, rõ ràng, có cấu trúc.
═══════════════════════════════════════════════════════════════
{reasoning_text}

YÊU CẦU BỔ SUNG (nếu có):
{(extra_instructions or "").strip()}


CĂN CỨ PHÁP LÝ:
{context}

═══════════════════════════════════════════════════════════════
CÂU HỎI: {question}
═══════════════════════════════════════════════════════════════

TRẢ LỜI (dựa CHỈ vào căn cứ trên, có trích dẫn điều khoản):
"""

        config = types.GenerateContentConfig(
            temperature=0.1,
            safety_settings=[
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
            ],
        )

        response = client.models.generate_content(
            model=settings.MODEL_NAME,
            contents=prompt,
            config=config,
        )

        answer = (getattr(response, "text", None) or "").strip()
        if not answer:
            raise GeminiError("Không thể tạo câu trả lời từ hệ thống AI.", "LLM_EMPTY_RESPONSE")

        return answer

    except GeminiError:
        raise
    except APIError as exc:
        raw = str(exc)
        lowered = raw.lower()
        logger.warning("Gemini APIError: %s", raw)
        if "429" in raw or "quota" in lowered:
            raise GeminiError("Hệ thống AI đang quá tải (đạt giới hạn API).", "LLM_QUOTA_EXCEEDED") from exc
        if "503" in raw or "unavailable" in lowered or "temporarily" in lowered:
            raise GeminiError("Hệ thống AI tạm thời không sẵn sàng.", "LLM_UNAVAILABLE") from exc
        raise GeminiError("Không thể kết nối hệ thống AI.", "LLM_UPSTREAM_ERROR") from exc
    except Exception as exc:
        logger.exception("Gemini exception")
        raise GeminiError("Hệ thống AI gặp sự cố tạm thời.", "LLM_INTERNAL_ERROR") from exc


def self_reflect_answer(
    question: str,
    answer: str,
    context: str,
    max_output_tokens: int = 256,
) -> dict:
    try:
        from google.genai import types
        from google.genai.errors import APIError
    except ModuleNotFoundError:
        raise GeminiError("Thiếu thư viện kết nối hệ thống AI.", "LLM_DEPENDENCY_MISSING")

    client = _get_client()
    prompt = f"""Bạn là bộ kiểm định chất lượng câu trả lời theo cơ chế Self-RAG (tự phản tư).

Bạn sẽ nhận vào:
- CÂU HỎI của người dùng
- CĂN CỨ PHÁP LÝ (context) do hệ thống truy xuất
- CÂU TRẢ LỜI do mô hình sinh

Nhiệm vụ:
1) Is_Supported: Câu trả lời có dựa HOÀN TOÀN trên context không? Nếu có phần suy diễn/khẳng định không thấy trong context thì là false.
2) Is_Useful: Câu trả lời có giải quyết đủ ý câu hỏi không? Nếu thiếu điều kiện/ngoại lệ/đối tượng áp dụng quan trọng thì là false.

CHỈ trả về đúng 1 JSON object, không kèm giải thích ngoài JSON, theo schema:
{{
  "is_supported": true/false,
  "unsupported_claims": ["..."],
  "is_useful": true/false,
  "missing_points": ["..."],
  "improvement_suggestions": "..."
}}

CÂU HỎI:
{question}

CĂN CỨ PHÁP LÝ:
{context}

CÂU TRẢ LỜI:
{answer}
"""

    try:
        response = client.models.generate_content(
            model=settings.MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=int(max_output_tokens or 256),
            ),
        )
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            raise GeminiError("Không thể tự đánh giá câu trả lời từ hệ thống AI.", "LLM_EMPTY_RESPONSE")
        import json

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                data = json.loads(text[start : end + 1])
            else:
                raise
        if not isinstance(data, dict):
            raise GeminiError("Kết quả tự đánh giá không hợp lệ.", "LLM_EVALUATOR_INVALID_OUTPUT")
        return data
    except GeminiError:
        raise
    except APIError as exc:
        raw = str(exc)
        lowered = raw.lower()
        logger.warning("Gemini self-reflection APIError: %s", raw)
        if "429" in raw or "quota" in lowered:
            raise GeminiError("Hệ thống AI đang quá tải khi tự đánh giá.", "LLM_QUOTA_EXCEEDED") from exc
        if "503" in raw or "unavailable" in lowered or "temporarily" in lowered:
            raise GeminiError("Hệ thống AI tạm thời không sẵn sàng khi tự đánh giá.", "LLM_UNAVAILABLE") from exc
        raise GeminiError("Không thể kết nối hệ thống AI để tự đánh giá.", "LLM_UPSTREAM_ERROR") from exc
    except Exception as exc:
        logger.exception("Gemini self-reflection exception")
        raise GeminiError("Hệ thống AI gặp sự cố khi tự đánh giá.", "LLM_INTERNAL_ERROR") from exc
