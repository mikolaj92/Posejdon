from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

Normalizer = Callable[[str], str]
Validator = Callable[[str], bool]


def normalize_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_upper_alnum(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def normalize_date_context(value: str) -> str:
    return re.sub(
        r"^(?:ur\.?|data urodzenia[: ]|dob[: ])\s*",
        "",
        value.strip(),
        flags=re.IGNORECASE,
    )


def normalize_case_identifier(value: str) -> str:
    return value.strip().upper()


def normalize_swift_bic(value: str) -> str:
    match = re.search(
        r"\b([A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?)\b",
        value.upper(),
    )
    return match.group(1) if match else ""


def validate_email(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", value, re.IGNORECASE))


def validate_phone(value: str) -> bool:
    digits = normalize_digits(value)
    return len(digits) in {9, 11} and (len(digits) == 9 or digits.startswith("48"))


def validate_pesel(value: str) -> bool:
    digits = normalize_digits(value)
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
    checksum = sum(int(digit) * weight for digit, weight in zip(digits[:10], weights, strict=True))
    control = (10 - (checksum % 10)) % 10
    if control != int(digits[10]):
        return False
    month = int(digits[2:4])
    century_offsets = {80: 1800, 0: 1900, 20: 2000, 40: 2100, 60: 2200}
    for offset, century in century_offsets.items():
        if offset < month <= offset + 12:
            try:
                datetime(
                    year=century + int(digits[0:2]),
                    month=month - offset,
                    day=int(digits[4:6]),
                )
                return True
            except ValueError:
                return False
    return False


def validate_nip(value: str) -> bool:
    digits = normalize_digits(value)
    if len(digits) != 10:
        return False
    weights = [6, 5, 7, 2, 3, 4, 5, 6, 7]
    checksum = (
        sum(int(digit) * weight for digit, weight in zip(digits[:9], weights, strict=True)) % 11
    )
    return checksum != 10 and checksum == int(digits[9])


def validate_regon(value: str) -> bool:
    digits = normalize_digits(value)
    if len(digits) == 9:
        weights = [8, 9, 2, 3, 4, 5, 6, 7]
        checksum = (
            sum(int(digit) * weight for digit, weight in zip(digits[:8], weights, strict=True)) % 11
        )
        checksum = 0 if checksum == 10 else checksum
        return checksum == int(digits[8])
    if len(digits) == 14:
        weights = [2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8]
        checksum = (
            sum(int(digit) * weight for digit, weight in zip(digits[:13], weights, strict=True))
            % 11
        )
        checksum = 0 if checksum == 10 else checksum
        return checksum == int(digits[13])
    return False


def validate_krs(value: str) -> bool:
    digits = normalize_digits(value)
    return len(digits) == 10 and digits.isdigit()


def validate_iban(value: str) -> bool:
    compact = normalize_upper_alnum(value)
    if len(compact) < 15 or len(compact) > 34:
        return False
    rearranged = compact[4:] + compact[:4]
    numeric = "".join(str(int(char, 36)) for char in rearranged)
    return int(numeric) % 97 == 1


def validate_bank_account(value: str) -> bool:
    compact = normalize_upper_alnum(value)
    digits = normalize_digits(value)
    if compact.startswith("PL") and len(compact) == 28:
        return validate_iban(compact)
    if len(digits) == 26:
        return validate_iban(f"PL{digits}")
    return validate_iban(value)


def validate_card_number(value: str) -> bool:
    digits = normalize_digits(value)
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        current = int(digit)
        if index % 2 == parity:
            current *= 2
            if current > 9:
                current -= 9
        checksum += current
    return checksum % 10 == 0


def validate_postal_code(value: str) -> bool:
    return bool(re.fullmatch(r"\d{2}-\d{3}", value))


def validate_date_of_birth(value: str) -> bool:
    candidate = normalize_date_context(value)
    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            datetime.strptime(candidate, fmt)
            return True
        except ValueError:
            continue
    return False


def validate_document_number(value: str) -> bool:
    cleaned = normalize_upper_alnum(value)
    return 6 <= len(cleaned) <= 24 and any(char.isdigit() for char in cleaned)


def validate_case_number(value: str) -> bool:
    return bool(re.search(r"\b[A-Z]{1,6}\s*[A-Z]?\s*\d+/\d{2,4}\b", value.upper()))


def validate_contract_number(value: str) -> bool:
    compact = normalize_case_identifier(value)
    return bool(
        re.search(
            r"\b(?:CONTRACT|UMOWA|AGR|CNT)(?:\s+(?:NUMBER|NO|NR))?"
            r"[-/_ :]*[A-Z0-9/_-]*\d[A-Z0-9/_-]{2,}\b",
            compact,
        )
    )


def validate_swift_bic(value: str) -> bool:
    compact = normalize_swift_bic(value) or normalize_upper_alnum(value)
    return bool(re.fullmatch(r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?", compact))


def validate_generic_reference(value: str) -> bool:
    cleaned = normalize_upper_alnum(value)
    return 4 <= len(cleaned) <= 32 and any(char.isdigit() for char in cleaned)


def validate_vat_id(value: str) -> bool:
    compact = normalize_upper_alnum(value)
    match = re.search(
        r"(?:VATUE|VATID|UEVAT|EUVAT|VAT)[A-Z0-9]*?([A-Z]{2}[A-Z0-9]{6,14}|\d{10,14})\b",
        compact,
    )
    if not match:
        return False
    candidate = match.group(1)
    if candidate.startswith("PL") and len(candidate) == 12:
        return validate_nip(candidate[2:])
    if candidate.isdigit():
        return 10 <= len(candidate) <= 14
    return len(candidate) >= 8


def validate_tax_id(value: str) -> bool:
    compact = normalize_upper_alnum(value)
    match = re.search(
        r"(?:TAXID|TIN|IDENTYFIKATORPODATKOWY)[A-Z0-9]*?([A-Z]{2}[A-Z0-9]{6,14}|\d{10,14}|[A-Z0-9]{6,18})\b",
        compact,
    )
    if not match:
        return False
    candidate = match.group(1)
    if candidate.startswith("PL") and len(candidate) == 12:
        return validate_nip(candidate[2:])
    if candidate.isdigit():
        return len(candidate) in {10, 11, 12, 13, 14}
    return 6 <= len(candidate) <= 18 and any(char.isdigit() for char in candidate)


def validate_address(value: str) -> bool:
    candidate = value.strip()
    street_markers = ("ul.", "al.", "pl.", "os.", "ulica", "aleja")
    has_street = any(marker in candidate.lower() for marker in street_markers)
    has_number = bool(re.search(r"\b\d+[A-Z]?(?:/\d+[A-Z]?)?\b", candidate, re.IGNORECASE))
    has_postal = bool(re.search(r"\b\d{2}-\d{3}\b", candidate))
    return (has_street and has_number) or (has_postal and has_number)


def validate_person_full_name(value: str) -> bool:
    candidate = " ".join(value.strip().split())
    if not candidate:
        return False
    if not re.fullmatch(
        r"[A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+(?:-[A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+)?"
        r"\s+"
        r"[A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+(?:-[A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+)?",
        candidate,
    ):
        return False

    blocked_tokens = {
        "Charakter",
        "Data",
        "Dane",
        "Dodatkowe",
        "Liczba",
        "Miejsce",
        "Strona",
        "Testowe",
        "Umowa",
        "Wszystkie",
    }
    return not any(token in blocked_tokens for token in candidate.split())


NORMALIZERS: dict[str, Normalizer] = {
    "digits": normalize_digits,
    "email": normalize_email,
    "upper_alnum": normalize_upper_alnum,
    "date_context": normalize_date_context,
    "case_identifier": normalize_case_identifier,
    "swift_bic": normalize_swift_bic,
    "identity": lambda value: value,
}

VALIDATORS: dict[str, Validator] = {
    "always_true": lambda value: True,
    "email": validate_email,
    "phone": validate_phone,
    "pesel": validate_pesel,
    "nip": validate_nip,
    "regon": validate_regon,
    "krs": validate_krs,
    "iban": validate_iban,
    "bank_account": validate_bank_account,
    "card_number": validate_card_number,
    "postal_code": validate_postal_code,
    "date_of_birth": validate_date_of_birth,
    "document_number": validate_document_number,
    "case_number": validate_case_number,
    "contract_number": validate_contract_number,
    "swift_bic": validate_swift_bic,
    "generic_reference": validate_generic_reference,
    "vat_id": validate_vat_id,
    "tax_id": validate_tax_id,
    "address": validate_address,
    "person_full_name": validate_person_full_name,
}


@dataclass(frozen=True, slots=True)
class RegexRule:
    entity_type: str
    pattern_text: str
    normalizer_name: str
    validator_name: str
    confidence: float
    context_required: bool = False

    @property
    def pattern(self) -> re.Pattern[str]:
        return re.compile(self.pattern_text, re.IGNORECASE)

    @property
    def normalizer(self) -> Normalizer:
        return NORMALIZERS[self.normalizer_name]

    @property
    def validator(self) -> Validator:
        return VALIDATORS[self.validator_name]


def build_entity_id(
    *,
    entity_type: str,
    normalized_text: str,
    start_offset: int,
    end_offset: int,
) -> str:
    digest = hashlib.sha1(
        f"{entity_type}|{normalized_text}|{start_offset}|{end_offset}".encode(),
        usedforsecurity=False,
    ).hexdigest()
    return f"ENT_{digest[:12]}"
