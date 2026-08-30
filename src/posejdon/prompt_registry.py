from __future__ import annotations

import os
from collections.abc import Iterator
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Template as JinjaTemplate

_PACKAGE_PROMPTS = "posejdon.prompts"


class PosejdonPromptRegistry:
    """Load prompt YAML from package data, or from POSEJDON_PROMPT_ROOT / explicit root."""

    def __init__(self, root: str | Path | None = None) -> None:
        env_root = os.getenv("POSEJDON_PROMPT_ROOT")
        if root is not None:
            self.root: Path | None = Path(root)
        elif env_root:
            self.root = Path(env_root)
        else:
            self.root = None
        self._cache: dict[str, dict[str, Any]] = {}

    def load(self, prompt_id: str) -> dict[str, Any]:
        if prompt_id not in self._cache:
            data = self._load_raw(prompt_id)
            if not isinstance(data, dict) or data.get("prompt_id") != prompt_id:
                raise ValueError(f"Invalid prompt file for {prompt_id}")
            self._cache[prompt_id] = data
        return self._cache[prompt_id]

    def render(self, prompt_id: str, variables: dict[str, Any]) -> str:
        record = self.load(prompt_id)
        template = JinjaTemplate(record["template"])
        return template.render(variables).strip()

    def _iter_prompt_docs(self) -> Iterator[dict[str, Any]]:
        if self.root is not None:
            for path in sorted(self.root.rglob("*.yaml")):
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    yield data
            return
        package = files(_PACKAGE_PROMPTS)
        for item in package.iterdir():
            if not item.name.endswith(".yaml"):
                continue
            data = yaml.safe_load(item.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                yield data

    def _load_raw(self, prompt_id: str) -> dict[str, Any]:
        for data in self._iter_prompt_docs():
            if data.get("prompt_id") == prompt_id:
                return data
        raise FileNotFoundError(f"Prompt not found: {prompt_id}")
