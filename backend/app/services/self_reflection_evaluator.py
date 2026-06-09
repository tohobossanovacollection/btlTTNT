import re
import unicodedata
from dataclasses import dataclass

from app.config import settings
from app.services.gemini_service import GeminiError, self_reflect_answer


@dataclass
class SelfReflectionResult:
    is_relevant: bool
    is_supported: bool
    is_useful: bool
    relevance_score: float
    support_feedback: dict
    usefulness_feedback: dict


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", str(value or ""))
    without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_accents.replace("đ", "d").replace("Đ", "D").lower()


def _tokenize(value: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", _normalize_text(value))
    return {token for token in tokens if len(token) >= 2}


def _context_from_chunks(chunks: list[dict]) -> str:
    blocks: list[str] = []
    for chunk in chunks:
        law_name = chunk.get("law_name") or "Khong ro van ban"
        article = chunk.get("article") or "Khong ro dieu"
        content = (chunk.get("content") or "").strip()
        if not content:
            continue
        blocks.append(f"{law_name} - {article}\n{content}")
    return "\n\n".join(blocks).strip()


class SelfReflectionEvaluator:
    def evaluate(self, question: str, chunks: list[dict], answer: str) -> SelfReflectionResult:
        scores = [float(chunk.get("_final_score") or 0.0) for chunk in chunks]
        top_score = max(scores) if scores else 0.0
        relevance_threshold = float(settings.SELF_RAG_RELEVANCE_THRESHOLD)

        question_tokens = _tokenize(question)
        overlap_scores: list[float] = []
        for chunk in chunks[: max(1, min(len(chunks), 6))]:
            text = chunk.get("text") or chunk.get("content") or ""
            if not text:
                continue
            chunk_tokens = _tokenize(text)
            if not question_tokens or not chunk_tokens:
                continue
            overlap_scores.append(len(question_tokens & chunk_tokens) / max(len(question_tokens), 1))
        overlap = max(overlap_scores) if overlap_scores else 0.0
        relevance_score = round(max(top_score, overlap), 4)
        is_relevant = bool(chunks and relevance_score >= relevance_threshold)

        support_feedback: dict = {}
        usefulness_feedback: dict = {}
        is_supported = True
        is_useful = True

        if settings.SELF_RAG_ENABLED and settings.SELF_RAG_SUPPORT_ENABLED and chunks:
            try:
                context = _context_from_chunks(chunks)
                data = self_reflect_answer(question, answer, context)
                support_feedback = {
                    "is_supported": bool(data.get("is_supported")),
                    "unsupported_claims": data.get("unsupported_claims") or [],
                }
                usefulness_feedback = {
                    "is_useful": bool(data.get("is_useful")),
                    "missing_points": data.get("missing_points") or [],
                    "improvement_suggestions": (data.get("improvement_suggestions") or "").strip(),
                }
                is_supported = bool(data.get("is_supported", True))
                is_useful = bool(data.get("is_useful", True))
            except GeminiError:
                support_feedback = {"skipped": True, "reason": "llm_unavailable"}
                usefulness_feedback = {"skipped": True, "reason": "llm_unavailable"}

        if settings.SELF_RAG_ENABLED and settings.SELF_RAG_USEFULNESS_ENABLED and chunks:
            if "is_useful" in usefulness_feedback:
                is_useful = bool(usefulness_feedback.get("is_useful"))

        return SelfReflectionResult(
            is_relevant=is_relevant,
            is_supported=is_supported,
            is_useful=is_useful,
            relevance_score=relevance_score,
            support_feedback=support_feedback,
            usefulness_feedback=usefulness_feedback,
        )

