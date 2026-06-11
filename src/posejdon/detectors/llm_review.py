from __future__ import annotations

import json
import subprocess
import sys
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


class MLXInternalProvider:
    def __init__(self, model_path: str) -> None:
        self.model_path = model_path

    def complete(self, request: LLMRequest) -> LLMResponse:
        prompt = "\n".join(f"{msg.role}: {msg.content}" for msg in request.messages)
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mlx_lm",
                    "generate",
                    "--model",
                    self.model_path,
                    "--prompt",
                    prompt,
                    "--max-tokens",
                    str(request.max_tokens or 1024),
                    "--temp",
                    str(request.temperature or 0.0),
                    "--verbose",
                    "false",
                ],
                capture_output=True,
                check=True,
                text=True,
                timeout=request.timeout_seconds,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"MLX generation failed: {exc.stderr}") from exc
        return LLMResponse(content=result.stdout)


class LLMGateway:
    def __init__(self, provider: MLXInternalProvider) -> None:
        self.provider = provider

    def complete(self, request: LLMRequest) -> LLMResponse:
        return self.provider.complete(request)


_PROMPT_REGISTRY = PosejdonPromptRegistry()


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
        """Return structured verification findings."""
        ...


class MLXProvider:
    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path

    def provider_id(self) -> str:
        return "mlx"

    def runtime_model_id(self) -> str:
        return self.model_path or "mlx-default"

    def _gateway(self) -> LLMGateway | None:
        if not self.model_path:
            return None
        return LLMGateway(provider=MLXInternalProvider(model_path=self.model_path))

    def review(
        self,
        *,
        text_window: str,
        entities: list[SensitiveEntity],
        allowed_entity_types: list[str],
    ) -> LLMReviewResponse:
        if not self.model_path:
            return LLMReviewResponse()
        prompt = _PROMPT_REGISTRY.render(
            "posejdon-review-sensitive-entities",
            {
                "text_window": text_window[:4000],
                "allowed_entity_types": allowed_entity_types,
                "entities": [entity.model_dump() for entity in entities],
            },
        )
        gateway = self._gateway()
        if gateway is None:
            return LLMReviewResponse()
        request = LLMRequest(
            messages=[LLMMessage(role="user", content=prompt)],
            max_tokens=512,
            temperature=0.0,
            metadata=LLMRequestMetadata(subsystem="posejdon"),
        )
        try:
            response = gateway.complete(request)
            payload = self._extract_json(response.content)
            return LLMReviewResponse.model_validate(payload)
        except Exception as exc:
            raise UnsafeProcessingError("MLX entity review failed") from exc

    def probe_availability(self) -> LLMRuntimeAvailability:
        if not self.model_path:
            return LLMRuntimeAvailability(
                warnings=["MLX model path is not configured."],
            )
        return LLMRuntimeAvailability(reachable=True, model_available=True)

    def verify_anonymization(
        self,
        *,
        output_segments: list[LLMVerificationWindowEntry],
        allowed_entity_types: list[str],
    ) -> LLMVerificationResponse:
        if not self.model_path:
            return LLMVerificationResponse(warnings=["MLX model path is not configured."])
        segments = [
            {"segment_id": segment.segment_id, "text": segment.text} for segment in output_segments
        ]
        prompt = _PROMPT_REGISTRY.render(
            "posejdon-verify-document-anonymized-window",
            {
                "allowed_entity_types": allowed_entity_types,
                "segments": segments,
            },
        )
        gateway = self._gateway()
        if gateway is None:
            return LLMVerificationResponse(warnings=["MLX model path is not configured."])
        request = LLMRequest(
            messages=[LLMMessage(role="user", content=prompt)],
            max_tokens=512,
            temperature=0.0,
            metadata=LLMRequestMetadata(subsystem="posejdon"),
        )
        try:
            response = gateway.complete(request)
            payload = self._extract_json(response.content)
            return LLMVerificationResponse.model_validate(payload)
        except Exception as exc:
            raise UnsafeProcessingError("MLX anonymization verification failed") from exc

    @staticmethod
    def _extract_json(output: str) -> dict:
        start = output.find("{")
        end = output.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {"suggestions": []}
        return json.loads(output[start : end + 1])
