from __future__ import annotations

from posejdon.domain.entities import SensitiveEntity


class OverlapResolver:
    def resolve(
        self,
        entities: list[SensitiveEntity],
    ) -> tuple[list[SensitiveEntity], list[str]]:
        ordered = sorted(
            entities,
            key=lambda entity: (
                entity.start_offset or 0,
                -(entity.end_offset or 0),
                -entity.confidence,
            ),
        )
        selected: list[SensitiveEntity] = []
        conflicts: list[str] = []
        for candidate in ordered:
            overlap = next(
                (
                    existing
                    for existing in selected
                    if self._overlaps(existing, candidate)
                    and existing.section_id == candidate.section_id
                    and existing.page_index == candidate.page_index
                ),
                None,
            )
            if overlap is None:
                selected.append(candidate)
                continue
            winner = max(
                [overlap, candidate],
                key=self._priority,
            )
            loser = candidate if winner is overlap else overlap
            if winner is candidate:
                selected.remove(overlap)
                selected.append(candidate)
            conflicts.append(f"{loser.entity_id} overlapped with {winner.entity_id}")
        return (
            sorted(
                selected,
                key=lambda entity: (entity.start_offset or 0, entity.end_offset or 0),
            ),
            conflicts,
        )

    @classmethod
    def _priority(cls, entity: SensitiveEntity) -> tuple[int, int, float, int]:
        return (
            cls._containment_priority(entity),
            cls._entity_type_priority(entity),
            entity.confidence,
            len(entity.raw_text),
        )

    @staticmethod
    def _entity_type_priority(entity: SensitiveEntity) -> int:
        priority = {
            "ADDRESS": 3,
            "ORG": 2,
            "PERSON": 2,
            "EMAIL": 2,
            "NIP": 2,
            "REGON": 2,
            "KRS": 2,
            "VAT_ID": 2,
            "POSTAL_CODE": 1,
            "PHONE": 1,
        }
        return priority.get(entity.entity_type, 0)

    @staticmethod
    def _containment_priority(entity: SensitiveEntity) -> int:
        return 1 if entity.metadata.get("context_required") == "true" else 0

    @staticmethod
    def _overlaps(left: SensitiveEntity, right: SensitiveEntity) -> bool:
        if left.start_offset is None or left.end_offset is None:
            return False
        if right.start_offset is None or right.end_offset is None:
            return False
        return not (left.end_offset <= right.start_offset or right.end_offset <= left.start_offset)
