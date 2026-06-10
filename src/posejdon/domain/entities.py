from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from posejdon.domain.models import BoundingBox


class MentionProvenance(BaseModel):
    canonical_entity_id: str
    mention_cluster_id: str
    derived_from: str
    mention_source: str
    mention_rule: str


class SensitiveEntity(BaseModel):
    MENTION_PROVENANCE_KEYS: ClassVar[tuple[str, ...]] = (
        "canonical_entity_id",
        "mention_cluster_id",
        "derived_from",
        "mention_source",
        "mention_rule",
    )

    entity_id: str
    entity_type: str
    raw_text: str
    normalized_text: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_detector: str
    segment_id: str | None = None
    page_index: int | None = None
    section_id: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    bbox: BoundingBox | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    def mention_provenance(self) -> MentionProvenance | None:
        payload = {
            key: value for key in self.MENTION_PROVENANCE_KEYS if (value := self.metadata.get(key))
        }
        if not payload:
            return None
        return MentionProvenance.model_validate(payload)

    def with_mention_provenance(self, provenance: MentionProvenance) -> SensitiveEntity:
        return self.model_copy(
            update={
                "metadata": {
                    **self.metadata,
                    **provenance.model_dump(),
                }
            }
        )
