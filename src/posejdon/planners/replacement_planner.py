from __future__ import annotations

from collections import defaultdict

from posejdon.core.enums import ProcessingMode, ReplacementKind
from posejdon.domain.entities import SensitiveEntity
from posejdon.domain.policies import PolicyProfileDefinition
from posejdon.domain.replacements import Replacement, ReplacementPlan, WriteTarget
from posejdon.planners.confidence_policy import ConfidencePolicy
from posejdon.planners.overlap_resolver import OverlapResolver
from posejdon.planners.placeholder_strategy import (
    DeterministicPlaceholderStrategy,
    FixedMaskStrategy,
    FormatPreservingStrategy,
    MaskingStrategy,
)


def _person_counter_key(entity: SensitiveEntity) -> tuple[str, str] | None:
    if entity.entity_type != "PERSON":
        return None
    provenance = entity.mention_provenance()
    if provenance is None:
        return entity.entity_type, entity.entity_id
    return entity.entity_type, provenance.mention_cluster_id


def _person_cluster_ordinals(entities: list[SensitiveEntity]) -> dict[tuple[str, str], int]:
    ordinals: dict[tuple[str, str], int] = {}
    person_count = 0
    for entity in entities:
        if entity.entity_type != "PERSON" or entity.mention_provenance() is not None:
            continue
        key = _person_counter_key(entity)
        if key is None or key in ordinals:
            continue
        person_count += 1
        ordinals[key] = person_count
    for entity in entities:
        provenance = entity.mention_provenance()
        if entity.entity_type == "PERSON" and provenance is not None:
            ordinals[(entity.entity_type, provenance.mention_cluster_id)] = ordinals.get(
                (entity.entity_type, provenance.canonical_entity_id),
                person_count + 1,
            )
    return ordinals


class ReplacementPlanner:
    def __init__(self, policy: PolicyProfileDefinition, secret: str = "posejdon") -> None:
        self.policy = policy
        self.confidence_policy = ConfidencePolicy(policy.confidence_thresholds)
        self.overlap_resolver = OverlapResolver()
        self.secret = secret

    def plan(
        self,
        *,
        entities: list[SensitiveEntity],
        document_kind,
        processing_mode: ProcessingMode = ProcessingMode.IRREVERSIBLE,
        replacement_style: ReplacementKind | None = None,
    ) -> ReplacementPlan:
        resolved, conflicts = self.overlap_resolver.resolve(entities)
        warnings: list[str] = []
        replacements: list[Replacement] = []
        counters: dict[str, int] = defaultdict(int)
        cluster_ordinals = _person_cluster_ordinals(resolved)
        strategy = self._strategy(processing_mode, replacement_style)

        for entity in resolved:
            if not self.confidence_policy.should_review(entity):
                warnings.append(f"Entity {entity.entity_id} below review threshold skipped.")
                continue
            if not self.confidence_policy.should_accept(entity):
                warnings.append(
                    f"Entity {entity.entity_id} below accept threshold included conservatively."
                )

            counter_key = _person_counter_key(entity)
            ordinal = cluster_ordinals.get(counter_key) if counter_key is not None else None
            if ordinal is None:
                counters[entity.entity_type] += 1
                ordinal = counters[entity.entity_type]
            replacement_text = strategy.replace(entity, ordinal)
            replacements.append(
                Replacement(
                    entity_id=entity.entity_id,
                    replacement_text=replacement_text,
                    replacement_kind=strategy.kind,
                    source_text=(
                        entity.raw_text if processing_mode == ProcessingMode.REVERSIBLE else None
                    ),
                    justification=f"Policy {self.policy.name.value} replacement.",
                    confidence=entity.confidence,
                    write_targets=[
                        WriteTarget(
                            segment_id=entity.segment_id,
                            container_id=entity.section_id or "document",
                            start_offset=entity.start_offset,
                            end_offset=entity.end_offset,
                            page_index=entity.page_index,
                        )
                    ],
                )
            )

        return ReplacementPlan(
            document_kind=document_kind,
            replacements=replacements,
            unresolved_conflicts=conflicts,
            warnings=warnings,
        )

    def _strategy(
        self,
        processing_mode: ProcessingMode,
        replacement_style: ReplacementKind | None = None,
    ):
        if processing_mode == ProcessingMode.REVERSIBLE:
            return DeterministicPlaceholderStrategy()
        if replacement_style is not None:
            return self._explicit_strategy(replacement_style)
        if self.policy.replacement_style == ReplacementKind.CATEGORY_PLACEHOLDER:
            # Format is governed by replacement_style, recoverability by
            # processing_mode (the latter nulls source_text for irreversible runs
            # at the call site). A CATEGORY_PLACEHOLDER policy therefore always
            # emits labeled placeholders; irreversible runs simply keep no
            # restore mapping. Collapsing labels to a fixed mask here would also
            # strip the anchors downstream reinjection relies on.
            return DeterministicPlaceholderStrategy()
        if self.policy.replacement_style == ReplacementKind.MASK:
            return MaskingStrategy()
        if self.policy.replacement_style == ReplacementKind.FORMAT_PRESERVING:
            return FormatPreservingStrategy()
        return DeterministicPlaceholderStrategy()

    @staticmethod
    def _explicit_strategy(replacement_style: ReplacementKind):
        if replacement_style == ReplacementKind.MASK:
            return FixedMaskStrategy()
        if replacement_style == ReplacementKind.FORMAT_PRESERVING:
            return FormatPreservingStrategy()
        return DeterministicPlaceholderStrategy()
