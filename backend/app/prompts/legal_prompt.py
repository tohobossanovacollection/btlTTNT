# def build_prompt(question: str, laws: list) -> str:
#     law_text = "\n\n".join(
#         f"Điều {l['article']}: {l['title']}\n{l['content']}"
#         for l in laws
#     )

#     return f"""
# Bạn là trợ lý AI tư vấn Luật Hôn nhân và Gia đình Việt Nam.

# CHỈ được sử dụng thông tin trong phần "NGỮ CẢNH PHÁP LUẬT" dưới đây.
# KHÔNG được sử dụng kiến thức bên ngoài.
# Nếu không tìm thấy thông tin phù hợp, hãy trả lời:
# "Không tìm thấy căn cứ pháp lý phù hợp trong dữ liệu hiện có."

# CÂU HỎI:
# {question}

# CĂN CỨ PHÁP LUẬT:
# {law_text}

# TRẢ LỜI:
# """
