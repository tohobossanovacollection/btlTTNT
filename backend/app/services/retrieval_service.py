import numpy as np
from app.services.law_retriever import load_all_laws
from app.services.embedding_service import embed_texts

# Load luật 1 lần khi server start
LAWS = load_all_laws()
LAW_TEXTS = [l["content"] for l in LAWS]
LAW_EMBEDDINGS = None


def retrieve_laws_semantic(question: str, top_k: int = 3):
    global LAW_EMBEDDINGS

    if LAW_EMBEDDINGS is None:
        LAW_EMBEDDINGS = embed_texts(LAW_TEXTS)

    question_embedding = embed_texts([question])[0]
    scores = np.dot(LAW_EMBEDDINGS, question_embedding)

    top_indices = scores.argsort()[-top_k:][::-1]
    return [LAWS[i] for i in top_indices]