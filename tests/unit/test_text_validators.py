from __future__ import annotations

import importlib
import sys

from posejdon.core.enums import DocumentKind
from posejdon.domain.entities import SensitiveEntity
from posejdon.validators.leakage_validator import LeakageValidator
from posejdon.validators.structural_validator import StructuralValidator

_LEGAL_ROLE_CONSENT_TEXT = (
    "Pełnomocnik składa oświadczenie w imieniu Pracownika. "
    "Administratora danych informuje się o zakresie przetwarzania. "
    "Zgoda dotyczy przetwarzania danych."
)
_CONTRACT_ROLE_TEXT = (
    "Wykonawca świadczy usługi na rzecz Zamawiającego. "
    "Strony zawierają Umowy w zakresie Zamówienia. "
    "Poufne informacje pozostają u stron."
)
_CONTRACT_ROLE_SURFACES = (
    "Wykonawca",
    "Zamawiającego",
    "Strony",
    "Umowy",
    "Zamówienia",
    "Poufne",
)


def _entity(**kwargs) -> SensitiveEntity:
    payload = {
        "entity_id": "entity-1",
        "entity_type": "PERSON",
        "raw_text": "Jan Kowalski",
        "normalized_text": "jan kowalski",
        "confidence": 0.9,
        "source_detector": "gliner",
    }
    payload.update(kwargs)
    return SensitiveEntity(**payload)


def _scan(tmp_path, text: str, entities: list[SensitiveEntity]):
    output = tmp_path / "output.txt"
    output.write_text(text, encoding="utf-8")
    return LeakageValidator().validate(
        output_path=str(output),
        document_kind=DocumentKind.TEXT,
        entities=entities,
    )


def test_leakage_validator_scans_text_file_for_raw_sensitive_value(tmp_path) -> None:
    output = tmp_path / "output.txt"
    output.write_text("Contact Jan Kowalski before publishing.\n", encoding="utf-8")

    result = LeakageValidator().validate(
        output_path=str(output),
        document_kind=DocumentKind.TEXT,
        entities=[
            SensitiveEntity(
                entity_id="person-1",
                entity_type="PERSON",
                raw_text="Jan Kowalski",
                normalized_text="jan kowalski",
                confidence=0.99,
                source_detector="test",
            )
        ],
    )

    assert result.leaked_values_detected is True
    assert result.findings == ["Jan Kowalski"]
    assert result.findings_by_segment[0].segment_id == "text:0"


def test_leakage_validator_ignores_unmatched_legal_role_common_noun(tmp_path) -> None:
    result = _scan(
        tmp_path,
        _LEGAL_ROLE_CONSENT_TEXT,
        [
            _entity(
                entity_id="role-1",
                raw_text="Pełnomocnik",
                normalized_text="pełnomocnik",
                confidence=0.67,
                metadata={"semantic_conflict": "true"},
            ),
            _entity(
                entity_id="role-2",
                entity_type="ORG",
                raw_text="Pracownika",
                normalized_text="pracownika",
                confidence=0.79,
                metadata={
                    "semantic_conflict": "true",
                    "conflicting_entity_types": "PERSON",
                },
            ),
            _entity(
                entity_id="role-3",
                raw_text="Administratora",
                normalized_text="administratora",
                confidence=0.62,
                source_detector="spacy",
            ),
        ],
    )

    assert result.leaked_values_detected is False
    assert result.findings == []
    assert result.normalized_findings == []
    assert result.findings_by_segment == []


def test_leakage_validator_ignores_unmatched_inflected_contract_role_nouns(tmp_path) -> None:
    result = _scan(
        tmp_path,
        _CONTRACT_ROLE_TEXT,
        [
            _entity(
                entity_id=f"role-{index}",
                entity_type="PERSON" if surface != "Zamawiającego" else "ORG",
                raw_text=surface,
                normalized_text=surface.casefold(),
                confidence=0.67,
                source_detector="gliner",
            )
            for index, surface in enumerate(_CONTRACT_ROLE_SURFACES, start=1)
        ],
    )

    assert result.leaked_values_detected is False
    assert result.findings == []
    assert result.normalized_findings == []
    assert result.findings_by_segment == []


def test_leakage_validator_ignores_false_nip_without_checksum(tmp_path) -> None:
    result = _scan(
        tmp_path,
        "Nr NIP: 1234563218.",
        [
            _entity(
                entity_id="false-nip",
                entity_type="NIP",
                raw_text="Nr",
                normalized_text="nr",
                source_detector="gliner",
                confidence=0.72,
            )
        ],
    )

    assert result.leaked_values_detected is False
    assert result.findings == []
    assert result.normalized_findings == []


def test_leakage_validator_ignores_unmatched_payment_and_order_nouns(tmp_path) -> None:
    result = _scan(
        tmp_path,
        "Zapłaty wynikają ze Zlecenia.",
        [
            _entity(
                entity_id="pay-1",
                raw_text="Zapłaty",
                normalized_text="zapłaty",
                source_detector="spacy",
                confidence=0.75,
            ),
            _entity(
                entity_id="order-1",
                entity_type="ORG",
                raw_text="Zlecenia",
                normalized_text="zlecenia",
                source_detector="spacy",
                confidence=0.75,
            ),
        ],
    )

    assert result.leaked_values_detected is False
    assert result.findings == []
    assert result.normalized_findings == []


def test_leakage_validator_still_fail_closes_on_residual_email(tmp_path) -> None:
    text = f"{_LEGAL_ROLE_CONSENT_TEXT} Kontakt: jan.kowalski@example.com"
    result = _scan(
        tmp_path,
        text,
        [
            _entity(
                entity_id="role-1",
                raw_text="Pełnomocnik",
                normalized_text="pełnomocnik",
                metadata={"semantic_conflict": "true"},
            ),
            _entity(
                entity_id="email-1",
                entity_type="EMAIL",
                raw_text="jan.kowalski@example.com",
                normalized_text="jan.kowalski@example.com",
                source_detector="regex",
                confidence=0.99,
            ),
        ],
    )

    assert result.leaked_values_detected is True
    assert result.findings == ["jan.kowalski@example.com"]
    assert "Pełnomocnik" not in result.findings
    assert "Pełnomocnik" not in result.normalized_findings


def test_leakage_validator_still_fail_closes_on_residual_nip_and_krs(tmp_path) -> None:
    text = f"{_LEGAL_ROLE_CONSENT_TEXT} NIP: 1234563218 KRS 0000123456"
    result = _scan(
        tmp_path,
        text,
        [
            _entity(
                entity_id="nip-1",
                entity_type="NIP",
                raw_text="1234563218",
                normalized_text="1234563218",
                source_detector="regex",
                confidence=0.99,
            ),
            _entity(
                entity_id="krs-1",
                entity_type="KRS",
                raw_text="KRS 0000123456",
                normalized_text="krs 0000123456",
                source_detector="regex",
                confidence=0.99,
            ),
        ],
    )

    assert result.leaked_values_detected is True
    assert result.findings == ["1234563218", "KRS 0000123456"]


def test_leakage_validator_still_fail_closes_on_planned_person_name(tmp_path) -> None:
    text = f"{_LEGAL_ROLE_CONSENT_TEXT} Podpis: Jan Kowalski"
    result = _scan(
        tmp_path,
        text,
        [
            _entity(
                entity_id="role-1",
                raw_text="Pełnomocnik",
                normalized_text="pełnomocnik",
                metadata={"semantic_conflict": "true"},
            ),
            _entity(
                entity_id="person-1",
                raw_text="Jan Kowalski",
                normalized_text="jan kowalski",
                source_detector="regex",
                confidence=0.99,
            ),
        ],
    )

    assert result.leaked_values_detected is True
    assert result.findings == ["Jan Kowalski"]
    assert "Pełnomocnik" not in result.findings


def test_structural_validator_accepts_readable_text_files_and_reports_text_checks(tmp_path) -> None:
    original = tmp_path / "input.txt"
    output = tmp_path / "output.txt"
    original.write_text("First line\nSecond line\n", encoding="utf-8")
    output.write_text("First line\n[PERSON]\n", encoding="utf-8")

    result = StructuralValidator().validate(
        input_path=str(original),
        output_path=str(output),
        document_kind=DocumentKind.TEXT,
    )

    assert result.passed is True
    assert result.errors == []
    assert "text_opened" in result.structure_checks
    assert not any(check.startswith("pdf_") for check in result.structure_checks)


def test_leakage_validator_refuses_document_paths_without_host_segments(tmp_path) -> None:
    path = tmp_path / "sample.docx"
    path.write_bytes(b"pk")
    try:
        LeakageValidator().validate(
            output_path=str(path),
            document_kind=DocumentKind.DOCX,
            entities=[],
        )
    except ValueError as exc:
        assert "does not parse" in str(exc)
    else:
        raise AssertionError("DOCX leakage must fail closed without host segments")


def test_document_parser_modules_are_not_imported_by_library_validators() -> None:
    for name in (
        "fitz",
        "docx",
        "posejdon_docs",
        "posejdon_docs.parsers",
        "posejdon_docs.parsers.base",
    ):
        sys.modules.pop(name, None)
    importlib.reload(importlib.import_module("posejdon.validators.leakage_validator"))
    importlib.reload(importlib.import_module("posejdon.validators.structural_validator"))
    importlib.reload(importlib.import_module("posejdon.planners.reinjection_planner"))
    for name in ("fitz", "docx", "posejdon_docs"):
        assert name not in sys.modules


def test_leakage_validator_ignores_related_party_legal_phrase(tmp_path) -> None:
    result = _scan(
        tmp_path,
        "Podmiot Powiązany przekazuje dane podmiotowi powiązanemu.",
        [
            _entity(
                entity_id="related-1",
                raw_text="Podmiot Powiązany",
                normalized_text="podmiot powiązany",
                source_detector="spacy",
                confidence=0.75,
            )
        ],
    )

    assert result.leaked_values_detected is False
    assert result.findings == []
    assert result.normalized_findings == []
