import numpy as np
from app.services.law_retriever import load_all_laws
from app.services.embedding_service import embed_texts

# Load luật 1 lần duy nhất khi server khởi động
LAWS = load_all_laws()

# Dùng trường "text" (giàu ngữ cảnh) để embedding, không dùng "content"
LAW_TEXTS = [l["text"] for l in LAWS]
LAW_EMBEDDINGS = None

# Ngưỡng tối thiểu: chỉ lấy kết quả có độ tương đồng >= 0.30
SCORE_THRESHOLD = 0.30


def retrieve_laws_semantic(question: str, top_k: int = 6) -> list:
    global LAW_EMBEDDINGS

    # Khởi tạo embeddings lần đầu (lazy loading)
    if LAW_EMBEDDINGS is None:
        print(f"⏳ Đang tạo embeddings cho {len(LAWS)} phân đoạn luật...")
        LAW_EMBEDDINGS = embed_texts(LAW_TEXTS)
        print("✅ Embeddings sẵn sàng!")

    # Embed câu hỏi
    question_embedding = embed_texts([question])[0]

    # Tính cosine similarity (dot product với vector đã normalize)
    scores = np.dot(LAW_EMBEDDINGS, question_embedding)

    # Lấy top_k * 2 để lọc theo threshold
    candidate_count = min(top_k * 2, len(LAWS))
    top_indices = scores.argsort()[-candidate_count:][::-1]

    # Lọc theo ngưỡng điểm và chỉ lấy top_k
    results = []
    print(f"\n🔍 Tìm kiếm: '{question[:60]}...'")
    for i in top_indices:
        score = float(scores[i])
        if score >= SCORE_THRESHOLD:
            law = LAWS[i].copy()
            law["_score"] = round(score, 4)
            results.append(law)
            print(f"  ✅ [{score:.4f}] {law['law_name']} — {law['article']}: {law['title'][:50]}")
        if len(results) >= top_k:
            break

    if not results:
        print(f"  ⚠️  Không có kết quả nào vượt ngưỡng {SCORE_THRESHOLD}")

    print(f"  → Trả về {len(results)} điều luật liên quan\n")
    return results
