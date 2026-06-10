from __future__ import annotations

from posejdon.domain.entities import SensitiveEntity
from posejdon.storage.regex_catalog import RegexCatalogStore

from . import regex_support
from .regex_support import RegexRule, build_entity_id

normalize_digits = regex_support.normalize_digits
normalize_email = regex_support.normalize_email
validate_card_number = regex_support.validate_card_number
validate_iban = regex_support.validate_iban
validate_nip = regex_support.validate_nip
validate_pesel = regex_support.validate_pesel
validate_phone = regex_support.validate_phone



POLISH_FIRST_NAMES = (
    "Adam",
    "Adrian",
    "Agnieszka",
    "Aleksandra",
    "Andrzej",
    "Anna",
    "Antoni",
    "Barbara",
    "Bartosz",
    "Beata",
    "Bogdan",
    "Cezary",
    "Damian",
    "Daniel",
    "Dariusz",
    "Dorota",
    "Ewa",
    "Filip",
    "Grzegorz",
    "Hanna",
    "Jakub",
    "Jan",
    "Joanna",
    "Jolanta",
    "Kamil",
    "Karolina",
    "Katarzyna",
    "Kinga",
    "Krzysztof",
    "Łukasz",
    "Magdalena",
    "Małgorzata",
    "Marcin",
    "Marek",
    "Maria",
    "Mariusz",
    "Mateusz",
    "Michał",
    "Monika",
    "Natalia",
    "Paweł",
    "Piotr",
    "Rafał",
    "Robert",
    "Stanisław",
    "Tomasz",
    "Wojciech",
    "Zbigniew",
)

POLISH_FIRST_NAME_FORMS = POLISH_FIRST_NAMES + (
    "Adama",
    "Agnieszki",
    "Aleksandry",
    "Andrzeja",
    "Annę",
    "Anny",
    "Annie",
    "Antoniego",
    "Barbary",
    "Bartosza",
    "Beaty",
    "Bogdana",
    "Cezarego",
    "Damiana",
    "Daniela",
    "Dariusza",
    "Doroty",
    "Ewy",
    "Filipa",
    "Grzegorza",
    "Hanny",
    "Jakuba",
    "Jana",
    "Joanny",
    "Jolanty",
    "Kamila",
    "Karoliny",
    "Katarzyny",
    "Kingi",
    "Krzysztofa",
    "Łukasza",
    "Magdaleny",
    "Małgorzaty",
    "Marcina",
    "Marka",
    "Marii",
    "Mariusza",
    "Mateusza",
    "Michała",
    "Moniki",
    "Natalii",
    "Pawła",
    "Piotra",
    "Rafała",
    "Roberta",
    "Stanisława",
    "Tomasza",
    "Wojciecha",
    "Zbigniewa",
)


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
            for match in rule.pattern.finditer(text):
                raw_text = match.group(0)
                normalized_text = rule.normalizer(raw_text)
                if not normalized_text or not rule.validator(raw_text):
                    continue
                if rule.entity_type == "CARD" and self._is_embedded_card_candidate(
                    text, start=match.start(), end=match.end()
                ):
                    continue
                key = (rule.entity_type, match.start(), match.end())
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                entities.append(
                    SensitiveEntity(
                        entity_id=build_entity_id(
                            entity_type=rule.entity_type,
                            normalized_text=normalized_text,
                            start_offset=match.start(),
                            end_offset=match.end(),
                        ),
                        entity_type=rule.entity_type,
                        raw_text=raw_text,
                        normalized_text=normalized_text,
                        confidence=rule.confidence,
                        source_detector=self.name,
                        start_offset=match.start(),
                        end_offset=match.end(),
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
        enabled = (
            None
            if self.allowed_entity_types is None
            else set(self.allowed_entity_types)
        )
        rules: list[RegexRule] = []
        person_token = r"(?-i:[A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+(?:-[A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+)?)"
        person_full_name = rf"{person_token}\s+{person_token}"
        if enabled is None or "PERSON" in enabled:
            first_names_alt = "|".join(POLISH_FIRST_NAME_FORMS)
            rules.extend(
                [
                    RegexRule(
                        entity_type="PERSON",
                        pattern_text=rf"\b(?:{first_names_alt})\s+{person_token}\b",
                        normalizer_name="identity",
                        validator_name="person_full_name",
                        confidence=0.85,
                        context_required=False,
                    ),
                    RegexRule(
                        entity_type="PERSON",
                        pattern_text=(
                            rf"\b{person_full_name}\b"
                            r"(?=,\s+dalej\s+jako\s+strona\s+operacyjna\b)"
                        ),
                        normalizer_name="identity",
                        validator_name="person_full_name",
                        confidence=0.91,
                        context_required=True,
                    ),
                    RegexRule(
                        entity_type="PERSON",
                        pattern_text=rf"(?<=przekazane przez ){person_full_name}\b",
                        normalizer_name="identity",
                        validator_name="person_full_name",
                        confidence=0.9,
                        context_required=True,
                    ),
                    RegexRule(
                        entity_type="PERSON",
                        pattern_text=(
                            rf"(?m)^{person_full_name}$"
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
                        pattern_text=rf"\b{person_full_name}\b",
                        normalizer_name="identity",
                        validator_name="person_full_name",
                        confidence=0.86,
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
