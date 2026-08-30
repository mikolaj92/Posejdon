"""Package version, lock, and audit subsystem version stay one value (#53)."""

from __future__ import annotations

from pathlib import Path

from posejdon.core.constants import DEFAULT_SUBSYSTEM_VERSION

_ROOT = Path(__file__).resolve().parents[2]


def _project_version() -> str:
    for line in (_ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.startswith("version = "):
            return line.split("=", 1)[1].strip().strip('"')
    raise AssertionError("pyproject.toml has no project version")


def _lock_version() -> str:
    lines = (_ROOT / "uv.lock").read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line == 'name = "posejdon"':
            version = lines[i + 1]
            assert version.startswith("version = ")
            return version.split("=", 1)[1].strip().strip('"')
    raise AssertionError("uv.lock has no posejdon package")


def test_package_lock_and_subsystem_version_match() -> None:
    project = _project_version()
    lock = _lock_version()
    assert project == lock == DEFAULT_SUBSYSTEM_VERSION
    assert project == "0.1.9"
