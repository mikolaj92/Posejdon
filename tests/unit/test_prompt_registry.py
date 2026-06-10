from __future__ import annotations

import json
from pathlib import Path

import pytest

from posejdon.prompt_registry import PosejdonPromptRegistry


@pytest.fixture
def fixture_prompt_root() -> Path:
    return Path(__file__).parent.parent.parent / "prompts"


def test_load_review_sensitive_entities_prompt(fixture_prompt_root: Path) -> None:
    registry = PosejdonPromptRegistry(fixture_prompt_root)
    record = registry.load("posejdon-review-sensitive-entities")
    assert record["prompt_id"] == "posejdon-review-sensitive-entities"
    assert record["version"] == "1.0.0"


def test_render_review_prompt(fixture_prompt_root: Path) -> None:
    registry = PosejdonPromptRegistry(fixture_prompt_root)
    rendered = registry.render(
        "posejdon-review-sensitive-entities",
        {
            "text_window": "sample text",
            "allowed_entity_types": ["PERSON", "EMAIL"],
            "entities": [{"id": "e1", "type": "PERSON"}],
        },
    )
    payload = rendered
    assert "review_sensitive_entities" in payload
    assert "sample text" in payload
    assert "PERSON" in payload


def test_render_review_prompt_escapes_json_text_window(
    fixture_prompt_root: Path,
) -> None:
    registry = PosejdonPromptRegistry(fixture_prompt_root)
    rendered = registry.render(
        "posejdon-review-sensitive-entities",
        {
            "text_window": 'Jan powiedzial "tajne"\nnowa linia',
            "allowed_entity_types": ["PERSON"],
            "entities": [],
        },
    )

    payload = json.loads(rendered)
    assert payload["text_window"] == 'Jan powiedzial "tajne"\nnowa linia'


def test_render_verify_prompt(fixture_prompt_root: Path) -> None:
    registry = PosejdonPromptRegistry(fixture_prompt_root)
    rendered = registry.render(
        "posejdon-verify-document-anonymized-window",
        {
            "allowed_entity_types": ["PERSON"],
            "segments": [{"segment_id": "s1", "text": "xxx"}],
        },
    )
    assert "verify_document_is_anonymized_window" in rendered
    assert "s1" in rendered


def test_missing_prompt_raises(fixture_prompt_root: Path) -> None:
    registry = PosejdonPromptRegistry(fixture_prompt_root)
    with pytest.raises(FileNotFoundError):
        registry.load("nonexistent-prompt")
