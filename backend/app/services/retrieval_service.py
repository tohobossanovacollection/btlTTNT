import numpy as np
from app.services.law_retriever import load_all_laws
from app.services.embedding_service import embed_texts

# Load luật 1 lần khi server start
LAWS = load_all_laws()
# Sử dụng trường "text" đầy đủ (gồm cả tên luật, điều, khoản) để làm embedding sẽ chính xác hơn chỉ dùng "content"
LAW_TEXTS = [l["text"] for l in LAWS] 
LAW_EMBEDDINGS = None

def retrieve_laws_semantic(question: str, top_k: int = 3, threshold: float = 0.4):
    global LAW_EMBEDDINGS

    if LAW_EMBEDDINGS is None:
        LAW_EMBEDDINGS = np.array(embed_texts(LAW_TEXTS))
        # Chuẩn hóa ma trận embedding sẵn để tăng tốc độ tính toán
        norm = np.linalg.norm(LAW_EMBEDDINGS, axis=1, keepdims=True)
        # Tránh chia cho 0 nếu có vector rỗng
        norm = np.where(norm == 0, 1, norm)
        LAW_EMBEDDINGS = LAW_EMBEDDINGS / norm

    # Embed câu hỏi của user
    question_embedding = np.array(embed_texts([question])[0])
    q_norm = np.linalg.norm(question_embedding)
    if q_norm > 0:
        question_embedding = question_embedding / q_norm

    # Tính Cosine Similarity chuẩn xác (Giá trị luôn nằm trong khoảng [-1, 1])
    scores = np.dot(LAW_EMBEDDINGS, question_embedding)

    # Lấy các index có điểm số cao nhất
    top_indices = scores.argsort()[-top_k:][::-1]
    
    results = []
    for i in top_indices:
        score = float(scores[i])
        # SKILL-RAG IDEA: Chỉ giữ lại các chunk thực sự liên quan vượt qua ngưỡng an toàn (threshold)
        if score >= threshold:
            # Gắn thêm điểm số vào dictionary để tầng API đưa ra quyết định định tuyến
            matched_law = LAWS[i].copy()
            matched_law["score"] = score
            results.append(matched_law)
            
    return results