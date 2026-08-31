from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from posejdon.core.enums import DocumentKind
from posejdon.domain.reports import ValidationResult

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_BODY_PARAGRAPH_TOLERANCE = 2
_REQUIRED_PACKAGE_REL_KINDS = frozenset(
    {
        "officeDocument",
        "core-properties",
        "extended-properties",
    }
)
_TRACKED_EXACT_PARTS = frozenset({"word/styles.xml", "word/numbering.xml"})
_TRACKED_PART_PREFIXES = ("word/header", "word/footer", "word/media/")


class StructuralValidator:
    def validate(
        self, *, input_path: str, output_path: str, document_kind: DocumentKind
    ) -> ValidationResult:
        warnings: list[str] = []
        errors: list[str] = []
        checks: list[str] = []

        try:
            if document_kind == DocumentKind.DOCX:
                self._validate_docx(input_path, output_path, errors, checks)
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
        input_path: str,
        output_path: str,
        errors: list[str],
        checks: list[str],
    ) -> None:
        source = _package_snapshot(input_path)
        output = _package_snapshot(output_path)
        checks.append("docx_opened")

        if abs(source.body_paragraphs - output.body_paragraphs) > _BODY_PARAGRAPH_TOLERANCE:
            errors.append("Paragraph count changed beyond tolerance.")
        checks.append("docx_paragraph_count_checked")

        if source.tables != output.tables:
            errors.append("DOCX table count changed unexpectedly.")
        checks.append("docx_table_count_checked")

        if source.header_paragraphs != output.header_paragraphs:
            errors.append("Header paragraph count changed.")
        checks.append("docx_header_count_checked")

        if source.footer_paragraphs != output.footer_paragraphs:
            errors.append("Footer paragraph count changed.")
        checks.append("docx_footer_count_checked")

        if source.has_sect_pr and not output.has_sect_pr:
            errors.append("lost package part: word/document.xml w:sectPr")
        checks.append("docx_section_checked")

        for part in sorted(source.tracked_parts - output.names):
            errors.append(f"lost package part: {part}")
        checks.append("docx_package_parts_checked")

        missing_rels = (
            source.package_rel_kinds & _REQUIRED_PACKAGE_REL_KINDS
        ) - output.package_rel_kinds
        for kind in sorted(missing_rels):
            errors.append(f"lost package relationship: {kind}")
        checks.append("docx_package_relationships_checked")

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


class _DocxSnapshot:
    def __init__(
        self,
        *,
        names: set[str],
        body_paragraphs: int,
        tables: int,
        header_paragraphs: int,
        footer_paragraphs: int,
        has_sect_pr: bool,
        tracked_parts: set[str],
        package_rel_kinds: set[str],
    ) -> None:
        self.names = names
        self.body_paragraphs = body_paragraphs
        self.tables = tables
        self.header_paragraphs = header_paragraphs
        self.footer_paragraphs = footer_paragraphs
        self.has_sect_pr = has_sect_pr
        self.tracked_parts = tracked_parts
        self.package_rel_kinds = package_rel_kinds


def _package_snapshot(path: str) -> _DocxSnapshot:
    with zipfile.ZipFile(path) as bundle:
        names = set(bundle.namelist())
        document = bundle.read("word/document.xml") if "word/document.xml" in names else b""
        rels = bundle.read("_rels/.rels") if "_rels/.rels" in names else b""
        header_paragraphs = 0
        footer_paragraphs = 0
        for name in names:
            if _is_header_part(name):
                header_paragraphs += _element_count(bundle.read(name), f"{_W}p")
            elif _is_footer_part(name):
                footer_paragraphs += _element_count(bundle.read(name), f"{_W}p")
        tracked = {name for name in names if _is_tracked_part(name)}
        return _DocxSnapshot(
            names=names,
            body_paragraphs=_body_paragraph_count(document),
            tables=_body_table_count(document),
            header_paragraphs=header_paragraphs,
            footer_paragraphs=footer_paragraphs,
            has_sect_pr=_has_sect_pr(document),
            tracked_parts=tracked,
            package_rel_kinds=_relationship_kinds(rels),
        )


def _is_header_part(name: str) -> bool:
    return name.startswith("word/header") and name.endswith(".xml")


def _is_footer_part(name: str) -> bool:
    return name.startswith("word/footer") and name.endswith(".xml")


def _is_tracked_part(name: str) -> bool:
    if name in _TRACKED_EXACT_PARTS:
        return True
    return name.startswith(_TRACKED_PART_PREFIXES)


def _body_paragraph_count(document_xml: bytes) -> int:
    body = _document_body(document_xml)
    if body is None:
        return 0
    return sum(1 for child in list(body) if child.tag == f"{_W}p")


def _body_table_count(document_xml: bytes) -> int:
    body = _document_body(document_xml)
    if body is None:
        return 0
    return sum(1 for child in list(body) if child.tag == f"{_W}tbl")


def _has_sect_pr(document_xml: bytes) -> bool:
    if not document_xml:
        return False
    root = ET.fromstring(document_xml)
    return any(element.tag == f"{_W}sectPr" for element in root.iter())


def _document_body(document_xml: bytes) -> ET.Element | None:
    if not document_xml:
        return None
    return ET.fromstring(document_xml).find(f"{_W}body")


def _element_count(xml_bytes: bytes, tag: str) -> int:
    if not xml_bytes:
        return 0
    return sum(1 for element in ET.fromstring(xml_bytes).iter(tag))


def _relationship_kinds(rels_xml: bytes) -> set[str]:
    if not rels_xml:
        return set()
    kinds: set[str] = set()
    for rel in ET.fromstring(rels_xml).findall(f"{_REL}Relationship"):
        rel_type = rel.get("Type") or ""
        kinds.add(rel_type.rsplit("/", 1)[-1])
    return kinds
