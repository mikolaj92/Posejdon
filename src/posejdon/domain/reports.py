from __future__ import annotations

from pydantic import BaseModel, Field

from posejdon.core.constants import DEFAULT_SUBSYSTEM_VERSION
from posejdon.core.enums import (
    DocumentKind,
    ProcessingMode,
    ReinjectionConflictReason,
)
from posejdon.domain.entities import SensitiveEntity
from posejdon.domain.models import CoverageSummary, DetectorSummary, TimingMetadata
from posejdon.domain.replacements import Replacement


class ValidationResult(BaseModel):
    passed: bool
    leakage_checks: list[str] = Field(default_factory=list)
    structure_checks: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class LeakageScanResult(BaseModel):
    leaked_values_detected: bool = False
    findings: list[str] = Field(default_factory=list)
    findings_by_segment: list[SegmentLeakageFinding] = Field(default_factory=list)
    llm_findings_by_segment: list[SegmentLeakageFinding] = Field(default_factory=list)
    normalized_findings: list[str] = Field(default_factory=list)
    scope_summary: str = (
        "Surface-level exact and normalized scans. "
        "Does not cover undetected PII, OCR/image text, split tokens, or equivalent forms."
    )


class SegmentLeakageFinding(BaseModel):
    segment_id: str
    findings: list[str] = Field(default_factory=list)


class LLMReviewFinding(BaseModel):
    segment_id: str
    entity_id: str
    action: str
    applied: bool = False
    replacement_entity_type: str | None = None
    reason: str


class PlaceholderRegistryEntry(BaseModel):
    entity_id: str
    entity_type: str
    placeholder_text: str
    placeholder_family: str
    placeholder_ordinal: int
    segment_id: str | None = None
    container_id: str | None = None
    page_index: int | None = None
    section_id: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    context_before: str = ""
    context_after: str = ""
    hints: dict[str, str] = Field(default_factory=dict)


class InjectorSegmentTemplate(BaseModel):
    segment_id: str
    container_id: str
    page_index: int | None = None
    section_id: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    text_with_placeholders: str
    placeholder_refs: list[str] = Field(default_factory=list)
    placeholder_count: int = 0
    placeholder_order_fingerprint: str
    normalized_text_fingerprint: str
    structural_fingerprint: str


class InjectorExport(BaseModel):
    subsystem_version: str = DEFAULT_SUBSYSTEM_VERSION
    injector_export_version: str = "v1"
    reinjection_contract_version: str = "v1"
    processing_mode: ProcessingMode
    input_document_type: DocumentKind
    output_document_type: DocumentKind
    injector_target: str = "local_llm_reinjection"
    placeholder_registry: list[PlaceholderRegistryEntry] = Field(default_factory=list)
    segment_templates: list[InjectorSegmentTemplate] = Field(default_factory=list)


class ReinjectionConflict(BaseModel):
    segment_id: str | None = None
    placeholder_text: str | None = None
    reason: ReinjectionConflictReason
    severity: str = "high"
    details: str = ""


class ReinjectionDecision(BaseModel):
    segment_id: str
    placeholder_text: str
    applied: bool
    decision_reason: str
    confidence_contract: str
    start_offset: int | None = None
    end_offset: int | None = None
    original_value_hash: str | None = None


class ReinjectionReport(BaseModel):
    subsystem_version: str = DEFAULT_SUBSYSTEM_VERSION
    restore_kind: str = "reinjection_restore"
    mapping_vault_id: str
    edited_input_hash: str
    source_output_artifact_path: str
    source_output_hash: str
    injector_export_path: str
    injector_export_hash: str
    status: str
    strict_mode: bool = True
    matched_segments: int = 0
    rejected_segments: int = 0
    rejected_placeholders: int = 0
    integrity_checks: list[str] = Field(default_factory=list)
    conflicts: list[ReinjectionConflict] = Field(default_factory=list)
    applied_reinjections: list[ReinjectionDecision] = Field(default_factory=list)


class ReinjectionPlan(BaseModel):
    restore_kind: str = "reinjection_restore"
    mapping_vault_id: str
    edited_input_path: str
    source_output_artifact_path: str
    status: str
    strict_mode: bool = True
    matched_segments: int = 0
    rejected_segments: int = 0
    rejected_placeholders: int = 0
    conflicts: list[ReinjectionConflict] = Field(default_factory=list)
    applied_reinjections: list[ReinjectionDecision] = Field(default_factory=list)


class ReidentificationRiskScore(BaseModel):
    overall_score: float = 0.0
    risk_level: str = "low"
    entity_type_scores: dict[str, float] = Field(default_factory=dict)
    metrics: dict[str, object] = Field(default_factory=dict)


class ProcessingReport(BaseModel):
    subsystem_version: str = DEFAULT_SUBSYSTEM_VERSION
    processing_mode: ProcessingMode
    input_document_type: DocumentKind
    output_document_type: DocumentKind
    detector_summary: DetectorSummary
    coverage_summary: CoverageSummary
    entities_found: list[SensitiveEntity] = Field(default_factory=list)
    llm_review_findings: list[LLMReviewFinding] = Field(default_factory=list)
    replacements_applied: list[Replacement] = Field(default_factory=list)
    placeholder_registry: list[PlaceholderRegistryEntry] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unsupported_features: list[str] = Field(default_factory=list)
    validation_results: ValidationResult
    leakage_scan_results: LeakageScanResult
    timing_metadata: TimingMetadata
    reidentification_risk: dict[str, object] = Field(default_factory=dict)
    entity_confidence_metrics: dict[str, object] = Field(default_factory=dict)


class RestoreReport(BaseModel):
    subsystem_version: str = DEFAULT_SUBSYSTEM_VERSION
    restore_kind: str = "archive_restore"
    processing_mode: ProcessingMode
    mapping_vault_id: str
    source_audit_id: str
    source_output_artifact_path: str
    restored_artifact_path: str
    integrity_checks: list[str] = Field(default_factory=list)
