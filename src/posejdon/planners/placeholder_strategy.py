from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from posejdon.core.enums import ReplacementKind
from posejdon.domain.entities import SensitiveEntity


class PlaceholderStrategy(Protocol):
    kind: ReplacementKind

    def replace(self, entity: SensitiveEntity, ordinal: int) -> str:
        """Return replacement text."""
        ...


ADDRESS_ENTITY_TYPES = {
    "ADDRESS",
    "STREET",
    "HOUSE_NUMBER",
    "APARTMENT_NUMBER",
    "POSTAL_CODE",
    "CITY",
    "COUNTRY",
    "PLACE_OF_BIRTH",
}


def placeholder_label(entity_type: str) -> str:
    normalized = entity_type.strip().upper()
    if normalized == "PERSON":
        return "OSOBA"
    if normalized in ADDRESS_ENTITY_TYPES:
        return "ADRES"
    return normalized


@dataclass(slots=True)
class DeterministicPlaceholderStrategy:
    kind: ReplacementKind = ReplacementKind.CATEGORY_PLACEHOLDER

    def replace(self, entity: SensitiveEntity, ordinal: int) -> str:
        return f"[{placeholder_label(entity.entity_type)}_{ordinal}]"


@dataclass(slots=True)
class MaskingStrategy:
    kind: ReplacementKind = ReplacementKind.MASK

    def replace(self, entity: SensitiveEntity, ordinal: int) -> str:
        text = entity.raw_text
        if entity.entity_type in {"EMAIL", "PHONE"}:
            return "*" * len(text)
        masked = re.sub(r"[A-Za-z0-9]", "*", text)
        return masked


@dataclass(slots=True)
class FixedMaskStrategy:
    kind: ReplacementKind = ReplacementKind.MASK
    mask_text: str = "****"

    def replace(self, entity: SensitiveEntity, ordinal: int) -> str:
        return self.mask_text


@dataclass(slots=True)
class FormatPreservingStrategy:
    kind: ReplacementKind = ReplacementKind.FORMAT_PRESERVING

    def replace(self, entity: SensitiveEntity, ordinal: int) -> str:
        text = entity.raw_text
        if entity.entity_type in {"EMAIL", "PHONE"}:
            return "*" * len(text)
        return "".join("*" if char.isalnum() else char for char in text)
