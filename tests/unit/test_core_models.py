from posejdon.core.enums import AuditStatus, DocumentKind, ProcessingMode
from posejdon.core.settings import PosejdonSettings
from posejdon.domain.artifacts import AuditRecord, PromptRenderingMetadata
from posejdon.domain.entities import MentionProvenance, SensitiveEntity
from posejdon.domain.models import CoverageSummary, DetectorSummary, TimingMetadata
from posejdon.domain.policies import (
    DEFAULT_POLICY_PROFILES,
    ENTITY_GROUPS,
    expand_entity_groups,
)
from posejdon.domain.reports import LeakageScanResult, ProcessingReport, ValidationResult


def test_policy_profiles_include_required_defaults() -> None:
    assert "external_irreversible" in {key.value for key in DEFAULT_POLICY_PROFILES}


def test_processing_report_supports_required_fields() -> None:
    report = ProcessingReport(
        processing_mode=ProcessingMode.IRREVERSIBLE,
        input_document_type=DocumentKind.DOCX,
        output_document_type=DocumentKind.DOCX,
        detector_summary=DetectorSummary(
            llm_provider="mlx",
            llm_runtime_status="ready",
            llm_review_executed=True,
            llm_verification_executed=True,
        ),
        coverage_summary=CoverageSummary(
            segment_count=3,
            segments_with_detections=1,
            mention_memory_seed_count=1,
            mention_memory_expanded_count=2,
            mention_memory_ambiguous_skip_count=3,
        ),
        validation_results=ValidationResult(passed=True),
        leakage_scan_results=LeakageScanResult(),
        timing_metadata=TimingMetadata(),
    )
    assert report.subsystem_version == "0.1.0"
    assert report.validation_results.passed is True
    assert report.coverage_summary.segment_count == 3
    assert report.coverage_summary.mention_memory_seed_count == 1
    assert report.coverage_summary.mention_memory_expanded_count == 2
    assert report.coverage_summary.mention_memory_ambiguous_skip_count == 3
    assert report.detector_summary.llm_runtime_status == "ready"


def test_processing_mode_enum_exposes_reversible_mode() -> None:
    assert ProcessingMode.REVERSIBLE.value == "reversible"


def test_policy_entity_groups_expand_without_duplicates() -> None:
    expanded = expand_entity_groups("core_identity", "financial_identifiers", extra=("EMAIL",))
    assert "EMAIL" in expanded
    assert len(expanded) == len(set(expanded))
    assert "core_identity" in ENTITY_GROUPS


def test_settings_expose_llm_limits() -> None:
    settings = PosejdonSettings()
    assert settings.llm_segment_max_chars >= 256
    assert settings.llm_max_review_segments >= 1
    assert settings.llm_max_verification_segments >= 1


def test_sensitive_entity_roundtrips_mention_provenance() -> None:
    entity = SensitiveEntity(
        entity_id="person-mention-1",
        entity_type="PERSON",
        raw_text="Kowalskiemu",
        normalized_text="Kowalskiemu",
        confidence=0.91,
        source_detector="mention_memory",
    ).with_mention_provenance(
        MentionProvenance(
            canonical_entity_id="person-1",
            mention_cluster_id="cluster-1",
            derived_from="person-1",
            mention_source="memory",
            mention_rule="surname_dative",
        )
    )

    provenance = entity.mention_provenance()

    assert provenance is not None
    assert provenance.canonical_entity_id == "person-1"
    assert provenance.mention_cluster_id == "cluster-1"
    assert provenance.derived_from == "person-1"
    assert provenance.mention_source == "memory"
    assert provenance.mention_rule == "surname_dative"


def test_prompt_rendering_metadata_serializes_stable_identifiers_only() -> None:
    meta = PromptRenderingMetadata(
        prompt_id="posejdon-llm-review-v1",
        prompt_version="1.0.0",
        template_hash="deadbeef",
        rendered_at="2026-05-01T18:00:00Z",
    )
    payload = meta.model_dump_json()
    assert "posejdon-llm-review-v1" in payload
    assert "1.0.0" in payload
    assert "deadbeef" in payload
    assert "variables" not in payload


def test_audit_record_carries_optional_prompt_rendering() -> None:
    record = AuditRecord(
        audit_id="audit-123",
        mode=ProcessingMode.IRREVERSIBLE,
        input_hash="input-hash",
        output_hash="output-hash",
        report_hash="report-hash",
        created_at="2026-05-01T18:00:00Z",
        operator="test",
        policy_profile="external_irreversible",
        status=AuditStatus.SUCCEEDED,
        prompt_rendering=PromptRenderingMetadata(
            prompt_id="posejdon-verify-v1",
            prompt_version="2.0.0",
            template_hash="cafebabe",
        ),
    )
    assert record.prompt_rendering is not None
    assert record.prompt_rendering.prompt_id == "posejdon-verify-v1"
    assert record.prompt_rendering.prompt_version == "2.0.0"
    assert record.prompt_rendering.template_hash == "cafebabe"

    # Ensure backward compatibility: missing prompt_rendering is allowed
    minimal = AuditRecord(
        audit_id="audit-456",
        mode=ProcessingMode.IRREVERSIBLE,
        input_hash="a",
        output_hash="b",
        report_hash="c",
        created_at="2026-05-01T18:00:00Z",
        operator="test",
        policy_profile="external_irreversible",
        status=AuditStatus.SUCCEEDED,
    )
    assert minimal.prompt_rendering is None
