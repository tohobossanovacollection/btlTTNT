"""Compatibility wrapper for the legacy LLM module path."""

from app.services.groq_service import (
    GroqServiceError as GeminiError,
    ask_groq as ask_gemini,
    classify_query_intent,
    self_reflect_answer,
)

__all__ = [
    "GeminiError",
    "ask_gemini",
    "classify_query_intent",
    "self_reflect_answer",
]
