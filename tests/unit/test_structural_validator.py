from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from posejdon.core.enums import DocumentKind
from posejdon.validators.structural_validator import StructuralValidator

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
_CORE = f"{_PKG}/metadata/core-properties"
_APP = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
    "extended-properties"
)
_RELS_TYPE = "application/vnd.openxmlformats-package.relationships+xml"
_DOC_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)
_CORE_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_APP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"


def _document_xml(*, paragraphs: list[str], tables: int = 1, sect_pr: bool = True) -> str:
    body: list[str] = [f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs]
    for _ in range(tables):
        body.append(
            "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
        )
    if sect_pr:
        body.append(
            '<w:sectPr><w:headerReference w:type="default" r:id="rId1"/>'
            '<w:footerReference w:type="default" r:id="rId2"/></w:sectPr>'
        )
    joined = "".join(body)
    return (
        f'<w:document xmlns:w="{_W}" xmlns:r="{_OFFICE}">'
        f"<w:body>{joined}</w:body></w:document>"
    )


def _rels_xml(*, include_office: bool = True, include_app: bool = True) -> str:
    parts = [f'<Relationships xmlns="{_REL}">']
    if include_office:
        parts.append(
            f'<Relationship Id="rId1" Type="{_OFFICE}/officeDocument" '
            'Target="word/document.xml"/>'
        )
    parts.append(
        f'<Relationship Id="rId2" Type="{_CORE}" Target="docProps/core.xml"/>'
    )
    if include_app:
        parts.append(
            f'<Relationship Id="rId3" Type="{_APP}" Target="docProps/app.xml"/>'
        )
    parts.append("</Relationships>")
    return "".join(parts)


def _header_xml(text: str = "Header") -> str:
    return f'<w:hdr xmlns:w="{_W}"><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:hdr>'


def _footer_xml(text: str = "Footer") -> str:
    return f'<w:ftr xmlns:w="{_W}"><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:ftr>'


def _styles_xml() -> str:
    return f'<w:styles xmlns:w="{_W}"><w:style w:type="paragraph" w:styleId="Normal"/></w:styles>'


def _numbering_xml() -> str:
    return f'<w:numbering xmlns:w="{_W}"><w:abstractNum w:abstractNumId="0"/></w:numbering>'


def _content_types() -> str:
    return (
        f'<Types xmlns="{_CT}">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'<Default Extension="rels" ContentType="{_RELS_TYPE}"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        f'<Override PartName="/word/document.xml" ContentType="{_DOC_TYPE}"/>'
        "</Types>"
    )


def _write_docx(
    path: Path,
    *,
    members: dict[str, str | bytes] | None = None,
    drop: set[str] | None = None,
) -> Path:
    parts: dict[str, str | bytes] = {
        "[Content_Types].xml": _content_types(),
        "_rels/.rels": _rels_xml(),
        "word/document.xml": _document_xml(paragraphs=["Body text"]),
        "word/styles.xml": _styles_xml(),
        "word/numbering.xml": _numbering_xml(),
        "word/header1.xml": _header_xml(),
        "word/footer1.xml": _footer_xml(),
        "word/media/image1.png": b"\x89PNG\r\n\x1a\n",
        "docProps/core.xml": f"<cp:coreProperties xmlns:cp='{_CORE_NS}'/>",
        "docProps/app.xml": f"<Properties xmlns='{_APP_NS}'/>",
    }
    if members:
        parts.update(members)
    for name in drop or set():
        parts.pop(name, None)
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as bundle:
        for name, payload in parts.items():
            data = payload if isinstance(payload, bytes) else payload.encode("utf-8")
            bundle.writestr(name, data)
    path.write_bytes(buffer.getvalue())
    return path


def _validate(
    tmp_path: Path,
    *,
    output_members: dict[str, str | bytes] | None = None,
    drop: set[str] | None = None,
):
    source = _write_docx(tmp_path / "input.docx")
    output = _write_docx(tmp_path / "output.docx", members=output_members, drop=drop)
    return StructuralValidator().validate(
        input_path=str(source),
        output_path=str(output),
        document_kind=DocumentKind.DOCX,
    )


def test_docx_text_only_change_still_passes(tmp_path: Path) -> None:
    result = _validate(
        tmp_path,
        output_members={"word/document.xml": _document_xml(paragraphs=["[PERSON]"])},
    )
    assert result.passed is True
    assert result.errors == []
    assert "docx_package_parts_checked" in result.structure_checks


def test_lost_styles_fails_closed(tmp_path: Path) -> None:
    result = _validate(tmp_path, drop={"word/styles.xml"})
    assert result.passed is False
    assert "lost package part: word/styles.xml" in result.errors


def test_lost_numbering_fails_closed(tmp_path: Path) -> None:
    result = _validate(tmp_path, drop={"word/numbering.xml"})
    assert result.passed is False
    assert "lost package part: word/numbering.xml" in result.errors


def test_lost_header_fails_closed(tmp_path: Path) -> None:
    result = _validate(tmp_path, drop={"word/header1.xml"})
    assert result.passed is False
    assert "lost package part: word/header1.xml" in result.errors


def test_lost_footer_fails_closed(tmp_path: Path) -> None:
    result = _validate(tmp_path, drop={"word/footer1.xml"})
    assert result.passed is False
    assert "lost package part: word/footer1.xml" in result.errors


def test_lost_media_fails_closed(tmp_path: Path) -> None:
    result = _validate(tmp_path, drop={"word/media/image1.png"})
    assert result.passed is False
    assert "lost package part: word/media/image1.png" in result.errors


def test_lost_section_properties_fail_closed(tmp_path: Path) -> None:
    result = _validate(
        tmp_path,
        output_members={
            "word/document.xml": _document_xml(paragraphs=["Body text"], sect_pr=False)
        },
    )
    assert result.passed is False
    assert "lost package part: word/document.xml w:sectPr" in result.errors


def test_lost_table_fails_closed(tmp_path: Path) -> None:
    result = _validate(
        tmp_path,
        output_members={"word/document.xml": _document_xml(paragraphs=["Body text"], tables=0)},
    )
    assert result.passed is False
    assert "DOCX table count changed unexpectedly." in result.errors


def test_lost_office_document_relationship_fails_closed(tmp_path: Path) -> None:
    result = _validate(
        tmp_path,
        output_members={"_rels/.rels": _rels_xml(include_office=False, include_app=False)},
    )
    assert result.passed is False
    assert "lost package relationship: officeDocument" in result.errors
    assert "lost package relationship: extended-properties" in result.errors


def test_header_paragraph_drift_is_an_error(tmp_path: Path) -> None:
    extra = (
        f'<w:hdr xmlns:w="{_W}">'
        "<w:p><w:r><w:t>Header</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>More</w:t></w:r></w:p>"
        "</w:hdr>"
    )
    result = _validate(tmp_path, output_members={"word/header1.xml": extra})
    assert result.passed is False
    assert "Header paragraph count changed." in result.errors
    assert "Header paragraph count changed." not in result.warnings


def test_body_paragraph_drift_beyond_tolerance_is_an_error(tmp_path: Path) -> None:
    result = _validate(
        tmp_path,
        output_members={"word/document.xml": _document_xml(paragraphs=["a", "b", "c", "d"])},
    )
    assert result.passed is False
    assert "Paragraph count changed beyond tolerance." in result.errors
    assert "Paragraph count changed beyond tolerance." not in result.warnings
