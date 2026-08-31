from __future__ import annotations

import pytest

from posejdon.core.errors import UnsafeProcessingError
from posejdon.detectors.llm_review import LLMResponse, LLMReviewer
from posejdon.domain.models import LLMVerificationWindowEntry


class _StubClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return LLMResponse(content=self.content)


class _FailingClient:
    def complete(self, request):
        raise RuntimeError("client failed")


def test_injected_client_reviews_without_provider_configuration() -> None:
    client = _StubClient(
        'prefix {"suggestions":[{"entity_id":"e1","action":"keep","reason":"valid"}]} suffix'
    )
    reviewer = LLMReviewer(client)

    response = reviewer.review(text_window="text", entities=[], allowed_entity_types=["PERSON"])

    assert response.suggestions[0].entity_id == "e1"
    assert len(client.requests) == 1
    assert client.requests[0].temperature == 0.0
    assert "PERSON" in client.requests[0].messages[0].content


def test_injected_client_verifies_anonymization() -> None:
    client = _StubClient(
        '{"suspected_leaks":[],"warnings":[],"verified_segment_ids":["segment-1"]}'
    )
    reviewer = LLMReviewer(client)

    response = reviewer.verify_anonymization(
        output_segments=[
            LLMVerificationWindowEntry(
                segment_id="segment-1",
                start_char=0,
                end_char=4,
                text="safe",
            )
        ],
        allowed_entity_types=["PERSON"],
    )

    assert response.verified_segment_ids == ["segment-1"]
    assert "segment-1" in client.requests[0].messages[0].content


def test_response_without_json_is_rejected() -> None:
    with pytest.raises(ValueError, match="did not contain a JSON object"):
        LLMReviewer._extract_json("generation completed without structured output")


@pytest.mark.parametrize("operation", ["review", "verify"])
def test_client_failure_raises_unsafe_processing(operation: str) -> None:
    reviewer = LLMReviewer(_FailingClient())

    with pytest.raises(UnsafeProcessingError, match="LLM .* failed"):
        if operation == "review":
            reviewer.review(text_window="text", entities=[], allowed_entity_types=[])
        else:
            reviewer.verify_anonymization(output_segments=[], allowed_entity_types=[])
