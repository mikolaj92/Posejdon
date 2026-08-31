from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from posejdon.domain.entities import SensitiveEntity
from posejdon.domain.models import LLMVerificationWindowEntry
from posejdon.domain.reports import SegmentLeakageFinding


class LLMReviewSuggestion(BaseModel):
    entity_id: str
    action: str = Field(pattern="^(keep|drop|extend_left|extend_right|relabel)$")
    replacement_entity_type: str | None = None
    reason: str


class LLMReviewResponse(BaseModel):
    suggestions: list[LLMReviewSuggestion] = Field(default_factory=list)


class LLMVerificationResponse(BaseModel):
    suspected_leaks: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    findings_by_segment: list[SegmentLeakageFinding] = Field(default_factory=list)
    verified_segment_ids: list[str] = Field(default_factory=list)


class LLMRuntimeAvailability(BaseModel):
    reachable: bool = False
    model_available: bool = False
    warnings: list[str] = Field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.reachable and self.model_available


class LocalLLMProvider(Protocol):
    def probe_availability(self) -> LLMRuntimeAvailability:
        """Return whether the provider runtime is ready for use."""
        ...

    def provider_id(self) -> str:
        """Return the stable provider identifier used for cache keys."""
        ...

    def runtime_model_id(self) -> str:
        """Return the concrete runtime model identifier used for requests."""
        ...

    def review(
        self,
        *,
        text_window: str,
        entities: list[SensitiveEntity],
        allowed_entity_types: list[str],
    ) -> LLMReviewResponse:
        """Return structured adjudication suggestions."""
        ...

    def verify_anonymization(
        self,
        *,
        output_segments: list[LLMVerificationWindowEntry],
        allowed_entity_types: list[str],
    ) -> LLMVerificationResponse:
        """Return segment-level leakage verification outcomes."""
        ...


__all__ = [
    "LLMReviewResponse",
    "LLMReviewSuggestion",
    "LLMRuntimeAvailability",
    "LLMVerificationResponse",
    "LocalLLMProvider",
]
