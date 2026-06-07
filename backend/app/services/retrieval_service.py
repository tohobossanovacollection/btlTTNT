import numpy as np
import threading
import unicodedata
from app.services.law_retriever import load_all_laws
from app.services.embedding_service import embed_texts

# Load luật 1 lần duy nhất khi server khởi động
LAWS = None

# Dùng trường "text" (giàu ngữ cảnh) để embedding, không dùng "content"
LAW_TEXTS = None
LAW_EMBEDDINGS = None
_LAWS_LOCK = threading.Lock()
_EMBEDDINGS_LOCK = threading.Lock()

# Ngưỡng tối thiểu: chỉ lấy kết quả có độ tương đồng >= 0.30
SCORE_THRESHOLD = 0.30


def _ensure_laws_loaded() -> list:
    global LAWS, LAW_TEXTS

    if LAWS is not None and LAW_TEXTS is not None:
        return LAWS

    with _LAWS_LOCK:
        if LAWS is None:
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
            print(f"⏳ Đang tạo embeddings cho {len(laws)} phân đoạn luật...")
            LAW_EMBEDDINGS = embed_texts(LAW_TEXTS)
            print("✅ Embeddings sẵn sàng!")

    return LAW_EMBEDDINGS


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", str(value or ""))
    without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    without_accents = without_accents.replace("đ", "d").replace("Đ", "D")
    return without_accents.lower()


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

    # Embed câu hỏi
    question_embedding = embed_texts([question])[0]

    # Tính cosine similarity (dot product với vector đã normalize)
    semantic_scores = np.dot(law_embeddings, question_embedding)
    scores = semantic_scores.copy()
    for i, law in enumerate(laws):
        scores[i] += _keyword_boost(question, law)

    # Lấy nhiều ứng viên hơn vì đã trộn semantic + keyword boost
    candidate_count = min(top_k * 8, len(laws))
    top_indices = scores.argsort()[-candidate_count:][::-1]

    # Lọc theo ngưỡng điểm và chỉ lấy top_k
    results = []
    print(f"\n🔍 Tìm kiếm: '{question[:60]}...'")
    for i in top_indices:
        score = float(scores[i])
        if score >= SCORE_THRESHOLD:
            law = laws[i].copy()
            law["_score"] = round(score, 4)
            law["_semantic_score"] = round(float(semantic_scores[i]), 4)
            results.append(law)
            print(
                f"  ✅ [{score:.4f}|semantic {semantic_scores[i]:.4f}] "
                f"{law['law_name']} — {law['article']}: {law['title'][:50]}"
            )
        if len(results) >= top_k:
            break

    if not results:
        print(f"  ⚠️  Không có kết quả nào vượt ngưỡng {SCORE_THRESHOLD}")

    print(f"  → Trả về {len(results)} điều luật liên quan\n")
    return results
