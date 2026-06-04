from sentence_transformers import SentenceTransformer

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

def embed_texts(texts):
    return model.encode(texts, normalize_embeddings=True)
