from __future__ import annotations

from posejdon.core.enums import DocumentKind, PolicyProfileName, ProcessingMode, ReplacementKind
from posejdon.domain.entities import SensitiveEntity
from posejdon.domain.models import MetadataPolicy
from posejdon.domain.policies import OutputNamingRules, PolicyProfileDefinition
from posejdon.planners.replacement_planner import ReplacementPlanner


def _policy(replacement_style: ReplacementKind) -> PolicyProfileDefinition:
    return PolicyProfileDefinition(
        name=PolicyProfileName.EXTERNAL_IRREVERSIBLE,
        entity_classes=["PERSON", "PESEL"],
        replacement_style=replacement_style,
        output_naming=OutputNamingRules(suffix="_anonymized"),
        metadata_policy=MetadataPolicy(),
        llm_review_allowed=False,
        confidence_thresholds={"accept_threshold": 0.85, "review_threshold": 0.60},
    )


def _entities() -> list[SensitiveEntity]:
    return [
        SensitiveEntity(
            entity_id="person-1",
            entity_type="PERSON",
            raw_text="Jan Kowalski",
            normalized_text="Jan Kowalski",
            confidence=0.95,
            source_detector="regex",
            start_offset=0,
            end_offset=12,
        ),
        SensitiveEntity(
            entity_id="pesel-1",
            entity_type="PESEL",
            raw_text="44051401359",
            normalized_text="44051401359",
            confidence=0.99,
            source_detector="regex",
            start_offset=19,
            end_offset=30,
        ),
    ]


def test_irreversible_category_placeholders_become_fixed_masks() -> None:
    planner = ReplacementPlanner(policy=_policy(ReplacementKind.CATEGORY_PLACEHOLDER))

    plan = planner.plan(
        entities=_entities(),
        document_kind=DocumentKind.TEXT,
        processing_mode=ProcessingMode.IRREVERSIBLE,
    )

    assert [replacement.replacement_text for replacement in plan.replacements] == ["****", "****"]
    assert {replacement.replacement_kind for replacement in plan.replacements} == {
        ReplacementKind.MASK
    }


def test_reversible_category_placeholders_stay_reinjectable_tokens() -> None:
    planner = ReplacementPlanner(policy=_policy(ReplacementKind.CATEGORY_PLACEHOLDER))

    plan = planner.plan(
        entities=_entities(),
        document_kind=DocumentKind.TEXT,
        processing_mode=ProcessingMode.REVERSIBLE,
    )

    assert [replacement.replacement_text for replacement in plan.replacements] == [
        "[OSOBA_1]",
        "[PESEL_1]",
    ]
    assert {replacement.replacement_kind for replacement in plan.replacements} == {
        ReplacementKind.CATEGORY_PLACEHOLDER
    }


def test_explicit_mask_policy_remains_format_masked_in_irreversible_mode() -> None:
    planner = ReplacementPlanner(policy=_policy(ReplacementKind.MASK))

    plan = planner.plan(
        entities=_entities(),
        document_kind=DocumentKind.TEXT,
        processing_mode=ProcessingMode.IRREVERSIBLE,
    )

    assert [replacement.replacement_text for replacement in plan.replacements] == [
        "*** ********",
        "***********",
    ]


def test_reversible_mode_overrides_non_reinjectable_mask_policy() -> None:
    planner = ReplacementPlanner(policy=_policy(ReplacementKind.MASK))

    plan = planner.plan(
        entities=_entities(),
        document_kind=DocumentKind.TEXT,
        processing_mode=ProcessingMode.REVERSIBLE,
    )

    assert [replacement.replacement_text for replacement in plan.replacements] == [
        "[OSOBA_1]",
        "[PESEL_1]",
    ]
    assert {replacement.replacement_kind for replacement in plan.replacements} == {
        ReplacementKind.CATEGORY_PLACEHOLDER
    }
