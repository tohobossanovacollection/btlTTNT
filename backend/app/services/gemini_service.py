import os
from google import genai
from google.genai.errors import APIError
from app.config import settings
from app.prompts.legal_prompt import build_prompt

# Khởi tạo client theo chuẩn SDK mới nhất của Google
if not settings.GOOGLE_API_KEY:
    raise RuntimeError("❌ GOOGLE_API_KEY chưa được thiết lập trong config")

client = genai.Client(api_key=settings.GOOGLE_API_KEY)

def ask_gemini(question: str, laws: list, history_context: str = "") -> str:
    """
    laws: list các dict luật đã retrieve từ vector search
    history_context: chuỗi lịch sử chat gộp từ các câu thoại cũ
    """
    try:
        # Gọi sang tầng prompt để lấy cấu trúc Prompt Thuế hoàn chỉnh
        prompt = build_prompt(question, laws, history_context)

        # Sử dụng mô hình gemini-2.5-flash theo cú pháp chuẩn của bạn
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )

        return response.text.strip()

    except APIError as e:
        error_message = str(e)
        if "429" in error_message or "quota" in error_message.lower():
            return "⚠️ Hệ thống đang quá tải (đã đạt giới hạn API miễn phí). Vui lòng thử lại sau."
        print("Gemini APIError:", e)
        return "❌ Lỗi kết nối tới hệ thống AI."

    except Exception as e:
        print("Gemini error:", e)
        return "❌ Hệ thống AI gặp sự cố tạm thời."