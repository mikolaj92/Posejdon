from __future__ import annotations

import re
from difflib import SequenceMatcher

from posejdon_docs.parsers.base import ParsedTextSegment

from posejdon.core.enums import ReinjectionConflictReason
from posejdon.domain.artifacts import ReinjectionVaultEntry
from posejdon.domain.reports import (
    InjectorExport,
    ReinjectionConflict,
    ReinjectionDecision,
    ReinjectionPlan,
)

PLACEHOLDER_RE = re.compile(r"\[[A-Z_]+_\d+\]")


class ReinjectionPlanner:
    MIN_FUZZY_RATIO = 0.80
    AMBIGUOUS_DELTA = 0.08

    def plan_exact(
        self,
        *,
        mapping_vault_id: str,
        edited_input_path: str,
        source_output_artifact_path: str,
        injector_export: InjectorExport,
        edited_segments: list[ParsedTextSegment],
        vault_entries: list[ReinjectionVaultEntry],
        enable_fuzzy: bool = True,
    ) -> ReinjectionPlan:
        edited_by_segment = {segment.segment_id: segment for segment in edited_segments}
        edited_placeholder_locations: dict[str, list[str]] = {}
        for segment in edited_segments:
            for placeholder in PLACEHOLDER_RE.findall(segment.text):
                edited_placeholder_locations.setdefault(placeholder, []).append(segment.segment_id)
        placeholder_to_template_segment = {
            placeholder: template.segment_id
            for template in injector_export.segment_templates
            for placeholder in template.placeholder_refs
        }
        vault_entries_by_segment: dict[str, dict[str, ReinjectionVaultEntry]] = {}
        for entry in vault_entries:
            if entry.segment_id is None:
                continue
            vault_entries_by_segment.setdefault(entry.segment_id, {})[entry.placeholder_text] = (
                entry
            )

        decisions: list[ReinjectionDecision] = []
        conflicts: list[ReinjectionConflict] = []

        for template in injector_export.segment_templates:
            segment = edited_by_segment.get(template.segment_id)
            if segment is None and enable_fuzzy:
                fuzzy_match, fuzzy_conflicts = self._fuzzy_match_missing_segment(
                    template=template,
                    edited_segments=edited_segments,
                )
                if fuzzy_match is not None:
                    segment = fuzzy_match
                else:
                    conflicts.extend(fuzzy_conflicts)
                    conflicts.extend(
                        self._missing_segment_conflicts(
                            template=template,
                            edited_placeholder_locations=edited_placeholder_locations,
                        )
                    )
                    continue
            elif segment is None:
                conflicts.extend(
                    self._missing_segment_conflicts(
                        template=template,
                        edited_placeholder_locations=edited_placeholder_locations,
                    )
                )
                continue

            segment_conflicts = self._segment_exact_conflicts(
                segment=segment,
                template=template,
                placeholder_to_template_segment=placeholder_to_template_segment,
                edited_placeholder_locations=edited_placeholder_locations,
                allow_fuzzy_identity=(segment.segment_id != template.segment_id),
            )
            if segment_conflicts:
                conflicts.extend(segment_conflicts)
                continue

            entries_for_segment = vault_entries_by_segment.get(template.segment_id, {})
            for placeholder in template.placeholder_refs:
                vault_entry = entries_for_segment.get(placeholder)
                if vault_entry is None:
                    conflicts.append(
                        ReinjectionConflict(
                            segment_id=template.segment_id,
                            placeholder_text=placeholder,
                            reason=ReinjectionConflictReason.MISSING_VAULT_ENTRY,
                            details=(
                                "Vault does not contain a reinjection entry "
                                "for the exported placeholder."
                            ),
                        )
                    )
                    continue
                decisions.append(
                    ReinjectionDecision(
                        segment_id=template.segment_id,
                        placeholder_text=placeholder,
                        applied=True,
                        decision_reason=(
                            "exact_segment_match"
                            if segment.segment_id == template.segment_id
                            else "fuzzy_anchored_segment_match"
                        ),
                        confidence_contract=(
                            "exact_anchor_match"
                            if segment.segment_id == template.segment_id
                            else "anchored_fuzzy_match"
                        ),
                        start_offset=vault_entry.start_offset,
                        end_offset=vault_entry.end_offset,
                        original_value_hash=vault_entry.original_value_hash,
                    )
                )

        status = "ready" if not conflicts else "fail_closed"
        matched_segments = len({item.segment_id for item in decisions})
        rejected_segments = len({item.segment_id for item in conflicts if item.segment_id})
        rejected_placeholders = len([item for item in conflicts if item.placeholder_text])
        return ReinjectionPlan(
            mapping_vault_id=mapping_vault_id,
            edited_input_path=edited_input_path,
            source_output_artifact_path=source_output_artifact_path,
            status=status,
            strict_mode=True,
            matched_segments=matched_segments,
            rejected_segments=rejected_segments,
            rejected_placeholders=rejected_placeholders,
            conflicts=conflicts,
            applied_reinjections=decisions,
        )

    def _segment_exact_conflicts(
        self,
        *,
        segment: ParsedTextSegment,
        template,
        placeholder_to_template_segment: dict[str, str],
        edited_placeholder_locations: dict[str, list[str]],
        allow_fuzzy_identity: bool,
    ) -> list[ReinjectionConflict]:
        conflicts: list[ReinjectionConflict] = []
        if allow_fuzzy_identity:
            same_container_family = self._locality_key(segment.container_id) == self._locality_key(
                template.container_id
            )
            same_section_family = self._locality_key(
                segment.section_id or ""
            ) == self._locality_key(template.section_id or "")
        else:
            same_container_family = segment.container_id == template.container_id
            same_section_family = (segment.section_id or None) == (template.section_id or None)
        if not same_container_family:
            conflicts.append(
                ReinjectionConflict(
                    segment_id=template.segment_id,
                    reason=ReinjectionConflictReason.CONTAINER_MISMATCH,
                    details=(
                        "Edited segment container id differs from the exported template container."
                    ),
                )
            )
        if (segment.page_index or None) != (template.page_index or None):
            conflicts.append(
                ReinjectionConflict(
                    segment_id=template.segment_id,
                    reason=ReinjectionConflictReason.PAGE_INDEX_MISMATCH,
                    details="Edited segment page index differs from the exported template.",
                )
            )
        if not same_section_family:
            conflicts.append(
                ReinjectionConflict(
                    segment_id=template.segment_id,
                    reason=ReinjectionConflictReason.SECTION_MISMATCH,
                    details="Edited segment section id differs from the exported template.",
                )
            )
        current_refs = PLACEHOLDER_RE.findall(segment.text)
        for placeholder in template.placeholder_refs:
            locations = edited_placeholder_locations.get(placeholder, [])
            if any(location != segment.segment_id for location in locations):
                conflicts.append(
                    ReinjectionConflict(
                        segment_id=template.segment_id,
                        placeholder_text=placeholder,
                        reason=ReinjectionConflictReason.SEGMENT_SPLIT,
                        details=(
                            "Edited document now contains the exported placeholder "
                            "across multiple segment locations."
                        ),
                    )
                )
        if current_refs != template.placeholder_refs:
            current_set = set(current_refs)
            expected_set = set(template.placeholder_refs)
            if current_set == expected_set and current_refs != template.placeholder_refs:
                conflicts.append(
                    ReinjectionConflict(
                        segment_id=template.segment_id,
                        reason=ReinjectionConflictReason.PLACEHOLDER_REORDERED,
                        details=(
                            "Edited segment preserved the placeholder set "
                            "but changed placeholder order."
                        ),
                    )
                )
            duplicated = [
                placeholder
                for placeholder in current_refs
                if current_refs.count(placeholder) > template.placeholder_refs.count(placeholder)
            ]
            for placeholder in sorted(set(duplicated)):
                conflicts.append(
                    ReinjectionConflict(
                        segment_id=template.segment_id,
                        placeholder_text=placeholder,
                        reason=ReinjectionConflictReason.PLACEHOLDER_DUPLICATED,
                        details=(
                            "Edited segment duplicated a placeholder beyond "
                            "the exported template count."
                        ),
                    )
                )
            missing = [
                placeholder
                for placeholder in template.placeholder_refs
                if placeholder not in current_set
            ]
            for placeholder in missing:
                locations = edited_placeholder_locations.get(placeholder, [])
                if not locations:
                    conflicts.append(
                        ReinjectionConflict(
                            segment_id=template.segment_id,
                            placeholder_text=placeholder,
                            reason=ReinjectionConflictReason.PLACEHOLDER_DELETED,
                            details="Edited segment no longer contains an exported placeholder.",
                        )
                    )
                elif any(location != template.segment_id for location in locations):
                    conflicts.append(
                        ReinjectionConflict(
                            segment_id=template.segment_id,
                            placeholder_text=placeholder,
                            reason=ReinjectionConflictReason.SEGMENT_SPLIT,
                            details=(
                                "Edited document moved exported placeholders "
                                "into a different segment layout."
                            ),
                        )
                    )
            extra = [placeholder for placeholder in current_refs if placeholder not in expected_set]
            for placeholder in sorted(set(extra)):
                owner = placeholder_to_template_segment.get(placeholder)
                conflicts.append(
                    ReinjectionConflict(
                        segment_id=template.segment_id,
                        placeholder_text=placeholder,
                        reason=(
                            ReinjectionConflictReason.SEGMENT_MERGE
                            if owner is not None and owner != template.segment_id
                            else ReinjectionConflictReason.PLACEHOLDER_DRIFT
                        ),
                        details=(
                            "Edited segment contains placeholders that belong "
                            "to a different exported segment or an unknown "
                            "placeholder set."
                        ),
                    )
                )
        if not conflicts and current_refs != template.placeholder_refs:
            conflicts.append(
                ReinjectionConflict(
                    segment_id=template.segment_id,
                    reason=ReinjectionConflictReason.PLACEHOLDER_DRIFT,
                    details=(
                        "Edited segment placeholder order or placeholder set "
                        "differs from the exported template."
                    ),
                )
            )
        return conflicts

    def _missing_segment_conflicts(
        self,
        *,
        template,
        edited_placeholder_locations: dict[str, list[str]],
    ) -> list[ReinjectionConflict]:
        locations = {
            location
            for placeholder in template.placeholder_refs
            for location in edited_placeholder_locations.get(placeholder, [])
        }
        if not locations:
            return [
                ReinjectionConflict(
                    segment_id=template.segment_id,
                    reason=ReinjectionConflictReason.MISSING_SEGMENT,
                    details="Edited document does not contain the exported segment id.",
                )
            ]
        if len(locations) > 1:
            return [
                ReinjectionConflict(
                    segment_id=template.segment_id,
                    reason=ReinjectionConflictReason.SEGMENT_SPLIT,
                    details=(
                        "Exported segment placeholders are now spread across "
                        "multiple edited segments."
                    ),
                )
            ]
        return [
            ReinjectionConflict(
                segment_id=template.segment_id,
                reason=ReinjectionConflictReason.SEGMENT_MERGE,
                details="Exported segment placeholders moved into a different edited segment.",
            )
        ]

    def _fuzzy_match_missing_segment(
        self,
        *,
        template,
        edited_segments: list[ParsedTextSegment],
    ) -> tuple[ParsedTextSegment | None, list[ReinjectionConflict]]:
        candidates: list[tuple[float, ParsedTextSegment]] = []
        template_context = self._locality_key(template.container_id)
        for segment in edited_segments:
            current_refs = PLACEHOLDER_RE.findall(segment.text)
            if current_refs != template.placeholder_refs:
                continue
            if self._locality_key(segment.container_id) != template_context:
                continue
            ratio = SequenceMatcher(
                None,
                self._normalize_match_text(template.text_with_placeholders),
                self._normalize_match_text(segment.text),
            ).ratio()
            candidates.append((ratio, segment))
        if not candidates:
            return None, []
        candidates.sort(key=lambda item: item[0], reverse=True)
        best_ratio, best_segment = candidates[0]
        if best_ratio < self.MIN_FUZZY_RATIO:
            return None, [
                ReinjectionConflict(
                    segment_id=template.segment_id,
                    reason=ReinjectionConflictReason.LOW_CONFIDENCE_MATCH,
                    details=(
                        "No edited segment satisfied the anchored fuzzy threshold for reinjection."
                    ),
                )
            ]
        if (
            len(candidates) > 1
            and candidates[1][0] >= self.MIN_FUZZY_RATIO
            and (best_ratio - candidates[1][0]) <= self.AMBIGUOUS_DELTA
        ):
            return None, [
                ReinjectionConflict(
                    segment_id=template.segment_id,
                    reason=ReinjectionConflictReason.AMBIGUOUS_SEGMENT_MATCH,
                    details=(
                        "Multiple edited segments satisfy the anchored fuzzy "
                        "threshold without a clear deterministic winner."
                    ),
                )
            ]
        return best_segment, []

    def _locality_key(self, container_id: str) -> str:
        return re.sub(r":p:\d+$", "", container_id)

    def _normalize_match_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip().lower()
