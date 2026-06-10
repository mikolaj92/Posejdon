from __future__ import annotations

from pydantic import BaseModel, Field

from posejdon.core.enums import AuditStatus, ProcessingMode
from posejdon.domain.entities import SensitiveEntity
from posejdon.domain.models import DetectorSummary


class EntityAuditEntry(BaseModel):
    """Per-entity or aggregated entity anonymization decision record for audit trails."""

    entity_type: str
    count: int
    confidence_mean: float
    confidence_median: float
    confidence_min: float
    confidence_max: float
    anonymization_rationale: str = ""
    source_detectors: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)

    @staticmethod
    def build_entity_audit(entities: list[SensitiveEntity]) -> list[EntityAuditEntry]:
        from statistics import median

        by_type: dict[str, list[SensitiveEntity]] = {}
        for entity in entities:
            by_type.setdefault(entity.entity_type, []).append(entity)

        entries = []
        for entity_type, type_entities in by_type.items():
            confidences = [e.confidence for e in type_entities if e.confidence is not None]
            entries.append(
                EntityAuditEntry(
                    entity_type=entity_type,
                    count=len(type_entities),
                    confidence_mean=(
                        round(sum(confidences) / len(confidences), 4)
                        if confidences
                        else 0.0
                    ),
                    confidence_median=round(median(confidences), 4) if confidences else 0.0,
                    confidence_min=round(min(confidences), 4) if confidences else 0.0,
                    confidence_max=round(max(confidences), 4) if confidences else 0.0,
                    anonymization_rationale="policy_driven",
                )
            )
        return entries


class ModeAuthorization(BaseModel):
    """Records how processing mode was selected and authorized."""

    requested_mode: ProcessingMode
    effective_mode: ProcessingMode
    authorized_by: str
    authorization_source: str = "runtime_default"
    authorization_reason: str = ""
    requires_justification: bool = False
    justification_provided: str | None = None


class AnonymizationAuditTrail(BaseModel):
    """Extended audit record with per-entity decisions and tamper evidence."""

    audit_id: str
    operation: str = "anonymize"
    mode: ProcessingMode
    mode_authorization: ModeAuthorization
    input_hash: str
    output_hash: str
    report_hash: str
    created_at: str
    operator: str
    policy_profile: str
    policy_version: str = "1.0"
    status: AuditStatus
    entity_audit: list[EntityAuditEntry] = Field(default_factory=list)
    detector_summary: DetectorSummary = Field(default_factory=DetectorSummary)
    source_audit_id: str | None = None
    mapping_vault_id: str | None = None
    trace_id: str | None = None
    request_id: str | None = None
    prompt_rendering: PromptRenderingMetadata | None = None
    tamper_evidence_hash: str | None = None
    previous_audit_hash: str | None = None
    audit_chain_hash: str | None = None


class ArtifactSet(BaseModel):
    input_artifact_id: str
    original_artifact_path: str
    output_artifact_path: str
    report_path: str
    injector_export_path: str
    audit_id: str
    mapping_vault_id: str | None = None
    mapping_vault_path: str | None = None


class RestoreArtifactSet(BaseModel):
    restore_kind: str = "archive_restore"
    mapping_vault_id: str
    restored_artifact_path: str
    restore_report_path: str
    restore_audit_id: str
    source_audit_id: str
    source_output_artifact_path: str


class ReinjectionRequest(BaseModel):
    mapping_vault_id: str
    edited_input_path: str
    operator: str = "system"
    mode: str = "strict"


class ReinjectionArtifactSet(BaseModel):
    restore_kind: str = "reinjection_restore"
    mapping_vault_id: str
    edited_input_path: str
    reinjected_artifact_path: str
    reinjection_report_path: str
    reinjection_audit_id: str
    source_audit_id: str
    source_output_artifact_path: str


class ReinjectionVaultEntry(BaseModel):
    entity_id: str
    entity_type: str
    placeholder_text: str
    original_value: str
    original_value_hash: str
    segment_id: str | None = None
    container_id: str | None = None
    page_index: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None


class MappingVaultRecord(BaseModel):
    vault_id: str
    mode: ProcessingMode
    input_artifact_id: str
    original_artifact_path: str
    original_artifact_hash: str
    output_artifact_path: str
    output_artifact_hash: str
    report_path: str
    report_hash: str
    injector_export_path: str
    injector_export_hash: str
    audit_id: str
    created_at: str
    operator: str
    policy_profile: str
    reinjection_state_version: str = "v1"
    reinjection_entries: list[ReinjectionVaultEntry] = []
    vault_hmac: str | None = None
    expires_at: str | None = None


class PromptRenderingMetadata(BaseModel):
    prompt_id: str
    prompt_version: str
    template_hash: str | None = None
    rendered_at: str | None = None


class AuditRecord(BaseModel):
    audit_id: str
    operation: str = "anonymize"
    mode: ProcessingMode
    input_hash: str
    output_hash: str
    report_hash: str
    created_at: str
    operator: str
    policy_profile: str
    status: AuditStatus
    source_audit_id: str | None = None
    mapping_vault_id: str | None = None
    trace_id: str | None = None
    request_id: str | None = None
    prompt_rendering: PromptRenderingMetadata | None = None
    entity_audit: list[EntityAuditEntry] = []
    mode_authorization: ModeAuthorization | None = None
    previous_audit_hash: str | None = None
    audit_chain_hash: str | None = None
