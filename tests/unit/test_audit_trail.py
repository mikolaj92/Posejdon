from datetime import UTC, datetime

from posejdon.core.enums import AuditStatus, DocumentKind, ProcessingMode
from posejdon.domain.artifacts import (
    AnonymizationAuditTrail,
    AuditRecord,
    EntityAuditEntry,
    ModeAuthorization,
    PromptRenderingMetadata,
)
from posejdon.domain.entities import SensitiveEntity
from posejdon.domain.models import CoverageSummary, DetectorSummary, TimingMetadata
from posejdon.domain.reports import LeakageScanResult, ProcessingReport, ValidationResult
from posejdon.storage.audit import AuditStore


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


def test_entity_audit_entry_serializes() -> None:
    entry = EntityAuditEntry(
        entity_type="PERSON",
        count=5,
        confidence_mean=0.85,
        confidence_median=0.87,
        confidence_min=0.72,
        confidence_max=0.95,
        anonymization_rationale="policy_driven",
    )
    payload = entry.model_dump_json()
    assert "PERSON" in payload
    assert "0.85" in payload
    assert "policy_driven" in payload


def test_mode_authorization_serializes() -> None:
    auth = ModeAuthorization(
        requested_mode=ProcessingMode.REVERSIBLE,
        effective_mode=ProcessingMode.REVERSIBLE,
        authorized_by="admin@example.com",
        authorization_source="explicit_override",
        authorization_reason="explicit_request",
        requires_justification=True,
        justification_provided="Legal hold requires reversible mode",
    )
    payload = auth.model_dump_json()
    assert "reversible" in payload
    assert "admin@example.com" in payload
    assert "explicit_override" in payload
    assert "Legal hold requires reversible mode" in payload


def test_audit_record_with_entity_audit_and_mode_auth() -> None:
    record = AuditRecord(
        audit_id="audit-789",
        mode=ProcessingMode.IRREVERSIBLE,
        input_hash="input",
        output_hash="output",
        report_hash="report",
        created_at="2026-05-01T18:00:00Z",
        operator="api_user",
        policy_profile="external_irreversible",
        status=AuditStatus.SUCCEEDED,
        entity_audit=[
            EntityAuditEntry(
                entity_type="PERSON",
                count=3,
                confidence_mean=0.91,
                confidence_median=0.92,
                confidence_min=0.88,
                confidence_max=0.95,
            ),
        ],
        mode_authorization=ModeAuthorization(
            requested_mode=ProcessingMode.IRREVERSIBLE,
            effective_mode=ProcessingMode.IRREVERSIBLE,
            authorized_by="api_user",
            authorization_source="runtime_default",
            authorization_reason="default_policy",
        ),
    )
    assert len(record.entity_audit) == 1
    assert record.entity_audit[0].entity_type == "PERSON"
    assert record.mode_authorization is not None
    assert record.mode_authorization.effective_mode == ProcessingMode.IRREVERSIBLE
    assert record.mode_authorization.authorization_source == "runtime_default"


def test_audit_store_chain_hash_computation(tmp_path) -> None:
    store = AuditStore(str(tmp_path))
    record = AuditRecord(
        audit_id="AUD_001",
        mode=ProcessingMode.IRREVERSIBLE,
        input_hash="a",
        output_hash="b",
        report_hash="c",
        created_at=datetime.now(UTC).isoformat(),
        operator="test",
        policy_profile="external_irreversible",
        status=AuditStatus.SUCCEEDED,
    )
    record.audit_chain_hash = store.compute_chain_hash(record)
    store.save(record)

    results = store.verify_chain()
    assert len(results) == 1
    assert results[0] == ("AUD_001", True)


def test_audit_store_chain_verification_detects_tampering(tmp_path) -> None:
    store = AuditStore(str(tmp_path))
    record = AuditRecord(
        audit_id="AUD_002",
        mode=ProcessingMode.IRREVERSIBLE,
        input_hash="a",
        output_hash="b",
        report_hash="c",
        created_at=datetime.now(UTC).isoformat(),
        operator="test",
        policy_profile="external_irreversible",
        status=AuditStatus.SUCCEEDED,
    )
    record.audit_chain_hash = store.compute_chain_hash(record)
    store.save(record)

    path = tmp_path / "AUD_002.json"
    content = path.read_text()
    content = content.replace('"operator": "test"', '"operator": "attacker"')
    path.write_text(content)

    results = store.verify_chain()
    assert len(results) == 1
    assert results[0] == ("AUD_002", False)


def test_audit_store_previous_hash_links_records(tmp_path) -> None:
    store = AuditStore(str(tmp_path))

    record1 = AuditRecord(
        audit_id="AUD_003",
        mode=ProcessingMode.IRREVERSIBLE,
        input_hash="a",
        output_hash="b",
        report_hash="c",
        created_at=datetime.now(UTC).isoformat(),
        operator="test",
        policy_profile="external_irreversible",
        status=AuditStatus.SUCCEEDED,
    )
    record1.audit_chain_hash = store.compute_chain_hash(record1)
    store.save(record1)

    previous_hash = store.get_previous_audit_hash()
    assert previous_hash is not None

    record2 = AuditRecord(
        audit_id="AUD_004",
        mode=ProcessingMode.IRREVERSIBLE,
        input_hash="d",
        output_hash="e",
        report_hash="f",
        created_at=datetime.now(UTC).isoformat(),
        operator="test",
        policy_profile="external_irreversible",
        status=AuditStatus.SUCCEEDED,
        previous_audit_hash=previous_hash,
    )
    record2.audit_chain_hash = store.compute_chain_hash(record2)
    store.save(record2)

    loaded = store.load("AUD_004")
    assert loaded.previous_audit_hash == previous_hash


def test_audit_store_list_all_returns_sorted_records(tmp_path) -> None:
    store = AuditStore(str(tmp_path))

    for i in range(3):
        record = AuditRecord(
            audit_id=f"AUD_{i:03d}",
            mode=ProcessingMode.IRREVERSIBLE,
            input_hash=f"input_{i}",
            output_hash=f"output_{i}",
            report_hash=f"report_{i}",
            created_at=datetime.now(UTC).isoformat(),
            operator="test",
            policy_profile="external_irreversible",
            status=AuditStatus.SUCCEEDED,
        )
        record.audit_chain_hash = store.compute_chain_hash(record)
        store.save(record)

    records = store.list_all()
    assert len(records) == 3
    assert all(isinstance(r, AuditRecord) for r in records)


def test_anonymization_audit_trail_with_tamper_evidence(tmp_path) -> None:
    store = AuditStore(str(tmp_path), secret="test_secret")
    trail = AnonymizationAuditTrail(
        audit_id="AUD_TAMPER_001",
        mode=ProcessingMode.IRREVERSIBLE,
        mode_authorization=ModeAuthorization(
            requested_mode=ProcessingMode.IRREVERSIBLE,
            effective_mode=ProcessingMode.IRREVERSIBLE,
            authorized_by="system",
            authorization_source="runtime_default",
        ),
        input_hash="input_hash",
        output_hash="output_hash",
        report_hash="report_hash",
        created_at="2026-05-11T12:00:00Z",
        operator="test",
        policy_profile="external_irreversible",
        status=AuditStatus.SUCCEEDED,
    )
    path = store.save_trail(trail)
    assert path.exists()

    loaded = store.load_trail("AUD_TAMPER_001")
    assert loaded.audit_id == "AUD_TAMPER_001"
    assert loaded.tamper_evidence_hash is not None


def test_anonymization_audit_trail_detects_tampering(tmp_path) -> None:
    store = AuditStore(str(tmp_path), secret="test_secret")
    trail = AnonymizationAuditTrail(
        audit_id="AUD_TAMPER_002",
        mode=ProcessingMode.IRREVERSIBLE,
        mode_authorization=ModeAuthorization(
            requested_mode=ProcessingMode.IRREVERSIBLE,
            effective_mode=ProcessingMode.IRREVERSIBLE,
            authorized_by="system",
            authorization_source="runtime_default",
        ),
        input_hash="input_hash",
        output_hash="output_hash",
        report_hash="report_hash",
        created_at="2026-05-11T12:00:00Z",
        operator="test",
        policy_profile="external_irreversible",
        status=AuditStatus.SUCCEEDED,
    )
    store.save_trail(trail)

    audit_file = tmp_path / "AUD_TAMPER_002.json"
    content = audit_file.read_text()
    tampered = content.replace("input_hash", "tampered_hash")
    audit_file.write_text(tampered)

    try:
        store.load_trail("AUD_TAMPER_002")
        raise AssertionError("Should have raised ValueError for tampered audit")
    except ValueError as exc:
        assert "tampered" in str(exc).lower()


def test_entity_audit_entry_from_sensitive_entities() -> None:
    entities = [
        SensitiveEntity(
            entity_id="e1",
            entity_type="PERSON",
            raw_text="Alice",
            normalized_text="Alice",
            confidence=0.95,
            source_detector="regex",
        ),
        SensitiveEntity(
            entity_id="e2",
            entity_type="PERSON",
            raw_text="Bob",
            normalized_text="Bob",
            confidence=0.85,
            source_detector="regex",
        ),
        SensitiveEntity(
            entity_id="e3",
            entity_type="EMAIL",
            raw_text="test@example.com",
            normalized_text="test@example.com",
            confidence=0.92,
            source_detector="regex",
        ),
    ]

    entries = EntityAuditEntry.build_entity_audit(entities)
    assert len(entries) == 2

    person_entry = next(e for e in entries if e.entity_type == "PERSON")
    assert person_entry.count == 2
    assert person_entry.confidence_mean == 0.9
    assert person_entry.confidence_median == 0.9
    assert person_entry.confidence_min == 0.85
    assert person_entry.confidence_max == 0.95

    email_entry = next(e for e in entries if e.entity_type == "EMAIL")
    assert email_entry.count == 1
    assert email_entry.confidence_mean == 0.92


def test_entity_audit_entry_empty_entities() -> None:
    entries = EntityAuditEntry.build_entity_audit([])
    assert entries == []


def test_entity_audit_entry_no_confidence() -> None:
    entities = [
        SensitiveEntity(
            entity_id="e1",
            entity_type="PERSON",
            raw_text="Alice",
            normalized_text="Alice",
            confidence=0.0,
            source_detector="regex",
        ),
    ]

    entries = EntityAuditEntry.build_entity_audit(entities)
    assert len(entries) == 1
    assert entries[0].confidence_mean == 0.0
    assert entries[0].confidence_min == 0.0
    assert entries[0].confidence_max == 0.0
