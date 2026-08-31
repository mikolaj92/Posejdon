from __future__ import annotations

import json
from typing import Protocol

from pydantic import BaseModel, Field

from posejdon.core.errors import UnsafeProcessingError
from posejdon.domain.entities import SensitiveEntity
from posejdon.domain.models import LLMVerificationWindowEntry
from posejdon.domain.reports import SegmentLeakageFinding
from posejdon.prompt_registry import PosejdonPromptRegistry


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMRequestMetadata(BaseModel):
    subsystem: str


class LLMRequest(BaseModel):
    messages: list[LLMMessage]
    max_tokens: int = 1024
    temperature: float = 0.7
    timeout_seconds: float = 60.0
    metadata: LLMRequestMetadata


class LLMResponse(BaseModel):
    content: str


class OpenAICompatibleClient(Protocol):
    """Injected completion client; Posejdon owns neither transport nor runtime config."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Complete a chat-style request using OpenAI-compatible semantics."""
        ...


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


class LLMReviewer:
    """Provider-blind optional review seam backed only by an injected client."""

    def __init__(self, client: OpenAICompatibleClient) -> None:
        self._client = client
        self._prompts = PosejdonPromptRegistry()

    def review(
        self,
        *,
        text_window: str,
        entities: list[SensitiveEntity],
        allowed_entity_types: list[str],
    ) -> LLMReviewResponse:
        prompt = self._prompts.render(
            "posejdon-review-sensitive-entities",
            {
                "text_window": text_window[:4000],
                "allowed_entity_types": allowed_entity_types,
                "entities": [entity.model_dump() for entity in entities],
            },
        )
        try:
            response = self._client.complete(self._request(prompt))
            return LLMReviewResponse.model_validate(self._extract_json(response.content))
        except Exception as exc:
            raise UnsafeProcessingError("LLM entity review failed") from exc

    def verify_anonymization(
        self,
        *,
        output_segments: list[LLMVerificationWindowEntry],
        allowed_entity_types: list[str],
    ) -> LLMVerificationResponse:
        segments = [
            {"segment_id": segment.segment_id, "text": segment.text} for segment in output_segments
        ]
        prompt = self._prompts.render(
            "posejdon-verify-document-anonymized-window",
            {
                "allowed_entity_types": allowed_entity_types,
                "segments": segments,
            },
        )
        try:
            response = self._client.complete(self._request(prompt))
            return LLMVerificationResponse.model_validate(self._extract_json(response.content))
        except Exception as exc:
            raise UnsafeProcessingError("LLM anonymization verification failed") from exc

    @staticmethod
    def _request(prompt: str) -> LLMRequest:
        return LLMRequest(
            messages=[LLMMessage(role="user", content=prompt)],
            max_tokens=512,
            temperature=0.0,
            metadata=LLMRequestMetadata(subsystem="posejdon"),
        )

    @staticmethod
    def _extract_json(output: str) -> dict:
        start = output.find("{")
        end = output.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("LLM response did not contain a JSON object")
        return json.loads(output[start : end + 1])
