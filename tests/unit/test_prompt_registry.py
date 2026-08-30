from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

import pytest

from posejdon.prompt_registry import PosejdonPromptRegistry


def test_packaged_prompts_are_importlib_resources() -> None:
    names = {item.name for item in files("posejdon.prompts").iterdir()}
    assert "review-sensitive-entities.yaml" in names
    assert "verify-document-anonymized-window.yaml" in names


def test_default_registry_loads_without_checkout_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("POSEJDON_PROMPT_ROOT", raising=False)
    registry = PosejdonPromptRegistry()
    record = registry.load("posejdon-review-sensitive-entities")
    assert record["prompt_id"] == "posejdon-review-sensitive-entities"
    assert record["version"] == "1.0.0"


def test_render_review_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("POSEJDON_PROMPT_ROOT", raising=False)
    registry = PosejdonPromptRegistry()
    rendered = registry.render(
        "posejdon-review-sensitive-entities",
        {
            "text_window": "sample text",
            "allowed_entity_types": ["PERSON", "EMAIL"],
            "entities": [{"id": "e1", "type": "PERSON"}],
        },
    )
    assert "review_sensitive_entities" in rendered
    assert "sample text" in rendered
    assert "PERSON" in rendered


def test_render_review_prompt_escapes_json_text_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("POSEJDON_PROMPT_ROOT", raising=False)
    registry = PosejdonPromptRegistry()
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


def test_render_verify_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("POSEJDON_PROMPT_ROOT", raising=False)
    registry = PosejdonPromptRegistry()
    rendered = registry.render(
        "posejdon-verify-document-anonymized-window",
        {
            "allowed_entity_types": ["PERSON"],
            "segments": [{"segment_id": "s1", "text": "xxx"}],
        },
    )
    assert "verify_document_is_anonymized_window" in rendered
    assert "s1" in rendered


def test_missing_prompt_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("POSEJDON_PROMPT_ROOT", raising=False)
    registry = PosejdonPromptRegistry()
    with pytest.raises(FileNotFoundError, match="Prompt not found"):
        registry.load("nonexistent-prompt")


def test_explicit_root_override(tmp_path: Path) -> None:
    yaml_path = tmp_path / "custom.yaml"
    yaml_path.write_text(
        "prompt_id: custom-override\nversion: \"1.0.0\"\ntemplate: hello\n",
        encoding="utf-8",
    )
    registry = PosejdonPromptRegistry(tmp_path)
    record = registry.load("custom-override")
    assert record["prompt_id"] == "custom-override"


def test_built_wheel_contains_prompt_yaml(tmp_path: Path) -> None:
    import subprocess
    import zipfile

    out = tmp_path / "dist"
    out.mkdir()
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(out)],
        cwd=Path(__file__).resolve().parents[2],
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(out.glob("posejdon-*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
    assert "posejdon/prompts/review-sensitive-entities.yaml" in names
    assert "posejdon/prompts/verify-document-anonymized-window.yaml" in names
