from __future__ import annotations

import pytest

from posejdon import TextAnonymizer
from posejdon.detectors.regex_detector import RegexDetector
from posejdon.detectors.regex_support import validate_phone


def _raw_entities(text: str, entity_type: str) -> set[str]:
    detector = RegexDetector(allowed_entity_types={entity_type})
    return {
        entity.raw_text for entity in detector.detect(text) if entity.entity_type == entity_type
    }


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Klientka: Anna Maria Nowak-Kowalska podpisała załącznik.", "Anna Maria Nowak-Kowalska"),
        ("Pełnomocnik Jana Kowalskiego przesłał dokument.", "Jana Kowalskiego"),
        ("Spotkanie z Panią Nowak zaplanowano na jutro.", "Nowak"),
        ("Reprezentowany przez dr. Piotra Wiśniewskiego.", "Piotra Wiśniewskiego"),
        ("Nazwisko i imię: Kowalski Jan.", "Kowalski Jan"),
        ("Kontakt: J. Kowalski, tel. 500 600 700.", "J. Kowalski"),
        ("Podpisane przez Karolinę Bednarek w siedzibie spółki.", "Karolinę Bednarek"),
        ("Odebrane przez Łukasza Wiśniewskiego dnia 12 maja.", "Łukasza Wiśniewskiego"),
        ("Prowadząca Małgorzata Zielińska zamknęła sprawę.", "Małgorzata Zielińska"),
        ("Rozmowa z Panem Tomaszem Szymańskim została odnotowana.", "Tomaszem Szymańskim"),
        ("Wnioskodawca Adam Nowakowski uzupełnił formularz.", "Adam Nowakowski"),
        ("Materiały przekazane przez Roman Mazur obejmują korespondencję.", "Roman Mazur"),
    ],
)
def test_regex_detector_finds_polish_person_variants(text: str, expected: str) -> None:
    assert expected in _raw_entities(text, "PERSON")


@pytest.mark.parametrize(
    "text",
    [
        "Data Zawarcia, dalej jako sekcja dokumentu.",
        "Miejsce Zawarcia\nWarszawa\nul. Jasna 12/4",
        "Kontakt: Dział Sprzedaży, telefon w stopce.",
        "Materiały przekazane przez Dział Marketingu pozostają jawne.",
        "Sąd Rejonowy prowadzi publiczny rejestr spraw.",
    ],
)
def test_regex_detector_rejects_polish_headings_departments_and_institutions(text: str) -> None:
    assert _raw_entities(text, "PERSON") == set()


@pytest.mark.parametrize(
    "phone",
    [
        "500600700",
        "500 600 700",
        "+48 500 600 700",
        "(+48) 500 600 700",
        "0048 500 600 700",
        "+48 22 123 45 67",
        "22 123 45 67",
    ],
)
def test_regex_detector_finds_common_polish_phone_formats(phone: str) -> None:
    assert validate_phone(phone) is True
    assert phone in _raw_entities(f"Telefon kontaktowy: {phone}.", "PHONE")


def test_regex_detector_finds_postal_code_city_address_without_street() -> None:
    entities = _raw_entities("Adres korespondencyjny: 31-147 Kraków.", "ADDRESS")

    assert "31-147 Kraków" in entities


@pytest.mark.parametrize(
    ("text", "leaked_values", "expected_entity_types"),
    [
        (
            (
                "Klientka: Anna Maria Nowak-Kowalska, PESEL 44051401359, "
                "NIP 856-734-62-15, data urodzenia: 14.05.1944."
            ),
            ["Anna Maria Nowak-Kowalska", "44051401359", "856-734-62-15", "14.05.1944"],
            {"PERSON", "PESEL", "NIP", "DATE_OF_BIRTH"},
        ),
        (
            ("Adres: ul. Żurawia 12/7, 00-515 Warszawa. Adres korespondencyjny: 31-147 Kraków."),
            ["ul. Żurawia 12/7", "00-515 Warszawa", "31-147 Kraków"],
            {"ADDRESS"},
        ),
        (
            "Kontakt: J. Kowalski, e-mail jkowalski@example.pl, tel. (+48) 500 600 700.",
            ["J. Kowalski", "jkowalski@example.pl", "(+48) 500 600 700"],
            {"PERSON", "EMAIL", "PHONE"},
        ),
        (
            "Rachunek bankowy 61 1090 1014 0000 0712 1981 2874.",
            ["61 1090 1014 0000 0712 1981 2874"],
            {"BANK_ACCOUNT"},
        ),
        (
            "KRS 0000123456, REGON 192598184, VAT UE PL8567346215.",
            ["0000123456", "192598184", "PL8567346215"],
            {"KRS", "REGON", "VAT_ID"},
        ),
        (
            "Nr dowodu ABA123456. Paszport nr AB1234567. Prawo jazdy nr XYZ-778899.",
            ["ABA123456", "AB1234567", "XYZ-778899"],
            {"ID_CARD_NUMBER", "PASSPORT_NUMBER", "DRIVER_LICENSE_NUMBER"},
        ),
        (
            "PESEL 90031412345 wskazano w formularzu mimo błędnej sumy kontrolnej.",
            ["90031412345"],
            {"PESEL"},
        ),
        (
            "Polisa nr POL-2026-88. Szkoda nr CLM-2026-11. Klient ID CL-2026-9001.",
            ["POL-2026-88", "CLM-2026-11", "CL-2026-9001"],
            {"POLICY_NUMBER", "CLAIM_NUMBER", "CLIENT_ID"},
        ),
    ],
)
def test_text_anonymizer_removes_polish_sensitive_surfaces(
    text: str,
    leaked_values: list[str],
    expected_entity_types: set[str],
) -> None:
    result = TextAnonymizer().anonymize(text)

    for value in leaked_values:
        assert value not in result.text
    assert expected_entity_types.issubset(result.findings)


def test_person_rules_do_not_embed_fixture_only_legal_clause() -> None:
    patterns = "\n".join(
        rule.pattern_text for rule in RegexDetector(allowed_entity_types={"PERSON"}).rules
    )

    assert "strona operacyjna" not in patterns


def test_text_anonymizer_default_policy_uses_canonical_entity_names() -> None:
    entity_classes = set(TextAnonymizer().policy.entity_classes)

    assert {"PESEL", "NIP", "REGON", "PHONE", "CARD"}.issubset(entity_classes)
    assert {"PL_PESEL", "PL_NIP", "PL_REGON", "PHONE_NUMBER", "PAYMENT_CARD"}.isdisjoint(
        entity_classes
    )
