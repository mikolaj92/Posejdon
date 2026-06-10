from __future__ import annotations

from pydantic import BaseModel, Field

from posejdon.core.enums import DocumentKind, ReplacementKind


class WriteTarget(BaseModel):
    segment_id: str | None = None
    container_id: str
    start_offset: int | None = None
    end_offset: int | None = None
    page_index: int | None = None


class Replacement(BaseModel):
    entity_id: str
    replacement_text: str
    replacement_kind: ReplacementKind
    source_text: str | None = Field(default=None, exclude=True)
    justification: str
    confidence: float = Field(ge=0.0, le=1.0)
    write_targets: list[WriteTarget] = Field(default_factory=list)


class ReplacementPlan(BaseModel):
    document_kind: DocumentKind
    replacements: list[Replacement] = Field(default_factory=list)
    unresolved_conflicts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
