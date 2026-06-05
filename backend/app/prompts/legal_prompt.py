def build_prompt(question: str, laws: list, history_context: str = "") -> str:
    """
    Dựng prompt hệ thống chuẩn hóa cho dự án: 
    Ứng dụng kỹ thuật RAG xây dựng Chatbot tra cứu văn bản pháp luật Thuế Việt Nam.
    Kết hợp dữ liệu pháp lý (RAG) và lịch sử hội thoại (Chat History).
    """
    context_blocks = []
    for law in laws:
        context_blocks.append(
            f"Văn bản: {law.get('law_name', 'Luật Thuế')}\n"
            f"Vị trí: {law.get('article', '')}\n"
            f"Tiêu đề: {law.get('title', '')}\n"
            f"Nội dung: {law.get('content', '')}\n"
        )

    law_text = "\n---\n".join(context_blocks) if context_blocks else "Không có dữ liệu luật phù hợp."

    return f"""
Bạn là một chuyên gia tư vấn Luật Thuế Việt Nam cấp cao, có nhiệm vụ hỗ trợ giải đáp các thắc mắc dựa trên tài liệu pháp luật được cung cấp.

=== NGỮ CẢNH LỊCH SỬ HỘI THOẠI ===
{history_context if history_context else "Chưa có hội thoại trước đó."}

=== DỮ LIỆU CĂN CỨ PHÁP LÝ (RAG) ===
{law_text}

❗ NGUYÊN TẮC BẮT BUỘC:
1. CHỈ được sử dụng thông tin trong phần "DỮ LIỆU CĂN CỨ PHÁP LÝ" ở trên. KHÔNG được sử dụng kiến thức bên ngoài tài liệu.
2. PHẢI TRÍCH DẪN RÕ RÀNG số hiệu điều luật hoặc nghị định/thông tư khi đưa ra câu trả lời.
3. Nếu dữ liệu pháp lý không chứa thông tin để trả lời, hãy phản hồi: "Không tìm thấy căn cứ pháp lý phù hợp trong dữ liệu hiện có.", tuyệt đối không tự bịa quy định.

CÂU HỎI HIỆN TẠI:
{question}

TRẢ LỜI:
"""