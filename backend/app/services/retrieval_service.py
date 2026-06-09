import numpy as np
import threading
import unicodedata
import logging
import json
import hashlib
import time
from pathlib import Path
from app.services.law_retriever import load_all_laws
from app.services.embedding_service import (
    LOCAL_EMBEDDING_DIM,
    LOCAL_EMBEDDING_MIN_TOKEN_LENGTH,
    embed_texts,
    get_idf_vector,
    set_idf_vector,
)
from app.config import settings

logger = logging.getLogger(__name__)

LAWS = None
LAW_TEXTS = None
LAW_EMBEDDINGS = None
_LAWS_LOCK = threading.Lock()
_EMBEDDINGS_LOCK = threading.Lock()

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _cache_dir() -> Path:
    path = Path(settings.RAG_CACHE_DIR)
    return path if path.is_absolute() else (_PROJECT_ROOT / path)


def _cache_paths() -> dict[str, Path]:
    root = _cache_dir()
    return {
        "dir": root,
        "laws": root / "law_index.json",
        "vectors": root / "law_vectors.npy",
        "idf": root / "idf_vector.npy",
        "meta": root / "metadata.json",
    }


def _processed_dir() -> Path:
    return _PROJECT_ROOT / "data" / "processed"


def _processed_fingerprint() -> str:
    processed_dir = _processed_dir()
    hasher = hashlib.blake2b(digest_size=16)
    hasher.update(str(processed_dir).encode("utf-8"))
    hasher.update(str(processed_dir.exists()).encode("utf-8"))
    if not processed_dir.exists():
        return hasher.hexdigest()

    for path in sorted(processed_dir.rglob("*")):
        if path.is_dir():
            continue
        if any(part.startswith("_") for part in path.relative_to(processed_dir).parts):
            continue
        rel = str(path.relative_to(processed_dir)).replace("\\", "/")
        stat = path.stat()
        hasher.update(rel.encode("utf-8"))
        hasher.update(str(stat.st_size).encode("utf-8"))
        hasher.update(str(stat.st_mtime_ns).encode("utf-8"))

    hasher.update(str(LOCAL_EMBEDDING_DIM).encode("utf-8"))
    hasher.update(str(LOCAL_EMBEDDING_MIN_TOKEN_LENGTH).encode("utf-8"))
    return hasher.hexdigest()


def _load_disk_cache():
    if not settings.RAG_DISK_CACHE:
        return None

    paths = _cache_paths()
    try:
        meta_path = paths["meta"]
        if not meta_path.exists():
            return None
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        if metadata.get("fingerprint") != _processed_fingerprint():
            return None
        if not paths["laws"].exists() or not paths["vectors"].exists() or not paths["idf"].exists():
            return None

        laws = json.loads(paths["laws"].read_text(encoding="utf-8"))
        vectors = np.load(paths["vectors"])
        idf_vector = np.load(paths["idf"])
        set_idf_vector(idf_vector)
        return laws, vectors
    except Exception:
        logger.exception("Khong the nap disk cache")
        return None


def _write_disk_cache(laws: list, vectors: np.ndarray) -> None:
    if not settings.RAG_DISK_CACHE:
        return

    paths = _cache_paths()
    paths["dir"].mkdir(parents=True, exist_ok=True)
    fingerprint = _processed_fingerprint()
    idf_vector = get_idf_vector()
    metadata = {
        "fingerprint": fingerprint,
        "created_at": int(time.time()),
        "law_count": len(laws),
        "vector_shape": list(vectors.shape),
        "embedding_dim": int(vectors.shape[1]) if vectors.ndim == 2 else None,
    }

    tmp_laws = paths["laws"].with_suffix(".json.tmp")
    tmp_meta = paths["meta"].with_suffix(".json.tmp")
    tmp_vectors = paths["vectors"].with_name(paths["vectors"].name + ".tmp")
    tmp_idf = paths["idf"].with_name(paths["idf"].name + ".tmp")

    tmp_laws.write_text(json.dumps(laws, ensure_ascii=False), encoding="utf-8")
    tmp_meta.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
    with tmp_vectors.open("wb") as file:
        np.save(file, vectors)
    with tmp_idf.open("wb") as file:
        np.save(file, idf_vector)

    tmp_laws.replace(paths["laws"])
    tmp_meta.replace(paths["meta"])
    tmp_vectors.replace(paths["vectors"])
    tmp_idf.replace(paths["idf"])


def _ensure_laws_loaded() -> list:
    global LAWS, LAW_TEXTS

    if LAWS is not None and LAW_TEXTS is not None:
        return LAWS

    with _LAWS_LOCK:
        if LAWS is None:
            cached = _load_disk_cache()
            if cached is not None:
                cached_laws, cached_vectors = cached
                LAWS = cached_laws
                global LAW_EMBEDDINGS
                LAW_EMBEDDINGS = _normalize_vectors(cached_vectors)
                logger.info("Nap disk cache: %s dieu luat", len(LAWS))
            else:
                LAWS = load_all_laws()
        if LAW_TEXTS is None:
            LAW_TEXTS = [law.get("text") or law.get("content", "") for law in LAWS]

    return LAWS


def _ensure_embeddings_loaded():
    global LAW_EMBEDDINGS

    laws = _ensure_laws_loaded()
    if LAW_EMBEDDINGS is not None:
        return LAW_EMBEDDINGS

    with _EMBEDDINGS_LOCK:
        if LAW_EMBEDDINGS is None:
            logger.info("Dang tao local embeddings cho %s phan doan luat...", len(laws))
            LAW_EMBEDDINGS = _normalize_vectors(embed_texts(LAW_TEXTS, task_type="retrieval_document"))
            _write_disk_cache(laws, LAW_EMBEDDINGS)
            logger.info("Local embeddings san sang.")

    return LAW_EMBEDDINGS


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", str(value or ""))
    without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    without_accents = without_accents.replace("đ", "d").replace("Đ", "D")
    return without_accents.lower()


def _normalize_vectors(vectors) -> np.ndarray:
    array = np.asarray(vectors, dtype=np.float32)
    if array.ndim == 1:
        array = array.reshape(1, -1)

    norms = np.linalg.norm(array, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return array / norms


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _keyword_boost(question: str, law: dict) -> float:
    q = _normalize_text(question)
    haystack = _normalize_text(
        " ".join(
            [
                law.get("law_name", ""),
                law.get("article", ""),
                law.get("title", ""),
                law.get("content", "")[:1200],
            ]
        )
    )

    boost = 0.0
    is_salary_tncn_question = _contains_any(
        q,
        ["tncn", "thu nhap ca nhan", "luong", "tien luong", "tien cong", "giam tru"],
    )
    domain_rules = [
        (
            ["tncn", "thu nhap ca nhan", "luong", "tien luong", "tien cong", "giam tru"],
            ["thu nhap ca nhan"],
            ["tien luong", "tien cong", "giam tru gia canh", "thu nhap tinh thue", "bieu thue"],
        ),
        (
            ["gtgt", "gia tri gia tang", "vat"],
            ["gia tri gia tang", "gtgt"],
            ["thue gia tri gia tang", "khau tru", "hoa don", "chung tu nop thue"],
        ),
        (
            ["tndn", "thu nhap doanh nghiep"],
            ["thu nhap doanh nghiep", "tndn"],
            ["chi phi duoc tru", "thu nhap tinh thue", "uu dai thue"],
        ),
        (
            ["hoa don", "chung tu", "xuat hoa don"],
            ["hoa don", "chung tu"],
            ["lap hoa don", "xuat hoa don", "chung tu"],
        ),
        (
            ["xu phat", "cham nop", "phat", "tron thue"],
            ["xu phat", "quan ly thue"],
            ["cham nop", "tien cham nop", "vi pham hanh chinh", "phat tien"],
        ),
    ]

    for question_terms, law_terms, article_terms in domain_rules:
        if not _contains_any(q, question_terms):
            continue
        if _contains_any(haystack, law_terms):
            boost += 0.30
        if _contains_any(haystack, article_terms):
            boost += 0.18

    if is_salary_tncn_question:
        law_name = _normalize_text(law.get("law_name", ""))
        article = _normalize_text(law.get("article", ""))

        if "luat thue thu nhap ca nhan" in law_name:
            boost += 0.05
            if article in {"dieu 8", "dieu 9", "dieu 10"}:
                boost += 0.95
            elif article == "dieu 11":
                boost += 0.25
            elif article == "dieu 21" and not _contains_any(q, ["khong cu tru", "nuoc ngoai"]):
                boost -= 0.45

        if _contains_any(
            haystack,
            [
                "chuyen nhuong von",
                "dau tu von",
                "trung thuong",
                "ban quyen",
                "nhuong quyen",
                "thua ke",
                "qua tang",
            ],
        ):
            boost -= 0.45

        if _contains_any(haystack, ["dieu khoan thi hanh"]):
            boost -= 0.50

        if _contains_any(haystack, ["hoan nop thua", "hoan thue", "quyet toan"]):
            if not _contains_any(q, ["hoan", "nop thua", "quyet toan"]):
                boost -= 0.25

    return boost


def retrieve_laws_semantic(question: str, top_k: int = 6) -> list:
    laws = _ensure_laws_loaded()
    if not laws:
        return []

    law_embeddings = _ensure_embeddings_loaded()
    top_k = int(top_k or settings.RAG_TOP_K)
    score_threshold = float(settings.RAG_SCORE_THRESHOLD)
    candidate_multiplier = int(settings.RAG_CANDIDATE_MULTIPLIER)

    # Embed câu hỏi
    question_embedding = _normalize_vectors(embed_texts([question], task_type="retrieval_query"))[0]

    # Tính cosine similarity với vector da duoc normalize
    semantic_scores = np.dot(law_embeddings, question_embedding)
    keyword_scores = np.zeros_like(semantic_scores, dtype=np.float32)
    final_scores = semantic_scores.copy()
    for i, law in enumerate(laws):
        boost = float(_keyword_boost(question, law))
        keyword_scores[i] = boost
        final_scores[i] += boost

    # Lấy nhiều ứng viên hơn vì đã trộn semantic + keyword boost
    candidate_count = min(top_k * max(candidate_multiplier, 1), len(laws))
    top_indices = final_scores.argsort()[-candidate_count:][::-1]

    # Lọc theo ngưỡng điểm và chỉ lấy top_k
    results = []
    logger.info("Tim kiem RAG cho cau hoi: %s...", question[:60])
    for i in top_indices:
        final_score = float(final_scores[i])
        if final_score >= score_threshold:
            law = laws[i].copy()
            law["_semantic_score"] = round(float(semantic_scores[i]), 4)
            law["_keyword_score"] = round(float(keyword_scores[i]), 4)
            law["_final_score"] = round(final_score, 4)
            results.append(law)
            logger.info(
                "[%.4f|semantic %.4f] %s - %s: %s",
                final_score,
                semantic_scores[i],
                law["law_name"],
                law["article"],
                law["title"][:50],
            )
        if len(results) >= top_k:
            break

    if not results:
        logger.warning("Khong co ket qua nao vuot nguong %.2f", score_threshold)

    logger.info("Tra ve %s dieu luat lien quan.", len(results))
    return results


def warmup() -> None:
    _ensure_embeddings_loaded()
