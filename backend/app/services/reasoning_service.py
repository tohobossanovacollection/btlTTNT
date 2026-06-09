import logging
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from app.config import settings
from app.services.retrieval_service import retrieve_laws_semantic

logger = logging.getLogger(__name__)


@dataclass
class ComplexityAssessment:
    score: int
    is_complex: bool
    reasons: list[str]


@dataclass
class ReasoningStep:
    step_id: str
    title: str
    query: str


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", str(value or ""))
    without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_accents.replace("đ", "d").replace("Đ", "D").lower()


def assess_question_complexity(question: str) -> ComplexityAssessment:
    normalized = _normalize_text(question)
    reasons: list[str] = []
    score = 0

    connectors = [
        "neu",
        "truong hop",
        "dong thoi",
        "tuy nhien",
        "nhung",
        "ngoai le",
        "hoac",
        "vua",
        "vua",
        "bao gom",
    ]
    if any(term in normalized for term in connectors):
        score += 2
        reasons.append("co_nhieu_menh_de")

    legal_conditions = [
        "dieu kien",
        "mien",
        "giam",
        "khau tru",
        "uu dai",
        "xu phat",
        "cham nop",
        "hoan thue",
        "quyet toan",
    ]
    matched_conditions = sum(1 for term in legal_conditions if term in normalized)
    if matched_conditions >= 2:
        score += 1
        reasons.append("co_nhieu_dieu_kien_phap_ly")

    clause_count = len([part for part in re.split(r"[;,]| va | voi dieu kien | trong truong hop ", normalized) if part.strip()])
    if clause_count >= 3:
        score += 1
        reasons.append("cau_hoi_da_menh_de")

    if len(question.strip()) >= settings.RAT_MIN_QUESTION_LENGTH:
        score += 1
        reasons.append("cau_hoi_dai")

    if "?" in question and question.count("?") > 1:
        score += 1
        reasons.append("nhieu_tieu_cau_hoi")

    return ComplexityAssessment(
        score=score,
        is_complex=bool(settings.RAT_ENABLED and score >= settings.RAT_COMPLEXITY_THRESHOLD),
        reasons=reasons,
    )


def _infer_focus_keywords(question: str) -> list[str]:
    normalized = _normalize_text(question)
    mapping = [
        ("thue thu nhap ca nhan", ["tncn", "thu nhap ca nhan", "giam tru", "luong", "tien cong"]),
        ("thue thu nhap doanh nghiep", ["tndn", "thu nhap doanh nghiep", "chi phi duoc tru", "uu dai thue"]),
        ("thue gia tri gia tang", ["gtgt", "vat", "gia tri gia tang", "khau tru"]),
        ("hoa don chung tu", ["hoa don", "chung tu", "xuat hoa don"]),
        ("xu phat va quan ly thue", ["xu phat", "cham nop", "tron thue", "quan ly thue"]),
    ]

    keywords: list[str] = []
    for label, terms in mapping:
        if any(term in normalized for term in terms):
            keywords.append(label)
    return keywords


def _split_question_fragments(question: str) -> list[str]:
    candidates = re.split(
        r"\bnhung\b|\btuy nhien\b|\bneu\b|\btruong hop\b|\bdong thoi\b|;|,|\bhoac\b",
        _normalize_text(question),
    )
    fragments = [fragment.strip() for fragment in candidates if len(fragment.strip()) >= 20]
    deduped: list[str] = []
    for fragment in fragments:
        if fragment not in deduped:
            deduped.append(fragment)
    return deduped


@lru_cache(maxsize=256)
def _cached_plan(question: str, max_steps: int) -> tuple[tuple[str, str, str], ...]:
    normalized_question = " ".join(question.strip().split())
    focus_keywords = _infer_focus_keywords(normalized_question)
    fragments = _split_question_fragments(normalized_question)

    plan: list[ReasoningStep] = [
        ReasoningStep(
            step_id="s1",
            title="Xac dinh van de phap ly trung tam",
            query=normalized_question,
        )
    ]

    if focus_keywords:
        plan.append(
            ReasoningStep(
                step_id=f"s{len(plan) + 1}",
                title="Tim can cu theo sac thue hoac nhom nghiep vu",
                query=f"{normalized_question}. Tap trung vao: {', '.join(focus_keywords)}",
            )
        )

    if any(term in _normalize_text(normalized_question) for term in ["dieu kien", "mien", "giam", "khau tru", "uu dai", "neu", "truong hop"]):
        plan.append(
            ReasoningStep(
                step_id=f"s{len(plan) + 1}",
                title="Kiem tra dieu kien, ngoai le va truong hop ap dung",
                query=f"dieu kien, ngoai le, truong hop ap dung cho van de sau: {normalized_question}",
            )
        )

    for fragment in fragments[:max(0, max_steps - len(plan) - 1)]:
        plan.append(
            ReasoningStep(
                step_id=f"s{len(plan) + 1}",
                title="Doi chieu tung menh de trong cau hoi",
                query=fragment,
            )
        )

    if len(plan) < max_steps:
        plan.append(
            ReasoningStep(
                step_id=f"s{len(plan) + 1}",
                title="Tim can cu de ket luan",
                query=f"can cu ket luan truc tiep cho cau hoi: {normalized_question}",
            )
        )

    trimmed = plan[:max_steps]
    return tuple((step.step_id, step.title, step.query) for step in trimmed)


def build_reasoning_plan(question: str) -> list[ReasoningStep]:
    tuples = _cached_plan(" ".join(question.strip().split()), settings.RAT_MAX_STEPS)
    return [ReasoningStep(step_id=step_id, title=title, query=query) for step_id, title, query in tuples]


def run_standard_retrieval(question: str, assessment: ComplexityAssessment | None = None) -> dict:
    current_assessment = assessment or assess_question_complexity(question)
    evidence = retrieve_laws_semantic(question, top_k=settings.RAG_TOP_K)
    return {
        "mode": "standard_rag",
        "assessment": current_assessment,
        "plan": [],
        "evidence": evidence,
    }


def run_rat_lite_retrieval(question: str, assessment: ComplexityAssessment | None = None) -> dict:
    current_assessment = assessment or assess_question_complexity(question)
    plan = build_reasoning_plan(question)

    aggregated: dict[tuple[str, str, str], dict] = {}
    step_summaries: list[dict] = []

    logger.info("RAT-lite enabled for question: %s", question[:80])
    for step in plan:
        step_hits = retrieve_laws_semantic(step.query, top_k=settings.RAT_STEP_TOP_K)
        step_summaries.append(
            {
                "step_id": step.step_id,
                "title": step.title,
                "query": step.query,
                "retrieved_count": len(step_hits),
                "top_score": step_hits[0].get("_final_score") if step_hits else None,
            }
        )
        for hit in step_hits:
            key = (
                str(hit.get("source") or ""),
                str(hit.get("law_name") or ""),
                str(hit.get("article") or ""),
            )
            existing = aggregated.get(key)
            if existing is None:
                law = hit.copy()
                law["_matched_steps"] = [step.step_id]
                law["_matched_step_titles"] = [step.title]
                aggregated[key] = law
                continue

            if float(hit.get("_final_score") or 0.0) > float(existing.get("_final_score") or 0.0):
                existing.update(hit)
            if step.step_id not in existing["_matched_steps"]:
                existing["_matched_steps"].append(step.step_id)
            if step.title not in existing["_matched_step_titles"]:
                existing["_matched_step_titles"].append(step.title)

    evidence = sorted(
        aggregated.values(),
        key=lambda item: (
            float(item.get("_final_score") or 0.0),
            len(item.get("_matched_steps") or []),
        ),
        reverse=True,
    )[: settings.RAG_TOP_K]

    if not evidence:
        logger.warning("RAT-lite khong tim thay bang chung, fallback sang standard RAG")
        return run_standard_retrieval(question, assessment=current_assessment)

    return {
        "mode": "rat_lite",
        "assessment": current_assessment,
        "plan": step_summaries,
        "evidence": evidence,
    }


def run_reasoning_retrieval(question: str, force_mode: str | None = None) -> dict:
    assessment = assess_question_complexity(question)
    if force_mode == "rat_lite":
        return run_rat_lite_retrieval(question, assessment=assessment)
    if force_mode == "standard_rag":
        return run_standard_retrieval(question, assessment=assessment)
    if assessment.is_complex:
        return run_rat_lite_retrieval(question, assessment=assessment)
    return run_standard_retrieval(question, assessment=assessment)
