from __future__ import annotations

from typing import Protocol

from posejdon.domain.entities import SensitiveEntity


class Detector(Protocol):
    name: str

    @property
    def available(self) -> bool:
        """Return whether the detector is loaded and ready."""
        ...

    def detect(self, text: str) -> list[SensitiveEntity]:
        """Return detected entities for a text fragment."""
        ...
