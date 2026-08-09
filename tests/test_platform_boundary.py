from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_posejdon_documents_platform_ui_as_a_host_contract() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "No document parsing. No web server. No queue." in readme
    assert "app_factory/product_shell.html" in readme
    assert "/static/platform/..." in readme
    assert "Anonimizator3000" in readme


def test_posejdon_has_no_unconsumed_platform_ui_dependencies() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = set(metadata["project"]["dependencies"])

    assert not any(
        dependency.startswith(prefix)
        for dependency in dependencies
        for prefix in ("app-factory", "my-auth", "my-usermanager", "fastapi", "starlette")
    )
