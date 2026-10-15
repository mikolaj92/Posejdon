from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from posejdon.core.enums import DocumentKind
from posejdon.validators.structural_validator import (
    StructuralValidator,
    StructureCoverage,
    StructureSnapshot,
)


def _snapshot() -> StructureSnapshot:
    return StructureSnapshot(
        coverage=StructureCoverage.COMPLETE,
        part_names=(
            "word/document.xml",
            "word/styles.xml",
            "word/numbering.xml",
            "word/header1.xml",
            "word/footer1.xml",
            "word/media/image1.png",
        ),
        relationship_types=("officeDocument", "core-properties", "extended-properties"),
        story_ids=("body", "header:0", "footer:0"),
        container_ids=("body:p:0", "header:0:p:0", "footer:0:p:0"),
        table_ids=("table:0",),
        section_property_hashes=("section-hash",),
        body_paragraphs=1,
        header_paragraphs=1,
        footer_paragraphs=1,
    )


def _validate(output: StructureSnapshot | None = None):
    source = _snapshot()
    return StructuralValidator().validate(
        input_path="not-opened.docx",
        output_path="not-opened.docx",
        document_kind=DocumentKind.DOCX,
        source_structure=source,
        output_structure=output or source,
    )


def test_docx_neutral_snapshot_passes_without_opening_document(tmp_path: Path) -> None:
    result = _validate()
    assert result.passed is True
    assert "docx_snapshot_received" in result.structure_checks

    readme = (Path(__file__).resolve().parents[2] / "README.md").read_text(encoding="utf-8")
    assert "No document parsing" not in readme
    assert "DOCX / JSON / XML / PDF parsers live in the host" not in readme
    assert "DOCX checks compare host-supplied structure snapshots" in readme
    assert (
        "`StructuralValidator` reads and parses JSON/XML with Python's standard library."
        in readme
    )

    for kind, content, invalid in (
        (DocumentKind.JSON, '{"name": "source"}', '{"name":'),
        (DocumentKind.XML, '<root name="source"/>', '<root>'),
    ):
        source = tmp_path / f"source.{kind.value}"
        output = tmp_path / f"output.{kind.value}"
        source.write_text(content, encoding="utf-8")
        output.write_text(content, encoding="utf-8")
        result = StructuralValidator().validate(
            input_path=str(source), output_path=str(output), document_kind=kind
        )
        assert result.passed is True

        output.write_text(invalid, encoding="utf-8")
        result = StructuralValidator().validate(
            input_path=str(source), output_path=str(output), document_kind=kind
        )
        assert result.passed is False
        assert any("unreadable or invalid" in error for error in result.errors)


def test_docx_requires_host_snapshots() -> None:
    result = StructuralValidator().validate(
        input_path="not-opened.docx",
        output_path="not-opened.docx",
        document_kind=DocumentKind.DOCX,
    )
    assert result.passed is False
    assert "DOCX structure snapshots are required" in result.errors[0]


def test_incomplete_snapshot_fails_closed() -> None:
    result = _validate(replace(_snapshot(), coverage=StructureCoverage.INCOMPLETE))
    assert result.passed is False
    assert "coverage is incomplete" in result.errors[0]


def test_lost_parts_relationships_stories_tables_and_section_fail_closed() -> None:
    output = replace(
        _snapshot(),
        part_names=("word/document.xml",),
        relationship_types=("officeDocument",),
        story_ids=("body",),
        table_ids=(),
        section_property_hashes=(),
    )
    result = _validate(output)
    assert result.passed is False
    assert "lost package part: word/styles.xml" in result.errors
    assert "lost package relationship: core-properties" in result.errors
    assert "lost document story: header:0" in result.errors
    assert "DOCX table count changed unexpectedly." in result.errors
    assert "lost package part: word/document.xml w:sectPr" in result.errors


def test_paragraph_and_header_footer_count_drift_fails_closed() -> None:
    output = replace(_snapshot(), body_paragraphs=5, header_paragraphs=2, footer_paragraphs=0)
    result = _validate(output)
    assert result.passed is False
    assert "Paragraph count changed beyond tolerance." in result.errors
    assert "Header paragraph count changed." in result.errors
    assert "Footer paragraph count changed." in result.errors
