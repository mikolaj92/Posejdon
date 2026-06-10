from __future__ import annotations

import contextlib
from collections import Counter

from posejdon.core.enums import DocumentKind, PolicyProfileName, ReplacementKind
from posejdon.detectors.fusion import DetectorFusion
from posejdon.detectors.gliner_detector import GLiNERDetector
from posejdon.detectors.presidio_detector import PresidioDetector
from posejdon.detectors.regex_detector import RegexDetector
from posejdon.detectors.spacy_detector import SpacyDetector
from posejdon.domain.models import MetadataPolicy
from posejdon.domain.policies import (
    ConfidenceThresholds,
    OutputNamingRules,
    PolicyProfileDefinition,
)
from posejdon.planners.replacement_planner import ReplacementPlanner


class AnonymizationResult:
    def __init__(self, text: str, findings: dict[str, int]) -> None:
        self.text = text
        self.findings = findings


class TextAnonymizer:
    def __init__(self, gliner_enabled: bool = False) -> None:
        self.detectors = []

        # Always include RegexDetector
        self.detectors.append(RegexDetector())

        # Include PresidioDetector if available
        with contextlib.suppress(Exception):
            self.detectors.append(PresidioDetector())

        # Include SpacyDetector if available
        with contextlib.suppress(Exception):
            self.detectors.append(SpacyDetector())

        # Include GlinerDetector if requested and available
        if gliner_enabled:
            with contextlib.suppress(Exception):
                self.detectors.append(GLiNERDetector())

        self.fusion = DetectorFusion()

        # Default policy: replace everything with placeholders (irreversible mode by default)
        self.policy = PolicyProfileDefinition(
            name=PolicyProfileName.EXTERNAL_IRREVERSIBLE,
            entity_classes=[
                "PERSON",
                "PL_PESEL",
                "PL_NIP",
                "PL_REGON",
                "EMAIL",
                "PHONE_NUMBER",
                "BANK_ACCOUNT",
                "PAYMENT_CARD",
            ],
            replacement_style=ReplacementKind.CATEGORY_PLACEHOLDER,
            output_naming=OutputNamingRules(suffix="_anonymized"),
            metadata_policy=MetadataPolicy(),
            llm_review_allowed=False,
            confidence_thresholds=ConfidenceThresholds(
                accept_threshold=0.85,
                review_threshold=0.60,
            ),
        )
        self.planner = ReplacementPlanner(policy=self.policy)

    def anonymize(self, text: str) -> AnonymizationResult:
        # 1. Run all detectors and gather candidate entities
        candidates = []
        for detector in self.detectors:
            with contextlib.suppress(Exception):
                candidates.extend(detector.detect(text))

        # 2. Merge candidates to resolve overlaps
        resolved = self.fusion.merge(candidates)

        # 3. Create the replacement plan
        plan = self.planner.plan(entities=resolved, document_kind=DocumentKind.TEXT)

        # 4. Sort replacements by start offset descending to avoid index shifting
        sorted_replacements = sorted(
            plan.replacements,
            key=lambda r: r.write_targets[0].start_offset if r.write_targets else 0,
            reverse=True,
        )

        # 5. Apply replacements to the text
        anonymized_text = text
        for r in sorted_replacements:
            if not r.write_targets:
                continue
            target = r.write_targets[0]
            if target.start_offset is not None and target.end_offset is not None:
                anonymized_text = (
                    anonymized_text[: target.start_offset]
                    + r.replacement_text
                    + anonymized_text[target.end_offset :]
                )

        # 6. Count entity types for findings
        findings_counter = Counter()
        for r in plan.replacements:
            entity = next((e for e in resolved if e.entity_id == r.entity_id), None)
            if entity:
                findings_counter[entity.entity_type] += 1

        return AnonymizationResult(
            text=anonymized_text,
            findings=dict(sorted(findings_counter.items())),
        )
