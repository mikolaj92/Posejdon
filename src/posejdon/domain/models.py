from __future__ import annotations

from pydantic import BaseModel, Field

from posejdon.core.enums import DocumentKind, StorageMode


class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class ProcessingRequest(BaseModel):
    input_path: str
    language: str = "pl"
    policy_profile: str | None = None
    output_preferences: dict[str, str] = Field(default_factory=dict)


class OutputPreferences(BaseModel):
    output_dir: str | None = None
    json_report_pretty: bool = True
    storage_mode: StorageMode = StorageMode.LOCAL_FS


class DetectorSummary(BaseModel):
    regex_enabled: bool = True
    regex_status: str = "ready"
    presidio_enabled: bool = False
    presidio_status: str = "disabled"
    gliner_enabled: bool = False
    gliner_status: str = "disabled"
    llm_review_enabled: bool = True
    llm_provider: str | None = None
    llm_profile: str | None = None
    llm_runtime_status: str = "disabled"
    llm_review_executed: bool = False
    llm_verification_executed: bool = False


class CoverageSummary(BaseModel):
    segment_count: int = 0
    layout_segment_count: int = 0
    page_count: int = 0
    segments_with_detections: int = 0
    segments_with_replacements: int = 0
    mention_memory_seed_count: int = 0
    mention_memory_expanded_count: int = 0
    mention_memory_ambiguous_skip_count: int = 0
    llm_segments_reviewed: int = 0
    llm_segments_verified: int = 0
    llm_review_budget: int = 0
    llm_verification_budget: int = 0
    llm_verification_scope: str = "none"
    llm_verification_skipped_reason: str | None = None
    llm_verification_window_count: int = 0
    llm_verification_cache_hits: int = 0
    llm_verification_cache_misses: int = 0
    llm_chunked_segment_count: int = 0
    llm_verification_coverage_complete: bool = False
    detected_segment_ids: list[str] = Field(default_factory=list)
    replaced_segment_ids: list[str] = Field(default_factory=list)
    llm_reviewed_segment_ids: list[str] = Field(default_factory=list)
    llm_verified_segment_ids: list[str] = Field(default_factory=list)


class TimingMetadata(BaseModel):
    parse_ms: int = 0
    detect_ms: int = 0
    plan_ms: int = 0
    render_ms: int = 0
    validate_ms: int = 0
    llm_runtime_prepare_ms: int = 0
    llm_review_ms: int = 0
    llm_verification_ms: int = 0


class LLMVerificationWindowEntry(BaseModel):
    segment_id: str
    chunk_id: str | None = None
    start_char: int
    end_char: int
    text: str


class LLMVerificationWindow(BaseModel):
    window_id: str
    group_key: str
    segment_ids: list[str] = Field(default_factory=list)
    entries: list[LLMVerificationWindowEntry] = Field(default_factory=list)
    text: str = ""


class ValidationCheck(BaseModel):
    name: str
    passed: bool
    details: str | None = None


class MetadataPolicy(BaseModel):
    strip_doc_properties: bool = True
    strip_pdf_metadata: bool = True


class SupportedFeatureSet(BaseModel):
    supported: list[str] = Field(default_factory=list)
    unsupported: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DocumentReference(BaseModel):
    path: str
    kind: DocumentKind
