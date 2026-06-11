from __future__ import annotations

import contextlib
from collections import Counter

from posejdon.core.enums import DocumentKind, PolicyProfileName, ProcessingMode
from posejdon.detectors.fusion import DetectorFusion
from posejdon.detectors.gliner_detector import GLiNERDetector
from posejdon.detectors.mention_memory import expand_person_mentions
from posejdon.detectors.presidio_detector import PresidioDetector
from posejdon.detectors.regex_detector import RegexDetector
from posejdon.domain.policies import DEFAULT_POLICY_PROFILES
from posejdon.planners.replacement_planner import ReplacementPlanner


class AnonymizationResult:
    def __init__(self, text: str, findings: dict[str, int]) -> None:
        self.text = text
        self.findings = findings


class SegmentAnonymizationResult:
    def __init__(self, texts: list[str], findings: dict[str, int]) -> None:
        self.texts = texts
        self.findings = findings


class TextAnonymizer:
    def __init__(
        self,
        gliner_enabled: bool = False,
        gliner_model: str = "urchade/gliner_small-v2.1",
        gliner_threshold: float = 0.45,
        processing_mode: ProcessingMode = ProcessingMode.IRREVERSIBLE,
    ) -> None:
        self.processing_mode = processing_mode
        self.detectors = []

        # Always include RegexDetector
        self.detectors.append(RegexDetector())

        # Include PresidioDetector if available
        with contextlib.suppress(Exception):
            self.detectors.append(PresidioDetector())

        # Include GlinerDetector if requested and available
        if gliner_enabled:
            with contextlib.suppress(Exception):
                self.detectors.append(
                    GLiNERDetector(model_name=gliner_model, threshold=gliner_threshold)
                )

        self.fusion = DetectorFusion()

        # Compatibility anonymizer stays local-only: regex/optional local detectors, no LLM review.
        self.policy = DEFAULT_POLICY_PROFILES[PolicyProfileName.EXTERNAL_IRREVERSIBLE].model_copy(
            update={"llm_review_allowed": False}
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
        resolved = expand_person_mentions(text, resolved)

        # 3. Create the replacement plan
        plan = self.planner.plan(
            entities=resolved,
            document_kind=DocumentKind.TEXT,
            processing_mode=self.processing_mode,
        )

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

    def anonymize_segments(self, texts: list[str]) -> SegmentAnonymizationResult:
        if not texts:
            return SegmentAnonymizationResult(texts=[], findings={})
        if len(texts) == 1:
            result = self.anonymize(texts[0])
            return SegmentAnonymizationResult(texts=[result.text], findings=result.findings)

        delimiter_root = _unique_segment_delimiter_root(texts)
        delimiters = [f"\n{delimiter_root}_{index}\n" for index in range(len(texts) - 1)]
        joined = texts[0]
        for delimiter, text in zip(delimiters, texts[1:], strict=True):
            joined += delimiter + text

        result = self.anonymize(joined)
        remaining = result.text
        anonymized_texts: list[str] = []
        for delimiter in delimiters:
            delimiter_index = remaining.find(delimiter)
            if delimiter_index < 0:
                raise RuntimeError("Anonymized segment boundary was not preserved.")
            anonymized_texts.append(remaining[:delimiter_index])
            remaining = remaining[delimiter_index + len(delimiter) :]
        anonymized_texts.append(remaining)
        return SegmentAnonymizationResult(texts=anonymized_texts, findings=result.findings)


def _unique_segment_delimiter_root(texts: list[str]) -> str:
    root = "<<POSEJDON_SEGMENT_BOUNDARY>>"
    while any(root in text for text in texts):
        root = f"{root}_X"
    return root
