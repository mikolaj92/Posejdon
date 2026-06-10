from __future__ import annotations

from dataclasses import dataclass

from posejdon.domain.entities import SensitiveEntity
from posejdon.domain.policies import ConfidenceThresholds

SEMANTIC_ENTITY_TYPES = {"PERSON", "ORG", "ADDRESS"}


@dataclass(slots=True)
class ConfidencePolicy:
    thresholds: ConfidenceThresholds

    def should_accept(self, entity: SensitiveEntity) -> bool:
        if entity.entity_type in SEMANTIC_ENTITY_TYPES and entity.source_detector != "regex":
            if entity.metadata.get("semantic_conflict") == "true":
                return False
            support_count = int(entity.metadata.get("support_count", "1"))
            required_confidence = max(self.thresholds.accept_threshold, 0.85)
            if support_count >= 2:
                required_confidence -= 0.05
            return entity.confidence >= required_confidence
        return entity.confidence >= self.thresholds.accept_threshold

    def should_review(self, entity: SensitiveEntity) -> bool:
        if entity.entity_type in SEMANTIC_ENTITY_TYPES:
            return (
                entity.confidence >= self.thresholds.review_threshold
                or entity.metadata.get("semantic_conflict") == "true"
            )
        return entity.confidence >= self.thresholds.review_threshold
