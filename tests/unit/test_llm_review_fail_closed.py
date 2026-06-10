from __future__ import annotations

import pytest

from posejdon.core.errors import UnsafeProcessingError
from posejdon.detectors.llm_review import MLXProvider


class _FailingGateway:
    def complete(self, request):
        raise RuntimeError("provider failed")


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
