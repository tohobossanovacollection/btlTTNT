import logging
import time

from app.config import settings
from app.services.gemini_service import ask_gemini
from app.services.reasoning_service import run_rat_lite_retrieval, run_standard_retrieval
from app.services.router import IntentRouter
from app.services.self_reflection_evaluator import SelfReflectionEvaluator

logger = logging.getLogger(__name__)

_intent_router = IntentRouter()
_self_reflection_evaluator = SelfReflectionEvaluator()


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

    loop_limit = max(0, int(settings.SELF_RAG_MAX_LOOPS or 0))
    support_retry_limit = max(0, int(settings.SELF_RAG_SUPPORT_MAX_RETRIES or 0))
    total_retrieval_ms = 0.0
    total_llm_ms = 0.0
    support_retries_used = 0
    loop_used = 0

    final_reasoning: dict | None = None
    final_evidence: list[dict] = []
    final_answer = ""
    final_reflection = None

    for attempt in range(loop_limit + 1):
        loop_used = attempt
        current_mode = "rat_lite" if attempt > 0 else reasoning_mode
        retrieval_start = time.perf_counter()
        if current_mode == "rat_lite":
            reasoning = run_rat_lite_retrieval(question)
        else:
            reasoning = run_standard_retrieval(question)
        retrieval_ms = (time.perf_counter() - retrieval_start) * 1000.0
        total_retrieval_ms += retrieval_ms
        evidence = reasoning["evidence"]
        final_reasoning = reasoning
        final_evidence = evidence

        logger.info(
            "Reasoning mode=%s router=%s retrieved=%s in %.0fms",
            reasoning["mode"],
            intent.provider,
            len(evidence),
            retrieval_ms,
        )

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
                    "self_reflection": {
                        "enabled": settings.SELF_RAG_ENABLED,
                        "is_relevant": False,
                        "is_supported": False,
                        "is_useful": False,
                        "relevance_score": 0.0,
                        "support_retries": 0,
                        "loops_used": loop_used,
                    },
                    "rag": {"retrieved_count": 0, "top_k": settings.RAG_TOP_K},
                    "timings_ms": {
                        "retrieval": round(total_retrieval_ms, 2),
                        "llm": round(total_llm_ms, 2),
                        "total": round((time.perf_counter() - total_start) * 1000.0, 2),
                    },
                },
            }

        extra_instructions = ""
        llm_start = time.perf_counter()
        answer = ask_gemini(
            question,
            evidence,
            reasoning_steps=reasoning["plan"],
            refined_context=None,
            extra_instructions=extra_instructions,
        )
        llm_ms = (time.perf_counter() - llm_start) * 1000.0
        total_llm_ms += llm_ms
        logger.info("LLM synthesis ok in %.0fms", llm_ms)

        reflection = (
            _self_reflection_evaluator.evaluate(question, evidence, answer)
            if settings.SELF_RAG_ENABLED
            else None
        )
        final_answer = answer
        final_reflection = reflection

        if reflection and not reflection.is_relevant:
            return {
                "answer": "Không tìm thấy căn cứ pháp lý phù hợp trong dữ liệu hiện có.",
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
                    "self_reflection": {
                        "enabled": settings.SELF_RAG_ENABLED,
                        "is_relevant": reflection.is_relevant,
                        "is_supported": reflection.is_supported,
                        "is_useful": reflection.is_useful,
                        "relevance_score": reflection.relevance_score,
                        "support_feedback": reflection.support_feedback,
                        "usefulness_feedback": reflection.usefulness_feedback,
                        "support_retries": support_retries_used,
                        "loops_used": loop_used,
                    },
                    "rag": {"retrieved_count": len(evidence), "top_k": settings.RAG_TOP_K},
                    "timings_ms": {
                        "retrieval": round(total_retrieval_ms, 2),
                        "llm": round(total_llm_ms, 2),
                        "total": round((time.perf_counter() - total_start) * 1000.0, 2),
                    },
                },
            }

        while (
            reflection
            and not reflection.is_supported
            and support_retries_used < support_retry_limit
        ):
            support_retries_used += 1
            unsupported_claims = reflection.support_feedback.get("unsupported_claims") if reflection else []
            unsupported_text = ""
            if unsupported_claims:
                unsupported_text = "\n- " + "\n- ".join(str(item) for item in unsupported_claims[:6])
            extra_instructions = (
                "Phiên bản trước có các khẳng định chưa được hỗ trợ bởi căn cứ pháp lý."
                " Hãy trả lời lại CHỈ dựa trên căn cứ đã cho; nếu thiếu thông tin thì nói thiếu."
                f"\nCác khẳng định cần tránh:{unsupported_text}"
            )
            llm_start = time.perf_counter()
            answer = ask_gemini(
                question,
                evidence,
                reasoning_steps=reasoning["plan"],
                refined_context=None,
                extra_instructions=extra_instructions,
            )
            llm_ms = (time.perf_counter() - llm_start) * 1000.0
            total_llm_ms += llm_ms
            reflection = _self_reflection_evaluator.evaluate(question, evidence, answer)
            final_answer = answer
            final_reflection = reflection

        if not reflection or (reflection.is_supported and reflection.is_useful):
            break
        if attempt >= loop_limit:
            break

        improvement = ""
        if reflection and reflection.usefulness_feedback:
            improvement = (reflection.usefulness_feedback.get("improvement_suggestions") or "").strip()
        if improvement:
            logger.info("Self-RAG loop triggered: %s", improvement[:120])

    if final_reasoning is None:
        final_reasoning = run_standard_retrieval(question)

    return {
        "answer": final_answer,
        "sources": [_build_source(law) for law in final_evidence],
        "meta": {
            "request_id": request_id,
            "model": settings.MODEL_NAME,
            "reasoning_mode": final_reasoning["mode"],
            "intent_router": {
                "label": intent.label,
                "provider": intent.provider,
                "fallback_used": intent.fallback_used,
                "reasons": intent.reasons,
            },
            "reasoning": {
                "complexity_score": final_reasoning["assessment"].score,
                "complexity_reasons": final_reasoning["assessment"].reasons,
                "steps": final_reasoning["plan"],
            },
            "self_reflection": (
                {
                    "enabled": settings.SELF_RAG_ENABLED,
                    "is_relevant": final_reflection.is_relevant,
                    "is_supported": final_reflection.is_supported,
                    "is_useful": final_reflection.is_useful,
                    "relevance_score": final_reflection.relevance_score,
                    "support_feedback": final_reflection.support_feedback,
                    "usefulness_feedback": final_reflection.usefulness_feedback,
                    "support_retries": support_retries_used,
                    "loops_used": loop_used,
                }
                if final_reflection
                else {"enabled": False}
            ),
            "rag": {"retrieved_count": len(final_evidence), "top_k": settings.RAG_TOP_K},
            "timings_ms": {
                "retrieval": round(total_retrieval_ms, 2),
                "llm": round(total_llm_ms, 2),
                "total": round((time.perf_counter() - total_start) * 1000.0, 2),
            },
        },
    }
