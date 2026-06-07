import os
from functools import lru_cache

EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "paraphrase-multilingual-MiniLM-L12-v2",
)


@lru_cache(maxsize=1)
def get_embedding_model():
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(EMBEDDING_MODEL_NAME)
    except Exception as exc:
        raise RuntimeError(
            f"Cannot load embedding model '{EMBEDDING_MODEL_NAME}'. "
            "Check your internet connection or download the model into the Hugging Face cache first."
        ) from exc

def embed_texts(texts):
    return get_embedding_model().encode(texts, normalize_embeddings=True)
