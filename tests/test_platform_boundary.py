from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _dependency_names(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield re.split(r"[ <=>!~;\[]", value, maxsplit=1)[0]
    elif isinstance(value, Mapping):
        if isinstance(value.get("name"), str):
            yield value["name"]
        for nested in value.values():
            yield from _dependency_names(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _dependency_names(nested)


def _normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def test_dependency_name_extraction_covers_all_supported_declarations() -> None:
    declarations = {
        "dependencies": ["FastAPI>=1"],
        "optional-dependencies": {"web": ["my_auth[fastapi-htmx]"]},
        "dependency-groups": {"dev": ["APP.FACTORY"]},
        "lock": {"package": [{"name": "my-usermanager"}]},
    }

    assert {_normalized(name) for name in _dependency_names(declarations)} == {
        "app-factory",
        "fastapi",
        "my-auth",
        "my-usermanager",
    }


def test_htmx_host_contract_is_documented() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    requirements = (
        "mutation routes return server-rendered HTML",
        "same partials as full-page responses",
        "stable `id`/`hx-target` pairs",
        "forms functional without JavaScript",
        "do not return JSON for client-side rendering",
    )

    assert all(requirement in readme for requirement in requirements)


def test_alpine_host_contract_is_documented() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    requirements = (
        "component-local presentation state",
        "do not put server data, business rules, or validation in Alpine stores",
        "focus management",
        "Escape handling",
        "`aria-expanded`/`aria-controls`",
    )

    assert all(requirement in readme for requirement in requirements)


def test_posejdon_has_no_platform_dependencies() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    declared = {"metadata": metadata, "lock": lock}
    prohibited = {"app-factory", "my-auth", "my-usermanager", "fastapi", "starlette"}

    found = {_normalized(name) for name in _dependency_names(declared)} & prohibited

    assert not found, f"platform dependencies belong in the host application: {sorted(found)}"
