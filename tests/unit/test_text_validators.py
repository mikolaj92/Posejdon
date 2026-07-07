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
