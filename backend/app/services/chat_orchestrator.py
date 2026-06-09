import logging
import time

from app.config import settings
from app.services.gemini_service import ask_gemini
from app.services.crag_evaluator import CragEvaluator
from app.services.reasoning_service import run_rat_lite_retrieval, run_standard_retrieval
from app.services.router import IntentRouter

logger = logging.getLogger(__name__)

_intent_router = IntentRouter()
_crag_evaluator = CragEvaluator()


def _build_source(law: dict) -> dict:
    content = (law.get("content") or "").strip()
    return {
        "source": law.get("source"),
        "law_name": law.get("law_name"),
        "article": law.get("article"),
        "title": law.get("title"),
        "excerpt": content[:500],
        "score": {
            "semantic_score": law.get("_semantic_score"),
            "keyword_score": law.get("_keyword_score"),
            "final_score": law.get("_final_score"),
        },
        "matched_steps": law.get("_matched_step_titles") or [],
    }


def handle_chat(question: str, request_id: str) -> dict:
    total_start = time.perf_counter()
    intent = _intent_router.route(question)
    reasoning_mode = "rat_lite" if intent.label == "COMPLEX" else "standard_rag"

    retrieval_start = time.perf_counter()
    if reasoning_mode == "rat_lite":
        reasoning = run_rat_lite_retrieval(question)
    else:
        reasoning = run_standard_retrieval(question)
    retrieval_ms = (time.perf_counter() - retrieval_start) * 1000.0
    evidence = reasoning["evidence"]
    logger.info(
        "Reasoning mode=%s router=%s retrieved=%s in %.0fms",
        reasoning["mode"],
        intent.provider,
        len(evidence),
        retrieval_ms,
    )

    crag = _crag_evaluator.evaluate(evidence) if settings.CRAG_ENABLED else None

    if not evidence:
        return {
            "answer": "Không tìm thấy căn cứ pháp lý phù hợp trong dữ liệu hiện có.",
            "sources": [],
            "meta": {
                "request_id": request_id,
                "model": settings.MODEL_NAME,
                "reasoning_mode": reasoning["mode"],
                "intent_router": {
                    "label": intent.label,
                    "provider": intent.provider,
                    "fallback_used": intent.fallback_used,
                    "reasons": intent.reasons,
                },
                "reasoning": {
                    "complexity_score": reasoning["assessment"].score,
                    "complexity_reasons": reasoning["assessment"].reasons,
                    "steps": reasoning["plan"],
                },
                "crag": {
                    "label": crag.label if crag else "SKIPPED",
                    "top_score": crag.top_score if crag else None,
                    "average_score": crag.average_score if crag else None,
                    "refined_count": len(crag.refined_chunks) if crag else 0,
                },
                "rag": {"retrieved_count": 0, "top_k": settings.RAG_TOP_K},
                "timings_ms": {
                    "retrieval": round(retrieval_ms, 2),
                    "total": round((time.perf_counter() - total_start) * 1000.0, 2),
                },
            },
        }

    if crag and crag.label == "INCORRECT":
        return {
            "answer": "Không tìm thấy căn cứ pháp lý đủ tin cậy trong dữ liệu hiện có để trả lời câu hỏi này.",
            "sources": [_build_source(law) for law in evidence],
            "meta": {
                "request_id": request_id,
                "model": settings.MODEL_NAME,
                "reasoning_mode": reasoning["mode"],
                "intent_router": {
                    "label": intent.label,
                    "provider": intent.provider,
                    "fallback_used": intent.fallback_used,
                    "reasons": intent.reasons,
                },
                "reasoning": {
                    "complexity_score": reasoning["assessment"].score,
                    "complexity_reasons": reasoning["assessment"].reasons,
                    "steps": reasoning["plan"],
                },
                "crag": {
                    "label": crag.label,
                    "top_score": crag.top_score,
                    "average_score": crag.average_score,
                    "refined_count": len(crag.refined_chunks),
                },
                "rag": {"retrieved_count": len(evidence), "top_k": settings.RAG_TOP_K},
                "timings_ms": {
                    "retrieval": round(retrieval_ms, 2),
                    "total": round((time.perf_counter() - total_start) * 1000.0, 2),
                },
            },
        }

    llm_start = time.perf_counter()
    answer = ask_gemini(
        question,
        evidence,
        reasoning_steps=reasoning["plan"],
        refined_context=crag.refined_context if crag else None,
    )
    llm_ms = (time.perf_counter() - llm_start) * 1000.0
    logger.info("LLM synthesis ok in %.0fms", llm_ms)

    return {
        "answer": answer,
        "sources": [_build_source(law) for law in evidence],
        "meta": {
            "request_id": request_id,
            "model": settings.MODEL_NAME,
            "reasoning_mode": reasoning["mode"],
            "intent_router": {
                "label": intent.label,
                "provider": intent.provider,
                "fallback_used": intent.fallback_used,
                "reasons": intent.reasons,
            },
            "reasoning": {
                "complexity_score": reasoning["assessment"].score,
                "complexity_reasons": reasoning["assessment"].reasons,
                "steps": reasoning["plan"],
            },
            "crag": {
                "label": crag.label if crag else "SKIPPED",
                "top_score": crag.top_score if crag else None,
                "average_score": crag.average_score if crag else None,
                "refined_count": len(crag.refined_chunks) if crag else 0,
            },
            "rag": {"retrieved_count": len(evidence), "top_k": settings.RAG_TOP_K},
            "timings_ms": {
                "retrieval": round(retrieval_ms, 2),
                "llm": round(llm_ms, 2),
                "total": round((time.perf_counter() - total_start) * 1000.0, 2),
            },
        },
    }
