import os
from google import genai
from google.genai.errors import APIError
from app.config import settings

# Khởi tạo client theo chuẩn SDK mới nhất của Google
if not settings.GOOGLE_API_KEY:
    raise RuntimeError("❌ GOOGLE_API_KEY chưa được thiết lập trong config")

client = genai.Client(api_key=settings.GOOGLE_API_KEY)

def ask_gemini(question: str, laws: list) -> str:
    """
    laws: list các dict luật đã retrieve
    """
    if not laws:
        return "Không tìm thấy căn cứ pháp lý trong dữ liệu hiện có."

    try:
        # ===== BUILD CONTEXT =====
        context_blocks = []
        for law in laws:
            context_blocks.append(
                f"Luật: {law.get('law_name', 'Luật HNGĐ 2014')}\n"
                f"Điều: {law.get('article', '')}\n"
                f"Tiêu đề: {law.get('title', '')}\n"
                f"Nội dung: {law.get('content', '')}\n"
            )

        context = "\n---\n".join(context_blocks)

        prompt = f"""
Bạn là trợ lý pháp luật Việt Nam chuyên về Luật Hôn nhân và Gia đình.

❗ NGUYÊN TẮC BẮT BUỘC:
- CHỈ sử dụng thông tin trong DỮ LIỆU PHÁP LUẬT bên dưới
- TUYỆT ĐỐI KHÔNG bổ sung kiến thức bên ngoài
- Nếu dữ liệu chưa đủ chi tiết → phải nói rõ

=== DỮ LIỆU PHÁP LUẬT ===
{context}

=== CÂU HỎI ===
{question}

=== TRẢ LỜI ===
"""

        # Cú pháp chuẩn của thư viện mới: client.models.generate_content
        # Sử dụng gemini-2.5-flash là bản mới nhất, miễn phí và phản hồi siêu nhanh
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