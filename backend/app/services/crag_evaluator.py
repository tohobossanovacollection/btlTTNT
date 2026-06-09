import re
from dataclasses import dataclass

from app.config import settings


@dataclass
class CragEvaluationResult:
    label: str
    top_score: float
    average_score: float
    refined_chunks: list[dict]
    refined_context: str


def _clean_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = text.replace("�", "")
    return text


def _refine_chunk(chunk: dict) -> dict:
    refined = {
        "law_name": _clean_text(chunk.get("law_name", "")),
        "article": _clean_text(chunk.get("article", "")),
        "content": _clean_text(chunk.get("content", "")),
    }
    if chunk.get("_final_score") is not None:
        refined["_final_score"] = chunk.get("_final_score")
    if chunk.get("_semantic_score") is not None:
        refined["_semantic_score"] = chunk.get("_semantic_score")
    if chunk.get("_keyword_score") is not None:
        refined["_keyword_score"] = chunk.get("_keyword_score")
    if chunk.get("_matched_step_titles"):
        refined["_matched_step_titles"] = list(chunk.get("_matched_step_titles") or [])
    return refined


class CragEvaluator:
    def evaluate(self, chunks: list[dict]) -> CragEvaluationResult:
        scores = [float(chunk.get("_final_score") or 0.0) for chunk in chunks]
        if not scores:
            return CragEvaluationResult(
                label="INCORRECT",
                top_score=0.0,
                average_score=0.0,
                refined_chunks=[],
                refined_context="",
            )

        top_score = max(scores)
        average_score = sum(scores) / len(scores)

        if top_score > settings.CRAG_CORRECT_THRESHOLD:
            label = "CORRECT"
        elif top_score >= settings.CRAG_AMBIGUOUS_THRESHOLD:
            label = "AMBIGUOUS"
        else:
            label = "INCORRECT"

        refined_chunks = [_refine_chunk(chunk) for chunk in chunks]
        refined_context = "\n\n".join(
            f"{chunk.get('law_name', 'Khong ro van ban')} - {chunk.get('article', 'Khong ro dieu')}\n{chunk.get('content', '')}"
            for chunk in refined_chunks
            if chunk.get("content")
        )

        return CragEvaluationResult(
            label=label,
            top_score=round(top_score, 4),
            average_score=round(average_score, 4),
            refined_chunks=refined_chunks,
            refined_context=refined_context,
        )

