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
    ) -> ReplacementPlan:
        resolved, conflicts = self.overlap_resolver.resolve(entities)
        warnings: list[str] = []
        replacements: list[Replacement] = []
        counters: dict[str, int] = defaultdict(int)
        strategy = self._strategy(processing_mode)

        for entity in resolved:
            if not self.confidence_policy.should_review(entity):
                warnings.append(f"Entity {entity.entity_id} below review threshold skipped.")
                continue
            if not self.confidence_policy.should_accept(entity):
                warnings.append(
                    f"Entity {entity.entity_id} below accept threshold included conservatively."
                )

            counters[entity.entity_type] += 1
            replacement_text = strategy.replace(entity, counters[entity.entity_type])
            replacements.append(
                Replacement(
                    entity_id=entity.entity_id,
                    replacement_text=replacement_text,
                    replacement_kind=strategy.kind,
                    source_text=entity.raw_text,
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

    def _strategy(self, processing_mode: ProcessingMode):
        if processing_mode == ProcessingMode.REVERSIBLE:
            return DeterministicPlaceholderStrategy()
        if (
            processing_mode == ProcessingMode.IRREVERSIBLE
            and self.policy.replacement_style == ReplacementKind.CATEGORY_PLACEHOLDER
        ):
            return FixedMaskStrategy()
        if self.policy.replacement_style == ReplacementKind.MASK:
            return MaskingStrategy()
        if self.policy.replacement_style == ReplacementKind.FORMAT_PRESERVING:
            return FormatPreservingStrategy()
        return DeterministicPlaceholderStrategy()
