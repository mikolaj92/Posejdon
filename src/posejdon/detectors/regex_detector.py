from __future__ import annotations

import re

from posejdon.domain.entities import SensitiveEntity
from posejdon.storage.regex_catalog import RegexCatalogStore

from . import regex_support
from .regex_support import POLISH_FIRST_NAME_FORMS, RegexRule, build_entity_id

normalize_digits = regex_support.normalize_digits
normalize_email = regex_support.normalize_email
validate_card_number = regex_support.validate_card_number
validate_iban = regex_support.validate_iban
validate_nip = regex_support.validate_nip
validate_pesel = regex_support.validate_pesel
validate_phone = regex_support.validate_phone


class RegexDetector:
    name = "regex"

    def __init__(
        self,
        allowed_entity_types: set[str] | None = None,
        *,
        catalog_path: str = "storage/regex_catalog.sqlite3",
        rules: list[RegexRule] | None = None,
    ) -> None:
        self.allowed_entity_types = allowed_entity_types
        self.catalog = RegexCatalogStore(catalog_path)
        base_rules = rules or self.catalog.load_rules(allowed_entity_types)
        self.rules = [*base_rules, *self._heuristic_rules()]

    @property
    def available(self) -> bool:
        return True

    def detect(self, text: str) -> list[SensitiveEntity]:
        entities: list[SensitiveEntity] = []
        seen_keys: set[tuple[str, int, int]] = set()

        for rule in self.rules:
            if (
                self.allowed_entity_types is not None
                and rule.entity_type not in self.allowed_entity_types
            ):
                continue
            pattern = rule.pattern
            group: str | int = "entity" if "entity" in pattern.groupindex else 0
            for match in pattern.finditer(text):
                raw_text = match.group(group)
                normalized_text = rule.normalizer(raw_text)
                if not normalized_text or not rule.validator(raw_text):
                    continue
                if rule.entity_type == "CARD" and self._is_embedded_card_candidate(
                    text, start=match.start(group), end=match.end(group)
                ):
                    continue
                start_offset = match.start(group)
                end_offset = match.end(group)
                key = (rule.entity_type, start_offset, end_offset)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                entities.append(
                    SensitiveEntity(
                        entity_id=build_entity_id(
                            entity_type=rule.entity_type,
                            normalized_text=normalized_text,
                            start_offset=start_offset,
                            end_offset=end_offset,
                        ),
                        entity_type=rule.entity_type,
                        raw_text=raw_text,
                        normalized_text=normalized_text,
                        confidence=rule.confidence,
                        source_detector=self.name,
                        start_offset=start_offset,
                        end_offset=end_offset,
                        metadata={
                            "validation": "checksum_or_pattern",
                            "context_required": str(rule.context_required).lower(),
                        },
                    )
                )
        return entities

    @staticmethod
    def _is_embedded_card_candidate(text: str, *, start: int, end: int) -> bool:
        left = text[:start].rstrip(" \t\r\n-")
        right = text[end:].lstrip(" \t\r\n-")
        return (bool(left) and left[-1].isdigit()) or (bool(right) and right[0].isdigit())

    def _heuristic_rules(self) -> list[RegexRule]:
        enabled = None if self.allowed_entity_types is None else set(self.allowed_entity_types)
        rules: list[RegexRule] = []
        person_token = (
            r"(?-i:[A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+"
            r"(?:-[A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+)?)"
        )
        initial_token = r"(?-i:[A-ZŁŚŻŹĆŃÓ]\.)"
        if enabled is None or "PERSON" in enabled:
            first_names_alt = "|".join(
                re.escape(name) for name in sorted(POLISH_FIRST_NAME_FORMS, key=len, reverse=True)
            )
            given_name = rf"(?-i:(?:{first_names_alt}))"
            given_or_initial = rf"(?:{given_name}|{initial_token})"
            given_first_name = rf"{given_name}(?:\s+{given_or_initial}){{0,2}}\s+{person_token}"
            surname_first_name = (
                rf"{person_token}\s+{given_or_initial}(?:\s+{given_or_initial}){{0,2}}"
            )
            initial_surname = rf"{initial_token}\s+{person_token}"
            full_person_reference = (
                rf"(?:{given_first_name}|{surname_first_name}|{initial_surname})"
            )
            person_reference = rf"(?:{full_person_reference}|{person_token})"
            honorific = (
                r"(?:(?:pan|pani|pana|panią|panem|dr\.?|mgr\.?|mec\.?|adw\.?|"
                r"radca\s+prawny)\s+)?"
            )
            person_context_prefix = (
                r"(?:imi[eę](?:\s+i\s+nazwisko)?|nazwisko\s+i\s+imi[eę]|nazwisko|"
                r"klient(?:ka)?|pacjent(?:ka)?|pracownik|pracownica|wnioskodawca|"
                r"wnioskodawczyni|ubezpieczon[ya]|pełnomocnik(?:a)?|reprezentant(?:ka)?|"
                r"reprezentowan[ay]\s+przez|osoba\s+kontaktowa|kontakt(?:\s+do)?|"
                r"opiekun(?:ka)?|adresat(?:ka)?|nadawca|odbiorca|podpisane\s+przez|"
                r"podpisał[ao]?|przekazane\s+przez|odebrane\s+przez|wystawione\s+przez|"
                r"sporządzone\s+przez|prowadząc[ay])"
            )
            rules.extend(
                [
                    RegexRule(
                        entity_type="PERSON",
                        pattern_text=(
                            rf"\b{person_context_prefix}\b\s*[:,-]?\s*"
                            rf"{honorific}(?P<entity>{person_reference})\b"
                        ),
                        normalizer_name="identity",
                        validator_name="person_full_name",
                        confidence=0.93,
                        context_required=True,
                    ),
                    RegexRule(
                        entity_type="PERSON",
                        pattern_text=(
                            rf"\b(?:z\s+)?(?:panem|panią|pan|pani|pana)\s+"
                            rf"(?P<entity>{person_reference})\b"
                        ),
                        normalizer_name="identity",
                        validator_name="person_full_name",
                        confidence=0.9,
                        context_required=True,
                    ),
                    RegexRule(
                        entity_type="PERSON",
                        pattern_text=rf"\b{given_first_name}\b",
                        normalizer_name="identity",
                        validator_name="person_full_name",
                        confidence=0.88,
                        context_required=False,
                    ),
                    RegexRule(
                        entity_type="PERSON",
                        pattern_text=(
                            rf"\b(?P<entity>{full_person_reference})\b"
                            r"(?=,\s+dalej\s+jako\s+(?!sekcja\b)[^,.]{3,80})"
                        ),
                        normalizer_name="identity",
                        validator_name="person_full_name",
                        confidence=0.91,
                        context_required=True,
                    ),
                    RegexRule(
                        entity_type="PERSON",
                        pattern_text=(
                            rf"(?m)^(?P<entity>{full_person_reference})$"
                            r"(?=\n"
                            r"(?-i:[A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+(?:-[A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+)?)"
                            r"\n(?:ul\.|al\.|pl\.|os\.|ulica|aleja)\s)"
                        ),
                        normalizer_name="identity",
                        validator_name="person_full_name",
                        confidence=0.92,
                        context_required=True,
                    ),
                    RegexRule(
                        entity_type="PERSON",
                        pattern_text=rf"\b{initial_surname}\b",
                        normalizer_name="identity",
                        validator_name="person_full_name",
                        confidence=0.87,
                        context_required=False,
                    ),
                ]
            )
        if enabled is None or "ORG" in enabled:
            rules.append(
                RegexRule(
                    entity_type="ORG",
                    pattern_text=(
                        r"\b[A-ZŁŚŻŹĆŃÓ][\w&.\-]+(?:\s+[A-ZŁŚŻŹĆŃÓ][\w&.\-]+){0,6}\s+"
                        r"(?:S\.A\.|Spółka\s+Akcyjna|sp\.\s*z\s*o\.o\.)"
                    ),
                    normalizer_name="identity",
                    validator_name="always_true",
                    confidence=0.92,
                    context_required=True,
                )
            )
        if enabled is None or "CITY" in enabled:
            rules.extend(
                [
                    RegexRule(
                        entity_type="CITY",
                        pattern_text=(
                            r"\b(?:registered\s+office\s+in|z\s+siedzibą\s+we?|"
                            r"z\s+siedzibą\s+w)\s+([A-ZŁŚŻŹĆŃÓ][A-Za-zŁŚŻŹĆŃÓąćęłńóśźż.\-]+)"
                        ),
                        normalizer_name="identity",
                        validator_name="always_true",
                        confidence=0.9,
                        context_required=True,
                    ),
                    RegexRule(
                        entity_type="CITY",
                        pattern_text=(
                            r"\b([A-ZŁŚŻŹĆŃÓ][A-Za-zŁŚŻŹĆŃÓąćęłńóśźż.\-]+)\s+\(\d{2}-\d{3}\)\s+"
                            r"at\s+\d+\s+[A-ZŁŚŻŹĆŃÓ][A-Za-zŁŚŻŹĆŃÓąćęłńóśźż.\-]+\s+Street\b"
                        ),
                        normalizer_name="identity",
                        validator_name="always_true",
                        confidence=0.9,
                        context_required=True,
                    ),
                ]
            )
        if enabled is None or "PESEL" in enabled:
            rules.append(
                RegexRule(
                    entity_type="PESEL",
                    pattern_text=r"\bPESEL[:\s-]*\d{11}\b",
                    normalizer_name="identity",
                    validator_name="always_true",
                    confidence=0.99,
                    context_required=True,
                )
            )
        return rules
