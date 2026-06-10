from __future__ import annotations

from enum import StrEnum


class DocumentKind(StrEnum):
    DOCX = "docx"
    PDF = "pdf"
    JSON = "json"
    XML = "xml"
    TEXT = "text"


class ProcessingMode(StrEnum):
    IRREVERSIBLE = "irreversible"
    REVERSIBLE = "reversible"


class StorageMode(StrEnum):
    LOCAL_FS = "local_fs"
    SECURE_FS = "secure_fs"
    OBJECT_STORE_COMPATIBLE = "object_store_compatible"


class ReplacementKind(StrEnum):
    CATEGORY_PLACEHOLDER = "category_placeholder"
    MASK = "mask"
    DETERMINISTIC_PSEUDONYM = "deterministic_pseudonym"
    FORMAT_PRESERVING = "format_preserving"


class PolicyProfileName(StrEnum):
    EXTERNAL_IRREVERSIBLE = "external_irreversible"
    LEGAL_REVIEW = "legal_review"
    HR_DOCUMENTS = "hr_documents"
    FINANCE_DOCUMENTS = "finance_documents"
    CUSTOM = "custom"


class AuditStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class LLMProfile(StrEnum):
    FAST = "fast"
    BALANCED = "balanced"
    FULL = "full"


class ReinjectionConflictReason(StrEnum):
    AMBIGUOUS_SEGMENT_MATCH = "ambiguous_segment_match"
    MISSING_SEGMENT = "missing_segment"
    SEGMENT_SPLIT = "segment_split"
    SEGMENT_MERGE = "segment_merge"
    CONTAINER_MISMATCH = "container_mismatch"
    PAGE_INDEX_MISMATCH = "page_index_mismatch"
    SECTION_MISMATCH = "section_mismatch"
    PLACEHOLDER_DELETED = "placeholder_deleted"
    PLACEHOLDER_DUPLICATED = "placeholder_duplicated"
    PLACEHOLDER_REORDERED = "placeholder_reordered"
    PLACEHOLDER_DRIFT = "placeholder_drift"
    LOW_CONFIDENCE_MATCH = "low_confidence_match"
    MISSING_VAULT_ENTRY = "missing_vault_entry"
    INTEGRITY_MISMATCH = "integrity_mismatch"
    UNSUPPORTED_TRANSFORM = "unsupported_transform"
