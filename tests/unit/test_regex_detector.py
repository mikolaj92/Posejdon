from posejdon.detectors.regex_detector import (
    RegexDetector,
    normalize_digits,
    normalize_email,
    validate_card_number,
    validate_iban,
    validate_nip,
    validate_pesel,
    validate_phone,
)
from posejdon.storage.regex_catalog import RegexCatalogStore


def test_normalizers_are_deterministic() -> None:
    assert normalize_digits("+48 500-600-700") == "48500600700"
    assert normalize_email(" Jan.Kowalski@Example.com ") == "jan.kowalski@example.com"


def test_identifier_validators_accept_valid_values() -> None:
    assert validate_phone("+48 500 600 700") is True
    assert validate_pesel("44051401458") is True
    assert validate_nip("8567346215") is True
    assert validate_iban("PL61109010140000071219812874") is True
    assert validate_card_number("4111 1111 1111 1111") is True


def test_identifier_validators_reject_invalid_values() -> None:
    assert validate_pesel("12345678901") is False
    assert validate_nip("1234567890") is False
    assert validate_iban("PL00109010140000071219812874") is False
    assert validate_card_number("4111 1111 1111 1112") is False


def test_regex_detector_finds_supported_entities_with_offsets() -> None:
    text = (
        "Kontakt: jan.kowalski@example.com, tel. +48 500 600 700, "
        "PESEL 44051401458, NIP 8567346215, IBAN PL61109010140000071219812874."
    )
    entities = RegexDetector().detect(text)

    entity_types = {entity.entity_type for entity in entities}
    assert {"EMAIL", "PHONE", "PESEL", "NIP", "IBAN"}.issubset(entity_types)
    assert all(entity.source_detector == "regex" for entity in entities)
    assert all(
        entity.start_offset is not None and entity.end_offset is not None for entity in entities
    )


def test_regex_detector_finds_context_labeled_pesel_without_checksum(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={"PESEL"},
        catalog_path=str(db_path),
    )

    entities = detector.detect("PESEL 90031412345")

    assert len(entities) == 1
    assert entities[0].entity_type == "PESEL"
    assert entities[0].raw_text == "PESEL 90031412345"


def test_regex_detector_finds_phone_numbers_with_spaces_and_hyphens() -> None:
    entities = RegexDetector(allowed_entity_types={"PHONE"}).detect(
        "Telefon: +48 500-600 700, drugi kontakt 500 600-701."
    )

    phones = [entity.raw_text for entity in entities if entity.entity_type == "PHONE"]

    assert "+48 500-600 700" in phones
    assert "500 600-701" in phones


def test_regex_detector_finds_pdf_truncated_labeled_phone_number() -> None:
    entities = RegexDetector(allowed_entity_types={"PHONE"}).detect(
        "Dane obejmują numer telefonu +48 \n222 333, rachunek 41 1140 2004."
    )

    phones = [entity.raw_text for entity in entities if entity.entity_type == "PHONE"]

    assert "+48 \n222 333" in phones


def test_regex_detector_finds_spaced_nip_and_labeled_krs_without_partial_phone_matches() -> None:
    detector = RegexDetector(allowed_entity_types={"NIP", "KRS", "PHONE"})
    entities = detector.detect("NIP: 856 734 62 15; KRS 0000 1234 56")

    assert {entity.entity_type for entity in entities} == {"NIP", "KRS"}
    assert {entity.raw_text for entity in entities if entity.entity_type == "KRS"} == {
        "KRS 0000 1234 56"
    }
    assert {entity.raw_text for entity in entities if entity.entity_type == "NIP"} == {
        "NIP: 856 734 62 15",
        "856 734 62 15",
    }


def test_regex_detector_finds_spaced_nip_without_label() -> None:
    detector = RegexDetector(allowed_entity_types={"NIP"})
    entities = detector.detect("Numer identyfikacyjny: 856 734 62 15")

    assert [entity.raw_text for entity in entities] == ["856 734 62 15"]


def test_regex_detector_honors_allowed_entity_filter() -> None:
    detector = RegexDetector(allowed_entity_types={"EMAIL"})
    entities = detector.detect("Email jan.kowalski@example.com oraz PESEL 44051401458.")

    assert len(entities) == 1
    assert entities[0].entity_type == "EMAIL"


def test_regex_detector_finds_person_names_in_strong_document_contexts() -> None:
    detector = RegexDetector(allowed_entity_types={"PERSON"})

    entities = detector.detect(
        "Paweł Lisowski, dalej jako Zamawiający, potwierdza ustalenia. "
        "Materiały przekazane przez Karolinę Bednarek pozostają w aktach.\n"
        "Jan Kowalski\n"
        "Warszawa\n"
        "ul. Jasna 12/4"
    )

    names = {entity.raw_text for entity in entities if entity.entity_type == "PERSON"}
    assert {"Paweł Lisowski", "Karolinę Bednarek", "Jan Kowalski"}.issubset(names)


def test_regex_detector_does_not_treat_headings_as_person_names() -> None:
    detector = RegexDetector(allowed_entity_types={"PERSON"})

    entities = detector.detect(
        "Data Zawarcia, dalej jako sekcja dokumentu.\nMiejsce Zawarcia\nWarszawa\nul. Jasna 12/4"
    )

    assert entities == []


def test_regex_catalog_bootstraps_sqlite_rules(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    store = RegexCatalogStore(str(db_path))

    rules = store.load_rules({"IBAN", "BANK_ACCOUNT", "ADDRESS", "DATE_OF_BIRTH"})

    assert db_path.exists()
    assert {rule.entity_type for rule in rules} == {
        "IBAN",
        "BANK_ACCOUNT",
        "ADDRESS",
        "DATE_OF_BIRTH",
    }


def test_regex_detector_finds_seeded_address_and_dob(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={"ADDRESS", "DATE_OF_BIRTH"},
        catalog_path=str(db_path),
    )

    entities = detector.detect(
        "Data urodzenia: 14.05.1944. Adres: 00-123 Warszawa, ul. Jasna 12/4."
    )

    entity_types = {entity.entity_type for entity in entities}
    assert "DATE_OF_BIRTH" in entity_types
    assert "ADDRESS" in entity_types


def test_regex_detector_finds_bank_account_and_invoice_number(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={"BANK_ACCOUNT", "INVOICE_NUMBER"},
        catalog_path=str(db_path),
    )

    entities = detector.detect(
        "Faktura FV/2026/03/17. Rachunek bankowy 61 1090 1014 0000 0712 1981 2874."
    )

    entity_types = {entity.entity_type for entity in entities}
    assert "BANK_ACCOUNT" in entity_types
    assert "INVOICE_NUMBER" in entity_types


def test_regex_detector_finds_bank_account_with_spaces_and_hyphens(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={"BANK_ACCOUNT"},
        catalog_path=str(db_path),
    )

    entities = detector.detect(
        "Rachunki: PL61 1090-1014 0000-0712 1981 2874 oraz 61-1090 1014 0000 0712-1981 2874."
    )

    accounts = [entity.raw_text for entity in entities if entity.entity_type == "BANK_ACCOUNT"]

    assert "PL61 1090-1014 0000-0712 1981 2874" in accounts
    assert "61-1090 1014 0000 0712-1981 2874" in accounts


def test_regex_detector_rejects_invalid_bank_account_candidates(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={"BANK_ACCOUNT"},
        catalog_path=str(db_path),
    )

    entities = detector.detect("Kandydat 12 3456 7890 1234 5678 9012 3456.")

    assert entities == []


def test_regex_detector_redacts_labeled_checksum_invalid_bank_account(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={"BANK_ACCOUNT"},
        catalog_path=str(db_path),
    )

    entities = detector.detect("Rachunek 41 1140 2004 0000 3102 1234 5678.")

    accounts = [entity.raw_text for entity in entities if entity.entity_type == "BANK_ACCOUNT"]
    assert "41 1140 2004 0000 3102 1234 5678" in accounts


def test_regex_detector_redacts_pdf_broken_bank_account_label(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={"BANK_ACCOUNT"},
        catalog_path=str(db_path),
    )

    entities = detector.detect("Dane obejmują rachu\n41 1140 2004 0000 3102 1234 5678.")

    accounts = [entity.raw_text for entity in entities if entity.entity_type == "BANK_ACCOUNT"]
    assert "41 1140 2004 0000 3102 1234 5678" in accounts


def test_regex_detector_redacts_pdf_truncated_bank_account_label(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={"BANK_ACCOUNT"},
        catalog_path=str(db_path),
    )

    entities = detector.detect(
        "Dane obejmują numer telefonu +48 514 222 333, rachun\n"
        "1140 2004 0000 3102 1234 5678, pojazd KR 7MZ18 oraz rachune\n"
        "1090 2590 0000 0001 2345 6789."
    )

    accounts = [entity.raw_text for entity in entities if entity.entity_type == "BANK_ACCOUNT"]
    assert "1140 2004 0000 3102 1234 5678" in accounts
    assert "1090 2590 0000 0001 2345 6789" in accounts


def test_regex_detector_finds_polish_city_and_street_contexts(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={"CITY", "STREET"},
        catalog_path=str(db_path),
    )

    entities = detector.detect(
        "Materiały obejmują korespondencję z Łódźa i dokumenty dla lokalu przy Piotrkowskiej. "
        "Dodatkowe ustalenia dotyczyły przekazania kluczy w Wrocławu przy ul. Długa 41/2."
    )

    by_type = {}
    for entity in entities:
        by_type.setdefault(entity.entity_type, set()).add(entity.raw_text)
    assert {"Łódźa", "Wrocławu"}.issubset(by_type["CITY"])
    assert {"Piotrkowskiej", "Długa"}.issubset(by_type["STREET"])


def test_regex_detector_finds_technical_identifiers_from_contract_context(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={"IP_ADDRESS", "VEHICLE_REGISTRATION", "DEVICE_ID"},
        catalog_path=str(db_path),
    )

    entities = detector.detect("Pojazd KR 7MZ18 i identyfikator host-waw-01. Dostęp z 83.21.144.9.")

    by_type = {entity.entity_type: entity.raw_text for entity in entities}
    assert by_type["VEHICLE_REGISTRATION"] == "KR 7MZ18"
    assert by_type["DEVICE_ID"] == "host-waw-01"
    assert by_type["IP_ADDRESS"] == "83.21.144.9"


def test_regex_detector_does_not_treat_card_fragment_inside_longer_number_as_card(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={"CARD"},
        catalog_path=str(db_path),
    )

    entities = detector.detect("Rachunek 1090 2590 0000 0001 2345 6789.")

    assert entities == []


def test_regex_detector_does_not_treat_plain_words_as_swift_bic(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={"SWIFT_BIC"},
        catalog_path=str(db_path),
    )

    entities = detector.detect("Tekst zawiera slowa wekslowy i wekslowe, ale bez kodu BIC.")

    assert entities == []


def test_regex_detector_avoids_label_only_false_positives(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={
            "CONTRACT_NUMBER",
            "DOCUMENT_NUMBER",
            "CLIENT_ID",
            "EMPLOYEE_ID",
            "INVOICE_NUMBER",
            "ORDER_NUMBER",
            "POLICY_NUMBER",
            "CLAIM_NUMBER",
        },
        catalog_path=str(db_path),
    )

    entities = detector.detect(
        "Umowa zostaje zawarta. Numer identyfikacyjny podmiotu. "
        "Klient: Anna Nowak. Pracownik podpisuje dokument. "
        "Faktura została opłacona. Zamówienie przyjęto. Polisa obowiązuje. Szkoda zgłoszona."
    )

    assert entities == []


def test_regex_detector_still_finds_contextual_reference_numbers(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={
            "CONTRACT_NUMBER",
            "DOCUMENT_NUMBER",
            "CLIENT_ID",
            "EMPLOYEE_ID",
            "INVOICE_NUMBER",
            "ORDER_NUMBER",
            "POLICY_NUMBER",
            "CLAIM_NUMBER",
        },
        catalog_path=str(db_path),
    )

    entities = detector.detect(
        "Umowa nr UM/2026/03/001. Nr dokumentu ABA123456. "
        "Klient ID CL-2026-9001. Pracownik ID EMP-7788. "
        "Faktura nr FV/2026/03/17. Zamówienie nr ORD-2026-44. "
        "Polisa nr POL-2026-88. Szkoda nr CLM-2026-11."
    )

    entity_types = {entity.entity_type for entity in entities}
    assert {
        "CONTRACT_NUMBER",
        "DOCUMENT_NUMBER",
        "CLIENT_ID",
        "EMPLOYEE_ID",
        "INVOICE_NUMBER",
        "ORDER_NUMBER",
        "POLICY_NUMBER",
        "CLAIM_NUMBER",
    }.issubset(entity_types)


def test_regex_detector_finds_polish_compliance_identifiers(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={
            "KRS",
            "REGON",
            "NIP",
            "VAT_ID",
            "TAX_ID",
            "PASSPORT_NUMBER",
            "ID_CARD_NUMBER",
            "DRIVER_LICENSE_NUMBER",
        },
        catalog_path=str(db_path),
    )

    entities = detector.detect(
        "KRS 0000123456. REGON: 192598184. NIP: 8567346215. "
        "VAT UE: PL8567346215. TIN: DE123456789. "
        "Paszport nr AB1234567. Nr dowodu ABA123456. Prawo jazdy nr XYZ-778899."
    )

    entity_types = {entity.entity_type for entity in entities}
    assert {
        "KRS",
        "REGON",
        "NIP",
        "VAT_ID",
        "TAX_ID",
        "PASSPORT_NUMBER",
        "ID_CARD_NUMBER",
        "DRIVER_LICENSE_NUMBER",
    }.issubset(entity_types)


def test_regex_detector_does_not_duplicate_labeled_regon_as_phone(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={"REGON", "PHONE"},
        catalog_path=str(db_path),
    )

    entity_types = {entity.entity_type for entity in detector.detect("REGON: 192598184")}

    assert "REGON" in entity_types
    assert "PHONE" not in entity_types


def test_regex_detector_does_not_duplicate_passport_as_document_number(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={"PASSPORT_NUMBER", "DOCUMENT_NUMBER"},
        catalog_path=str(db_path),
    )

    entity_types = {entity.entity_type for entity in detector.detect("Paszport nr AB1234567")}

    assert "PASSPORT_NUMBER" in entity_types
    assert "DOCUMENT_NUMBER" not in entity_types


def test_regex_detector_avoids_public_form_false_positives(tmp_path) -> None:
    db_path = tmp_path / "regex_catalog.sqlite3"
    detector = RegexDetector(
        allowed_entity_types={
            "CONTRACT_NUMBER",
            "DOCUMENT_NUMBER",
            "CLIENT_ID",
            "EMPLOYEE_ID",
            "POLICY_NUMBER",
            "CLAIM_NUMBER",
            "ORDER_NUMBER",
            "SWIFT_BIC",
            "VAT_ID",
            "TAX_ID",
        },
        catalog_path=str(db_path),
    )

    entities = detector.detect(
        "Skwer kard. S. Wyszyńskiego 9, 01-015 Warszawa. "
        "iod@krrit.gov.pl. Formularz nr 1 informacje o podmiocie. "
        "Wniosek składa pracownik urzędu, dokument podpisuje kierownik jednostki."
    )

    assert entities == []


def test_regex_detector_redacts_labeled_identifiers_without_valid_checksum() -> None:
    entities = RegexDetector(allowed_entity_types={"NIP", "REGON"}).detect(
        "wpisany do CEIDG, NIP 8981234567, REGON 123456789,"
    )

    by_type = {entity.entity_type: entity.raw_text for entity in entities}
    assert by_type["NIP"] == "NIP 8981234567"
    assert by_type["REGON"] == "REGON 123456789"


def test_regex_detector_finds_split_id_card_series_and_number() -> None:
    entities = RegexDetector(allowed_entity_types={"ID_CARD_NUMBER"}).detect(
        "legitymującą się dowodem osobistym seria ABC nr 123456,"
    )

    assert [entity.raw_text for entity in entities] == ["ABC nr 123456"]


def test_regex_detector_flags_quoted_brand_name_as_org() -> None:
    entities = RegexDetector(allowed_entity_types={"ORG"}).detect("Firma „TechNova” zawarła umowę.")

    assert [entity.raw_text for entity in entities] == ["TechNova"]


def test_regex_detector_ignores_quoted_common_words() -> None:
    entities = RegexDetector(allowed_entity_types={"ORG"}).detect(
        "zwany dalej „Pracodawcą”, umowa „na czas nieokreślony” oraz „Umowa”."
    )

    assert entities == []


def test_regex_detector_masks_declined_first_name_with_surname() -> None:
    entities = RegexDetector(allowed_entity_types={"PERSON"}).detect(
        "Panią Anną Nowak, zamieszkałą we Wrocławiu,"
    )

    assert any(entity.raw_text == "Anną Nowak" for entity in entities)
