import hashlib
import math
import os
import re
import threading
import unicodedata
from collections import Counter

import numpy as np

LOCAL_EMBEDDING_DIM = int(os.getenv("LOCAL_EMBEDDING_DIM", "2048"))
LOCAL_EMBEDDING_MIN_TOKEN_LENGTH = int(os.getenv("LOCAL_EMBEDDING_MIN_TOKEN_LENGTH", "2"))

_STATE_LOCK = threading.Lock()
_IDF_VECTOR: np.ndarray | None = None


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", str(value or ""))
    without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_accents.replace("đ", "d").replace("Đ", "D").lower()


def _tokenize(text: str) -> list[str]:
    normalized = _normalize_text(text)
    tokens = re.findall(r"[a-z0-9]+", normalized)
    return [token for token in tokens if len(token) >= LOCAL_EMBEDDING_MIN_TOKEN_LENGTH]


def _extract_features(text: str) -> list[str]:
    tokens = _tokenize(text)
    if not tokens:
        return []

    features = list(tokens)
    features.extend(f"{tokens[index]}_{tokens[index + 1]}" for index in range(len(tokens) - 1))
    return features


def _hash_feature(feature: str) -> tuple[int, float]:
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    number = int.from_bytes(digest, "big", signed=False)
    index = number % LOCAL_EMBEDDING_DIM
    sign = 1.0 if (number >> 1) % 2 == 0 else -1.0
    return index, sign


def _default_idf_vector() -> np.ndarray:
    return np.ones(LOCAL_EMBEDDING_DIM, dtype=np.float32)


def _build_idf_vector(texts: list[str]) -> np.ndarray:
    document_count = max(len(texts), 1)
    document_frequency = np.zeros(LOCAL_EMBEDDING_DIM, dtype=np.float32)

    for text in texts:
        active_indices = {_hash_feature(feature)[0] for feature in set(_extract_features(text))}
        for index in active_indices:
            document_frequency[index] += 1.0

    return np.log((1.0 + document_count) / (1.0 + document_frequency)) + 1.0


def _vectorize_text(text: str, idf_vector: np.ndarray) -> list[float]:
    features = _extract_features(text)
    vector = np.zeros(LOCAL_EMBEDDING_DIM, dtype=np.float32)

    if not features:
        return vector.tolist()

    counts = Counter(features)
    for feature, count in counts.items():
        index, sign = _hash_feature(feature)
        term_frequency = 1.0 + math.log(float(count))
        vector[index] += sign * term_frequency * float(idf_vector[index])

    return vector.tolist()


def _get_idf_vector() -> np.ndarray:
    with _STATE_LOCK:
        if _IDF_VECTOR is None:
            return _default_idf_vector()
        return _IDF_VECTOR.copy()


def set_idf_vector(idf_vector: np.ndarray | None) -> None:
    with _STATE_LOCK:
        global _IDF_VECTOR
        _IDF_VECTOR = None if idf_vector is None else np.asarray(idf_vector, dtype=np.float32).copy()


def get_idf_vector() -> np.ndarray:
    return _get_idf_vector()


def embed_texts(texts: list[str], task_type: str = "retrieval_document") -> list:
    if not texts:
        return []

    normalized_task_type = str(task_type or "").strip().lower()

    if normalized_task_type == "retrieval_document" and len(texts) > 1:
        idf_vector = _build_idf_vector(texts)
        set_idf_vector(idf_vector)
        return [_vectorize_text(text, idf_vector) for text in texts]

    idf_vector = _get_idf_vector()
    return [_vectorize_text(text, idf_vector) for text in texts]
