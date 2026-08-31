"""Host-supplied text segments. The library does not parse documents (#54)."""

from __future__ import annotations

from pydantic import BaseModel


class TextSegment(BaseModel):
    """One addressable text span. Host parsers (posejdon-docs / Docxtor) fill this."""

    segment_id: str
    text: str
    container_id: str
    page_index: int | None = None
    section_id: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
