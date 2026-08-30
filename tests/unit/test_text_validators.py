from __future__ import annotations

import sys
import types
from dataclasses import dataclass

class _FitzStub(types.ModuleType):
    attempted_paths: list[str] = []

    def open(self, path: str):  # pragma: no cover - should never be reached for TEXT
        self.attempted_paths.append(path)
        raise AssertionError(f"attempted PDF parsing for {path}")


@dataclass
class _ParsedTextSegment:
    segment_id: str
    text: str
    container_id: str
    section_id: str
    start_offset: int
    end_offset: int
    page_index: int | None = None


_fitz_stub = _FitzStub("fitz")
sys.modules.setdefault("docx", types.SimpleNamespace(Document=object))
sys.modules.setdefault("posejdon_docs", types.ModuleType("posejdon_docs"))
sys.modules.setdefault("posejdon_docs.parsers", types.ModuleType("posejdon_docs.parsers"))
sys.modules.setdefault(
    "posejdon_docs.parsers.base",
    types.SimpleNamespace(ParsedTextSegment=_ParsedTextSegment),
)
sys.modules.setdefault(
    "posejdon_docs.parsers.json_parser",
    types.SimpleNamespace(JSONParser=object),
)
sys.modules.setdefault(
    "posejdon_docs.parsers.xml_parser",
    types.SimpleNamespace(XMLParser=object),
)
sys.modules.setdefault("fitz", _fitz_stub)
from posejdon.validators.leakage_validator import LeakageValidator
from posejdon.validators.structural_validator import StructuralValidator

from posejdon.core.enums import DocumentKind
from posejdon.domain.entities import SensitiveEntity

_LEGAL_ROLE_CONSENT_TEXT = (
    "Pełnomocnik składa oświadczenie w imieniu Pracownika. "
    "Zgoda dotyczy przetwarzania danych."
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
        ],
    )

    assert result.leaked_values_detected is False
    assert result.findings == []
    assert result.normalized_findings == []
    assert result.findings_by_segment == []


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
    assert _fitz_stub.attempted_paths == []
