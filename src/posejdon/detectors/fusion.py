from __future__ import annotations

from dataclasses import dataclass

from posejdon.domain.entities import SensitiveEntity

CANONICAL_ENTITY_TYPES: dict[str, str] = {
    "PER": "PERSON",
    "PERSON": "PERSON",
    "PERSNAME": "PERSON",
    "ORG": "ORG",
    "ORGANIZATION": "ORG",
    "ORGNAME": "ORG",
    "COMPANY": "ORG",
    "ADDRESS": "ADDRESS",
    "ADDR": "ADDRESS",
    "POSTAL_ADDRESS": "ADDRESS",
}

SEMANTIC_ENTITY_TYPES = {"PERSON", "ORG", "ADDRESS"}


def spans_overlap(left: SensitiveEntity, right: SensitiveEntity) -> bool:
    if left.start_offset is None or left.end_offset is None:
        return False
    if right.start_offset is None or right.end_offset is None:
        return False
    return not (left.end_offset <= right.start_offset or right.end_offset <= left.start_offset)


@dataclass(slots=True)
class DetectorFusion:
    prefer_detectors: tuple[str, ...] = ("regex", "presidio", "gliner", "spacy")

    def merge(self, candidates: list[SensitiveEntity]) -> list[SensitiveEntity]:
        normalized = [self._canonicalize(entity) for entity in candidates]
        ordered = sorted(
            normalized,
            key=lambda entity: (
                entity.start_offset or 0,
                -(entity.end_offset or 0),
                -entity.confidence,
                self._priority(entity.source_detector),
            ),
        )

        selected: list[SensitiveEntity] = []
        consumed_indexes: set[int] = set()
        for index, entity in enumerate(ordered):
            if index in consumed_indexes:
                continue
            if entity.entity_type in SEMANTIC_ENTITY_TYPES:
                cluster = [entity]
                consumed_indexes.add(index)
                expanded = True
                while expanded:
                    expanded = False
                    for candidate_index in range(index + 1, len(ordered)):
                        if candidate_index in consumed_indexes:
                            continue
                        candidate = ordered[candidate_index]
                        if candidate.entity_type not in SEMANTIC_ENTITY_TYPES:
                            continue
                        if any(spans_overlap(existing, candidate) for existing in cluster):
                            cluster.append(candidate)
                            consumed_indexes.add(candidate_index)
                            expanded = True
                winner = self._select_semantic_winner(cluster)
                selected = [
                    existing
                    for existing in selected
                    if not (
                        existing.entity_type in SEMANTIC_ENTITY_TYPES
                        and any(spans_overlap(existing, candidate) for candidate in cluster)
                    )
                ]
                selected.append(winner)
                continue

            overlapping = [
                existing
                for existing in selected
                if spans_overlap(existing, entity)
                and (
                    existing.entity_type == entity.entity_type
                    or (
                        existing.entity_type in SEMANTIC_ENTITY_TYPES
                        and entity.entity_type in SEMANTIC_ENTITY_TYPES
                    )
                )
            ]
            if not overlapping:
                selected.append(entity)
                continue
            if entity.entity_type not in SEMANTIC_ENTITY_TYPES:
                conflicting = next(
                    (
                        existing
                        for existing in overlapping
                        if existing.entity_type == entity.entity_type
                    ),
                    None,
                )
                if conflicting is None:
                    selected.append(entity)
                    continue
                if self._should_replace(current=conflicting, challenger=entity):
                    selected.remove(conflicting)
                    selected.append(self._merge_provenance(conflicting, entity))
                else:
                    selected[selected.index(conflicting)] = self._merge_provenance(
                        entity,
                        conflicting,
                    )
                continue

        return sorted(
            selected,
            key=lambda entity: (entity.start_offset or 0, entity.end_offset or 0),
        )

    def _canonicalize(self, entity: SensitiveEntity) -> SensitiveEntity:
        canonical_type = CANONICAL_ENTITY_TYPES.get(entity.entity_type, entity.entity_type)
        supporting_detectors = self._metadata_list(entity.metadata, "supporting_detectors")
        metadata = {
            **entity.metadata,
            "supporting_detectors": ",".join(supporting_detectors or [entity.source_detector]),
            "support_count": entity.metadata.get("support_count", "1"),
            "original_entity_type": entity.metadata.get("original_entity_type", entity.entity_type),
        }
        return entity.model_copy(
            update={
                "entity_type": canonical_type,
                "metadata": metadata,
            }
        )

    @staticmethod
    def _metadata_list(metadata: dict[str, str], key: str) -> list[str]:
        raw = metadata.get(key, "")
        if not raw:
            return []
        return [item for item in raw.split(",") if item]

    def _select_semantic_winner(self, group: list[SensitiveEntity]) -> SensitiveEntity:
        grouped: dict[str, list[SensitiveEntity]] = {}
        for entity in group:
            grouped.setdefault(entity.entity_type, []).append(entity)

        best_type = max(
            grouped,
            key=lambda entity_type: (
                any(item.source_detector == "regex" for item in grouped[entity_type]),
                len(grouped[entity_type]),
                max(item.confidence for item in grouped[entity_type]),
                -min(self._priority(item.source_detector) for item in grouped[entity_type]),
                max(
                    (item.end_offset or 0) - (item.start_offset or 0)
                    for item in grouped[entity_type]
                ),
            ),
        )
        winner = max(
            grouped[best_type],
            key=lambda entity: (
                entity.source_detector == "regex",
                entity.confidence,
                -self._priority(entity.source_detector),
                (entity.end_offset or 0) - (entity.start_offset or 0),
            ),
        )
        conflict_types = sorted(
            {item.entity_type for item in group if item.entity_type != best_type}
        )
        supporting_detectors = sorted({item.source_detector for item in grouped[best_type]})
        return winner.model_copy(
            update={
                "metadata": {
                    **winner.metadata,
                    "supporting_detectors": ",".join(supporting_detectors),
                    "support_count": str(len(grouped[best_type])),
                    "semantic_conflict": str(bool(conflict_types)).lower(),
                    "conflicting_entity_types": ",".join(conflict_types),
                }
            }
        )

    def _merge_provenance(
        self,
        current: SensitiveEntity,
        challenger: SensitiveEntity,
    ) -> SensitiveEntity:
        supporting_detectors = sorted(
            {
                *self._metadata_list(current.metadata, "supporting_detectors"),
                *self._metadata_list(challenger.metadata, "supporting_detectors"),
                current.source_detector,
                challenger.source_detector,
            }
        )
        return challenger.model_copy(
            update={
                "metadata": {
                    **challenger.metadata,
                    "supporting_detectors": ",".join(supporting_detectors),
                    "support_count": str(len(supporting_detectors)),
                }
            }
        )

    def _priority(self, detector_name: str) -> int:
        try:
            return self.prefer_detectors.index(detector_name)
        except ValueError:
            return len(self.prefer_detectors)

    def _should_replace(self, *, current: SensitiveEntity, challenger: SensitiveEntity) -> bool:
        if current.source_detector == "regex" and challenger.source_detector != "regex":
            return False
        if challenger.source_detector == "regex" and current.source_detector != "regex":
            return True
        current_span = (current.end_offset or 0) - (current.start_offset or 0)
        challenger_span = (challenger.end_offset or 0) - (challenger.start_offset or 0)
        if challenger.confidence > current.confidence + 0.05:
            return True
        if challenger.confidence == current.confidence and challenger_span > current_span:
            return True
        if abs(challenger.confidence - current.confidence) < 0.01:
            return self._priority(challenger.source_detector) < self._priority(
                current.source_detector
            )
        return False
