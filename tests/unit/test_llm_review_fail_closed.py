from __future__ import annotations

import pytest

from posejdon.core.errors import UnsafeProcessingError
from posejdon.detectors.llm_review import MLXProvider


class _FailingGateway:
    def complete(self, request):
        raise RuntimeError("provider failed")


def test_missing_model_configuration_fails_closed() -> None:
    provider = MLXProvider()

    with pytest.raises(UnsafeProcessingError, match="model path is not configured"):
        provider.runtime_model_id()
    with pytest.raises(UnsafeProcessingError, match="model path is not configured"):
        provider.review(text_window="text", entities=[], allowed_entity_types=[])
    with pytest.raises(UnsafeProcessingError, match="model path is not configured"):
        provider.verify_anonymization(output_segments=[], allowed_entity_types=[])


def test_probe_reports_missing_runtime_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = MLXProvider(model_path="local-model")
    monkeypatch.setattr("posejdon.detectors.llm_review.find_spec", lambda name: None)

    availability = provider.probe_availability()

    assert availability.ready is False
    assert availability.model_available is True
    assert availability.warnings == ["MLX runtime dependency 'mlx_lm' is not installed."]


def test_response_without_json_is_rejected() -> None:
    with pytest.raises(ValueError, match="did not contain a JSON object"):
        MLXProvider._extract_json("generation completed without structured output")


def test_review_provider_failure_raises_unsafe_processing(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = MLXProvider(model_path="local-model")
    monkeypatch.setattr(provider, "_gateway", lambda: _FailingGateway())

    with pytest.raises(UnsafeProcessingError, match="entity review failed"):
        provider.review(text_window="text", entities=[], allowed_entity_types=[])


def test_verification_provider_failure_raises_unsafe_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = MLXProvider(model_path="local-model")
    monkeypatch.setattr(provider, "_gateway", lambda: _FailingGateway())

    with pytest.raises(UnsafeProcessingError, match="verification failed"):
        provider.verify_anonymization(output_segments=[], allowed_entity_types=[])
