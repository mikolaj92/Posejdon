from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from posejdon.core.enums import DocumentKind
from posejdon.detectors.gliner_detector import GLiNERDetector
from posejdon.detectors.regex_support import (
    is_checksum_valid_identifier,
    validate_person_full_name,
)
from posejdon.domain.entities import SensitiveEntity
from posejdon.domain.reports import LeakageScanResult, SegmentLeakageFinding
from posejdon.domain.segments import TextSegment


class LeakageValidator:
    _CONNECTOR_CHARS = r"\w@._-"
    _RESIDUAL_IDENTIFIER_TYPES = frozenset({"EMAIL", "NIP", "KRS"})

    def extract_text_file_segments(self, path: str) -> list[TextSegment]:
        """Read a UTF-8 text file. Document formats belong to the host (#54)."""
        text = Path(path).read_text(encoding="utf-8")
        if not text:
            return []
        return [
            TextSegment(
                segment_id="text:0",
                text=text,
                container_id="text:0",
                section_id="text:0",
                start_offset=0,
                end_offset=len(text),
            )
        ]

    def extract_segments(self, path: str, document_kind: DocumentKind) -> list[TextSegment]:
        if document_kind == DocumentKind.TEXT:
            return self.extract_text_file_segments(path)
        raise ValueError(
            "posejdon leakage: extract_segments no longer parses documents; "
            "pass host TextSegment values into validate(segments=...)"
        )

    def validate(
        self,
        *,
        entities: list[SensitiveEntity],
        segments: Sequence[TextSegment] | None = None,
        output_path: str | None = None,
        document_kind: DocumentKind | None = None,
    ) -> LeakageScanResult:
        resolved = list(segments or [])
        if not resolved:
            if document_kind == DocumentKind.TEXT and output_path:
                resolved = self.extract_text_file_segments(output_path)
            else:
                raise ValueError(
                    "posejdon leakage: document segments must be supplied by the host; "
                    "the library does not parse DOCX, JSON, XML, or PDF"
                )
        segment_lookup = {segment.segment_id: segment.text for segment in resolved}
        global_findings: set[str] = set()
        normalized_findings: set[str] = set()
        segmented_findings: list[SegmentLeakageFinding] = []
        scannable = [entity for entity in entities if self._is_scannable_entity(entity)]

        for segment in resolved:
            matched = sorted(
                {
                    entity.raw_text
                    for entity in scannable
                    if self._contains_surface(segment.text, entity.raw_text)
                    and (entity.segment_id is None or entity.segment_id == segment.segment_id)
                }
            )
            normalized_matched = sorted(
                {
                    entity.raw_text
                    for entity in scannable
                    if self._normalized_contains(segment.text, entity.raw_text)
                    and (entity.segment_id is None or entity.segment_id == segment.segment_id)
                }
            )
            if matched:
                segmented_findings.append(
                    SegmentLeakageFinding(segment_id=segment.segment_id, findings=matched)
                )
                global_findings.update(matched)
            if normalized_matched:
                normalized_findings.update(normalized_matched)

        full_text = "\n".join(segment_lookup.values())
        for entity in scannable:
            if entity.segment_id is not None:
                continue
            if self._contains_surface(full_text, entity.raw_text):
                global_findings.add(entity.raw_text)
            if self._normalized_contains(full_text, entity.raw_text):
                normalized_findings.add(entity.raw_text)

        return LeakageScanResult(
            leaked_values_detected=bool(global_findings or normalized_findings),
            findings=sorted(global_findings),
            findings_by_segment=segmented_findings,
            normalized_findings=sorted(normalized_findings),
        )

    @classmethod
    def _is_scannable_entity(cls, entity: SensitiveEntity) -> bool:
        if entity.entity_type in cls._RESIDUAL_IDENTIFIER_TYPES:
            return is_checksum_valid_identifier(entity.entity_type, entity.raw_text)
        if GLiNERDetector._is_generic_role_surface(entity.raw_text):
            return False
        if entity.metadata.get("semantic_conflict") == "true":
            return validate_person_full_name(entity.raw_text)
        return True

    @classmethod
    def _contains_surface(cls, text: str, surface: str) -> bool:
        pattern = cls._surface_pattern(surface)
        if pattern is None:
            return False
        return pattern.search(text) is not None

    @classmethod
    def _normalized_contains(cls, text: str, surface: str) -> bool:
        pattern = cls._normalized_surface_pattern(surface)
        if pattern is None:
            return False
        return pattern.search(cls._normalize_text(text)) is not None

    @classmethod
    def _surface_pattern(cls, surface: str) -> re.Pattern[str] | None:
        cleaned = " ".join(surface.split())
        if not cleaned:
            return None
        parts = cleaned.split(" ")
        escaped = [re.escape(part) for part in parts]
        return re.compile(
            rf"(?<![{cls._CONNECTOR_CHARS}]){'\\s+'.join(escaped)}(?![{cls._CONNECTOR_CHARS}])"
        )

    @classmethod
    def _normalized_surface_pattern(cls, surface: str) -> re.Pattern[str] | None:
        cleaned = cls._normalize_text(surface)
        parts = cleaned.split()
        if not parts:
            return None
        escaped = [re.escape(part) for part in parts]
        return re.compile(rf"(?<!\w){'\\s+'.join(escaped)}(?!\w)")

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"[^\w\s]", "", text.casefold())
