from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Template as JinjaTemplate

DEFAULT_PROMPT_ROOT = "prompts"


class PosejdonPromptRegistry:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or os.getenv("POSEJDON_PROMPT_ROOT", DEFAULT_PROMPT_ROOT))
        self._cache: dict[str, dict[str, Any]] = {}

    def load(self, prompt_id: str) -> dict[str, Any]:
        if prompt_id not in self._cache:
            path = self._find_file(prompt_id)
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("prompt_id") != prompt_id:
                raise ValueError(f"Invalid prompt file for {prompt_id}")
            self._cache[prompt_id] = data
        return self._cache[prompt_id]

    def render(self, prompt_id: str, variables: dict[str, Any]) -> str:
        record = self.load(prompt_id)
        template = JinjaTemplate(record["template"])
        return template.render(variables).strip()

    def _find_file(self, prompt_id: str) -> Path:
        for path in self.root.rglob("*.yaml"):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("prompt_id") == prompt_id:
                return path
        raise FileNotFoundError(f"Prompt not found: {prompt_id}")
