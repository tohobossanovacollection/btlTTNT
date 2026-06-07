from google import genai
from google.genai import types
from google.genai.errors import APIError
from app.config import settings

if not settings.GOOGLE_API_KEY:
    raise RuntimeError("❌ GOOGLE_API_KEY chưa được thiết lập trong config")

client = genai.Client(api_key=settings.GOOGLE_API_KEY)


def ask_gemini(question: str, laws: list) -> str:
    """
    Gọi Gemini với các điều luật đã retrieve để trả lời câu hỏi.
    laws: list[dict] — mỗi dict có 'law_name', 'article', 'title', 'content'
    """
    if not laws:
        return "Không tìm thấy căn cứ pháp lý phù hợp trong dữ liệu hiện có."

    try:
        # BUILD CONTEXT 
        context_blocks = []
        for law in laws:
            score_info = f" (độ liên quan: {law.get('_score', '')})" if law.get('_score') else ""
            block = (
                f"📌 {law.get('law_name', 'Không rõ tên luật')}{score_info}\n"
                f"   {law.get('article', '')} — {law.get('title', '')}\n"
                f"{law.get('content', '').strip()}"
            )
            context_blocks.append(block)

        context = "\n\n" + "─" * 60 + "\n\n".join(context_blocks)

        # PROMPT 
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

CĂN CỨ PHÁP LÝ:
{context}

═══════════════════════════════════════════════════════════════
CÂU HỎI: {question}
═══════════════════════════════════════════════════════════════

TRẢ LỜI (dựa CHỈ vào căn cứ trên, có trích dẫn điều khoản):
"""

        # CONFIG 
        config = types.GenerateContentConfig(
            temperature=0.1,  # Rất thấp — AI phải trả lời chính xác, không sáng tạo
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
            ]
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=config
        )

        if not response.text:
            return "⚠️ Không thể tạo câu trả lời. Vui lòng thử lại."

        return response.text.strip()

    except APIError as e:
        err = str(e)
        if "429" in err or "quota" in err.lower():
            return "⚠️ Hệ thống đang quá tải (đạt giới hạn API). Vui lòng thử lại sau vài phút."
        print(f"❌ Gemini APIError: {e}")
        return "❌ Lỗi kết nối tới hệ thống AI."

    except Exception as e:
        print(f"❌ Gemini exception: {e}")
        return "❌ Hệ thống AI gặp sự cố tạm thời."
