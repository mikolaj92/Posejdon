from __future__ import annotations

from collections.abc import Sequence

from posejdon.detectors.llm_review import (
    LLMReviewResponse,
    LLMRuntimeAvailability,
    LLMVerificationResponse,
    LocalLLMProvider,
)
from posejdon.domain.entities import SensitiveEntity
from posejdon.domain.models import LLMVerificationWindowEntry


class FakeInjectedLLMProvider:
    def probe_availability(self) -> LLMRuntimeAvailability:
        return LLMRuntimeAvailability(reachable=True, model_available=True)

    def provider_id(self) -> str:
        return "fake_provider"

    def runtime_model_id(self) -> str:
        return "fake_model"

    def review(
        self,
        *,
        text_window: str,
        entities: Sequence[SensitiveEntity] | list[SensitiveEntity],
        allowed_entity_types: Sequence[str] | list[str],
    ) -> LLMReviewResponse:
        return LLMReviewResponse()

    def verify_anonymization(
        self,
        *,
        output_segments: Sequence[LLMVerificationWindowEntry] | list[LLMVerificationWindowEntry],
        allowed_entity_types: Sequence[str] | list[str],
    ) -> LLMVerificationResponse:
        return LLMVerificationResponse()


def test_injected_llm_provider_satisfies_protocol() -> None:
    provider: LocalLLMProvider = FakeInjectedLLMProvider()
    assert provider.provider_id() == "fake_provider"
    assert provider.probe_availability().ready is True
