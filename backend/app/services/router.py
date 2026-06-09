import logging
from dataclasses import dataclass

from app.config import settings
from app.services.gemini_service import GeminiError, classify_query_intent
from app.services.reasoning_service import assess_question_complexity

logger = logging.getLogger(__name__)


@dataclass
class IntentRouteResult:
    label: str
    provider: str
    fallback_used: bool
    reasons: list[str]


class IntentRouter:
    def route(self, query: str) -> IntentRouteResult:
        normalized = str(query or "").strip()
        if not normalized:
            return IntentRouteResult(
                label="SIMPLE",
                provider="fallback",
                fallback_used=True,
                reasons=["empty_query"],
            )

        if settings.ROUTER_ENABLED:
            try:
                label = classify_query_intent(
                    normalized,
                    max_output_tokens=settings.ROUTER_MAX_OUTPUT_TOKENS,
                )
                if label in {"SIMPLE", "COMPLEX"}:
                    return IntentRouteResult(
                        label=label,
                        provider="gemini",
                        fallback_used=False,
                        reasons=["llm_router"],
                    )
            except GeminiError as exc:
                logger.warning("IntentRouter fallback because Gemini classification failed: %s", str(exc))

        assessment = assess_question_complexity(normalized)
        label = "COMPLEX" if assessment.is_complex else "SIMPLE"
        return IntentRouteResult(
            label=label,
            provider="heuristic",
            fallback_used=True,
            reasons=assessment.reasons or ["heuristic_router"],
        )

