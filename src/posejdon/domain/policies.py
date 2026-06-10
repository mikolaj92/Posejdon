from __future__ import annotations

from pydantic import BaseModel, Field

from posejdon.core.enums import PolicyProfileName, ReplacementKind
from posejdon.domain.models import MetadataPolicy


class ConfidenceThresholds(BaseModel):
    accept_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    review_threshold: float = Field(default=0.60, ge=0.0, le=1.0)


class OutputNamingRules(BaseModel):
    suffix: str
    preserve_extension: bool = True


class PolicyProfileDefinition(BaseModel):
    name: PolicyProfileName
    entity_classes: list[str]
    replacement_style: ReplacementKind
    output_naming: OutputNamingRules
    metadata_policy: MetadataPolicy
    llm_review_allowed: bool
    confidence_thresholds: ConfidenceThresholds
    fail_on_unsupported: bool = False
    warn_on_unsupported: bool = True


ENTITY_GROUPS: dict[str, tuple[str, ...]] = {
    "core_identity": (
        "PERSON",
        "ORG",
        "EMAIL",
        "PHONE",
        "PESEL",
        "NIP",
    ),
    "financial_identifiers": (
        "IBAN",
        "BANK_ACCOUNT",
        "SWIFT_BIC",
        "CARD",
        "REGON",
        "KRS",
        "VAT_ID",
        "TAX_ID",
    ),
    "addressing": (
        "ADDRESS",
        "POSTAL_CODE",
        "CITY",
        "STREET",
        "HOUSE_NUMBER",
        "APARTMENT_NUMBER",
        "COUNTRY",
        "PLACE_OF_BIRTH",
    ),
    "document_identity": (
        "DOCUMENT_NUMBER",
        "PASSPORT_NUMBER",
        "ID_CARD_NUMBER",
        "DRIVER_LICENSE_NUMBER",
        "DATE_OF_BIRTH",
    ),
    "case_and_contract_refs": (
        "CASE_NUMBER",
        "CONTRACT_NUMBER",
        "INVOICE_NUMBER",
        "ORDER_NUMBER",
        "POLICY_NUMBER",
        "CLAIM_NUMBER",
    ),
    "workforce_refs": (
        "CLIENT_ID",
        "EMPLOYEE_ID",
    ),
}


def expand_entity_groups(*group_names: str, extra: tuple[str, ...] = ()) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for group_name in group_names:
        for entity_type in ENTITY_GROUPS[group_name]:
            if entity_type in seen:
                continue
            seen.add(entity_type)
            ordered.append(entity_type)
    for entity_type in extra:
        if entity_type in seen:
            continue
        seen.add(entity_type)
        ordered.append(entity_type)
    return ordered


DEFAULT_POLICY_PROFILES: dict[PolicyProfileName, PolicyProfileDefinition] = {
    PolicyProfileName.EXTERNAL_IRREVERSIBLE: PolicyProfileDefinition(
        name=PolicyProfileName.EXTERNAL_IRREVERSIBLE,
        entity_classes=expand_entity_groups(
            "core_identity",
            "financial_identifiers",
            "addressing",
            "document_identity",
            "case_and_contract_refs",
            "workforce_refs",
        ),
        replacement_style=ReplacementKind.CATEGORY_PLACEHOLDER,
        output_naming=OutputNamingRules(suffix="_anonymized"),
        metadata_policy=MetadataPolicy(),
        llm_review_allowed=True,
        confidence_thresholds=ConfidenceThresholds(),
        fail_on_unsupported=True,
    ),
    PolicyProfileName.LEGAL_REVIEW: PolicyProfileDefinition(
        name=PolicyProfileName.LEGAL_REVIEW,
        entity_classes=expand_entity_groups(
            "core_identity",
            extra=("CASE_NUMBER", "CONTRACT_NUMBER"),
        ),
        replacement_style=ReplacementKind.FORMAT_PRESERVING,
        output_naming=OutputNamingRules(suffix="_legal_review"),
        metadata_policy=MetadataPolicy(),
        llm_review_allowed=True,
        confidence_thresholds=ConfidenceThresholds(accept_threshold=0.80, review_threshold=0.55),
    ),
    PolicyProfileName.HR_DOCUMENTS: PolicyProfileDefinition(
        name=PolicyProfileName.HR_DOCUMENTS,
        entity_classes=expand_entity_groups(
            "core_identity",
            "addressing",
            "document_identity",
            extra=("EMPLOYEE_ID",),
        ),
        replacement_style=ReplacementKind.CATEGORY_PLACEHOLDER,
        output_naming=OutputNamingRules(suffix="_hr"),
        metadata_policy=MetadataPolicy(),
        llm_review_allowed=False,
        confidence_thresholds=ConfidenceThresholds(),
    ),
    PolicyProfileName.FINANCE_DOCUMENTS: PolicyProfileDefinition(
        name=PolicyProfileName.FINANCE_DOCUMENTS,
        entity_classes=expand_entity_groups(
            "core_identity",
            "financial_identifiers",
            "case_and_contract_refs",
            extra=("CLIENT_ID",),
        ),
        replacement_style=ReplacementKind.MASK,
        output_naming=OutputNamingRules(suffix="_finance"),
        metadata_policy=MetadataPolicy(),
        llm_review_allowed=False,
        confidence_thresholds=ConfidenceThresholds(),
    ),
    PolicyProfileName.CUSTOM: PolicyProfileDefinition(
        name=PolicyProfileName.CUSTOM,
        entity_classes=[],
        replacement_style=ReplacementKind.CATEGORY_PLACEHOLDER,
        output_naming=OutputNamingRules(suffix="_custom"),
        metadata_policy=MetadataPolicy(),
        llm_review_allowed=False,
        confidence_thresholds=ConfidenceThresholds(),
    ),
}
