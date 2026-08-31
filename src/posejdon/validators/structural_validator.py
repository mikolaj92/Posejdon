from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from posejdon.core.enums import DocumentKind
from posejdon.domain.reports import ValidationResult

_BODY_PARAGRAPH_TOLERANCE = 2
_REQUIRED_PACKAGE_REL_KINDS = frozenset(
    {"officeDocument", "core-properties", "extended-properties"}
)
_TRACKED_EXACT_PARTS = frozenset({"word/styles.xml", "word/numbering.xml"})
_TRACKED_PART_PREFIXES = ("word/header", "word/footer", "word/media/")


class StructureCoverage(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True)
class StructureSnapshot:
    """Domain-neutral mechanical structure supplied by a document host.

    Posejdon core compares these facts. It never opens DOCX, ZIP, OPC or XML.
    """

    coverage: StructureCoverage
    part_names: tuple[str, ...]
    relationship_types: tuple[str, ...]
    story_ids: tuple[str, ...]
    container_ids: tuple[str, ...]
    table_ids: tuple[str, ...]
    section_property_hashes: tuple[str, ...]
    body_paragraphs: int
    header_paragraphs: int
    footer_paragraphs: int
    diagnostics: tuple[str, ...] = ()


class StructuralValidator:
    def validate(
        self,
        *,
        input_path: str,
        output_path: str,
        document_kind: DocumentKind,
        source_structure: StructureSnapshot | None = None,
        output_structure: StructureSnapshot | None = None,
    ) -> ValidationResult:
        warnings: list[str] = []
        errors: list[str] = []
        checks: list[str] = []

        try:
            if document_kind == DocumentKind.DOCX:
                if source_structure is None or output_structure is None:
                    errors.append("DOCX structure snapshots are required from the document host.")
                    checks.append("docx_snapshot_required")
                else:
                    self._validate_docx(source_structure, output_structure, errors, checks)
            elif document_kind == DocumentKind.PDF:
                self._validate_pdf(input_path, output_path, errors, warnings, checks)
            elif document_kind == DocumentKind.JSON:
                self._validate_segments(
                    input_path,
                    output_path,
                    opened_check="json_opened",
                    count_check="json_readable",
                    warnings=warnings,
                    checks=checks,
                )
            elif document_kind == DocumentKind.XML:
                self._validate_segments(
                    input_path,
                    output_path,
                    opened_check="xml_opened",
                    count_check="xml_readable",
                    warnings=warnings,
                    checks=checks,
                )
            elif document_kind == DocumentKind.TEXT:
                Path(input_path).read_text(encoding="utf-8")
                Path(output_path).read_text(encoding="utf-8")
                checks.append("text_opened")
        except Exception as exc:
            errors.append(str(exc))

        return ValidationResult(
            passed=not errors,
            structure_checks=checks,
            warnings=warnings,
            errors=errors,
        )

    def _validate_docx(
        self,
        source: StructureSnapshot,
        output: StructureSnapshot,
        errors: list[str],
        checks: list[str],
    ) -> None:
        checks.append("docx_snapshot_received")
        if (
            source.coverage is StructureCoverage.INCOMPLETE
            or output.coverage is StructureCoverage.INCOMPLETE
        ):
            errors.append("DOCX structure snapshot coverage is incomplete.")
            checks.append("docx_coverage_checked")
            return
        checks.append("docx_coverage_checked")

        if abs(source.body_paragraphs - output.body_paragraphs) > _BODY_PARAGRAPH_TOLERANCE:
            errors.append("Paragraph count changed beyond tolerance.")
        checks.append("docx_paragraph_count_checked")

        if source.table_ids != output.table_ids:
            errors.append("DOCX table count changed unexpectedly.")
        checks.append("docx_table_count_checked")

        if source.header_paragraphs != output.header_paragraphs:
            errors.append("Header paragraph count changed.")
        checks.append("docx_header_count_checked")

        if source.footer_paragraphs != output.footer_paragraphs:
            errors.append("Footer paragraph count changed.")
        checks.append("docx_footer_count_checked")

        if source.section_property_hashes and not output.section_property_hashes:
            errors.append("lost package part: word/document.xml w:sectPr")
        checks.append("docx_section_checked")

        tracked = {
            name
            for name in source.part_names
            if name in _TRACKED_EXACT_PARTS or name.startswith(_TRACKED_PART_PREFIXES)
        }
        output_names = set(output.part_names)
        for part in sorted(tracked - output_names):
            errors.append(f"lost package part: {part}")
        checks.append("docx_package_parts_checked")

        missing_rels = (set(source.relationship_types) & _REQUIRED_PACKAGE_REL_KINDS) - set(
            output.relationship_types
        )
        for kind in sorted(missing_rels):
            errors.append(f"lost package relationship: {kind}")
        checks.append("docx_package_relationships_checked")

        for story in sorted(set(source.story_ids) - set(output.story_ids)):
            errors.append(f"lost document story: {story}")
        checks.append("docx_stories_checked")

    def _validate_pdf(
        self,
        input_path: str,
        output_path: str,
        errors: list[str],
        warnings: list[str],
        checks: list[str],
    ) -> None:
        errors.append(
            "PDF structure checks belong to the host; the library does not parse documents"
        )
        checks.append("pdf_rejected_in_library")

    def _validate_segments(
        self,
        input_path: str,
        output_path: str,
        *,
        opened_check: str,
        count_check: str,
        warnings: list[str],
        checks: list[str],
    ) -> None:
        Path(input_path).read_text(encoding="utf-8")
        Path(output_path).read_text(encoding="utf-8")
        checks.append(opened_check)
        checks.append(count_check)
