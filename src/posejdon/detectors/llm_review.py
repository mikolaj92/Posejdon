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
    """Host-supplied LLM interface; Posejdon provides no runtime or default client.

    Implementations must report unavailability explicitly and propagate request
    failures, not return empty success responses or switch to another client.
    """

    def probe_availability(self) -> LLMRuntimeAvailability:
        """Report runtime readiness; unavailable runtimes must not report ready."""
        raise NotImplementedError("Host provider must implement probe_availability")

    def provider_id(self) -> str:
        """Return the stable provider identifier used for cache keys."""
        raise NotImplementedError("Host provider must implement provider_id")

    def runtime_model_id(self) -> str:
        """Return the concrete runtime model identifier used for requests."""
        raise NotImplementedError("Host provider must implement runtime_model_id")

    def review(
        self,
        *,
        text_window: str,
        entities: list[SensitiveEntity],
        allowed_entity_types: list[str],
    ) -> LLMReviewResponse:
        """Return structured adjudication suggestions or raise on request failure."""
        raise NotImplementedError("Host provider must implement review")

    def verify_anonymization(
        self,
        *,
        output_segments: list[LLMVerificationWindowEntry],
        allowed_entity_types: list[str],
    ) -> LLMVerificationResponse:
        """Return segment-level verification outcomes or raise on request failure."""
        raise NotImplementedError("Host provider must implement verify_anonymization")


__all__ = [
    "LLMReviewResponse",
    "LLMReviewSuggestion",
    "LLMRuntimeAvailability",
    "LLMVerificationResponse",
    "LocalLLMProvider",
]
