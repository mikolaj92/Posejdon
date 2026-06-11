from __future__ import annotations

import sqlite3
from pathlib import Path

from posejdon.core.errors import InvalidRegexCatalogError
from posejdon.detectors.regex_support import NORMALIZERS, VALIDATORS, RegexRule

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entity_types (
    entity_type TEXT PRIMARY KEY,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS regex_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL REFERENCES entity_types(entity_type),
    pattern_text TEXT NOT NULL,
    normalizer_name TEXT NOT NULL,
    validator_name TEXT NOT NULL,
    confidence REAL NOT NULL,
    context_required INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 100,
    enabled INTEGER NOT NULL DEFAULT 1,
    description TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_regex_rules_entity_enabled
ON regex_rules(entity_type, enabled, priority);

CREATE UNIQUE INDEX IF NOT EXISTS idx_regex_rules_unique_signature
ON regex_rules(entity_type, pattern_text, normalizer_name, validator_name);
"""

DEFAULT_ENTITY_TYPES: tuple[tuple[str, str], ...] = (
    ("EMAIL", "Email addresses"),
    ("PHONE", "Phone numbers"),
    ("PESEL", "Polish PESEL identifiers"),
    ("NIP", "Polish NIP tax identifiers"),
    ("REGON", "Polish REGON identifiers"),
    ("KRS", "Polish KRS identifiers"),
    ("IBAN", "International bank account numbers"),
    ("CARD", "Card-like payment numbers"),
    ("POSTAL_CODE", "Postal codes"),
    ("DATE_OF_BIRTH", "Date of birth variants"),
    ("DOCUMENT_NUMBER", "Document numbers"),
    ("CASE_NUMBER", "Case numbers"),
    ("CONTRACT_NUMBER", "Contract numbers"),
    ("ADDRESS", "Postal addresses"),
    ("BANK_ACCOUNT", "Bank account references"),
    ("SWIFT_BIC", "SWIFT/BIC bank identifiers"),
    ("INVOICE_NUMBER", "Invoice numbers"),
    ("ORDER_NUMBER", "Order numbers"),
    ("POLICY_NUMBER", "Insurance policy numbers"),
    ("CLAIM_NUMBER", "Claim numbers"),
    ("CLIENT_ID", "Client identifiers"),
    ("EMPLOYEE_ID", "Employee identifiers"),
    ("PASSPORT_NUMBER", "Passport identifiers"),
    ("ID_CARD_NUMBER", "ID card identifiers"),
    ("DRIVER_LICENSE_NUMBER", "Driver license identifiers"),
    ("VAT_ID", "VAT identifiers"),
    ("TAX_ID", "Tax identifiers"),
    ("COMPANY_NAME", "Company names"),
    ("FULL_NAME", "Full personal names"),
    ("FIRST_NAME", "First names"),
    ("LAST_NAME", "Last names"),
    ("CITY", "City references"),
    ("STREET", "Street references"),
    ("HOUSE_NUMBER", "House number references"),
    ("APARTMENT_NUMBER", "Apartment number references"),
    ("COUNTRY", "Country references"),
    ("PLACE_OF_BIRTH", "Place of birth references"),
)

DEFAULT_REGEX_RULES: tuple[tuple[str, str, str, str, float, int, int, str], ...] = (
    (
        "EMAIL",
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "email",
        "email",
        0.99,
        0,
        10,
        "Standard email address",
    ),
    (
        "PHONE",
        r"(?:(?<!\d)(?:(?:\(\+?48\)|\+?48|0048)[\s-]*)?(?:\d[\s-]*){8}\d(?!\d))",
        "digits",
        "phone",
        0.96,
        0,
        10,
        "Polish phone number",
    ),
    ("PESEL", r"\b\d{11}\b", "digits", "pesel", 0.995, 0, 10, "PESEL"),
    ("NIP", r"\b\d{3}-?\d{3}-?\d{2}-?\d{2}\b", "digits", "nip", 0.99, 0, 10, "NIP"),
    ("REGON", r"\b\d{9}(?:\d{5})?\b", "digits", "regon", 0.98, 0, 10, "REGON"),
    (
        "KRS",
        r"\b(?:KRS|nr\s*KRS)[:\s#/-]*\d{10}\b",
        "digits",
        "krs",
        0.97,
        1,
        10,
        "KRS with context label",
    ),
    (
        "REGON",
        r"\b(?:REGON|nr\s*REGON)[:\s#/-]*\d{9}(?:\d{5})?\b",
        "digits",
        "regon",
        0.985,
        1,
        9,
        "REGON with context label",
    ),
    (
        "NIP",
        r"\b(?:NIP|Tax\s*ID|Identyfikator\s*podatkowy)[:\s#/-]*\d{3}-?\d{3}-?\d{2}-?\d{2}\b",
        "digits",
        "nip",
        0.992,
        1,
        9,
        "NIP with context label",
    ),
    (
        "IBAN",
        r"\b[A-Z]{2}\d{2}(?:[\s-]?[A-Z0-9]{4}){3,7}\b",
        "upper_alnum",
        "iban",
        0.99,
        0,
        10,
        "IBAN",
    ),
    (
        "BANK_ACCOUNT",
        r"(?:(?<![A-Z0-9])(?:PL[\s-]*)?(?:\d[\s-]*){25}\d(?!\d))",
        "upper_alnum",
        "bank_account",
        0.98,
        0,
        15,
        "Bank account number",
    ),
    (
        "VAT_ID",
        r"\b(?:VAT(?:\s*ID|\s*UE)?|UE\s*VAT|EU\s*VAT)[:\s#/-]*(?:[A-Z]{2}\s*)?[A-Z0-9-]{8,16}\b",
        "upper_alnum",
        "vat_id",
        0.95,
        1,
        12,
        "VAT identifier with context label",
    ),
    (
        "TAX_ID",
        r"\b(?:TIN|Tax\s*ID|Identyfikator\s*podatkowy)[:\s#/-]*(?:[A-Z]{2}\s*)?[A-Z0-9-]{6,18}\b",
        "upper_alnum",
        "tax_id",
        0.94,
        1,
        12,
        "Tax identifier with context label",
    ),
    (
        "SWIFT_BIC",
        r"\b(?:SWIFT|BIC)(?:[:\s/-]+)([A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?)\b",
        "swift_bic",
        "swift_bic",
        0.96,
        1,
        20,
        "SWIFT/BIC code with context label",
    ),
    ("CARD", r"\b(?:\d[ -]?){13,19}\b", "digits", "card_number", 0.97, 0, 10, "Card-like number"),
    (
        "POSTAL_CODE",
        r"\b\d{2}-\d{3}\b",
        "identity",
        "postal_code",
        0.95,
        0,
        10,
        "Postal code",
    ),
    (
        "DATE_OF_BIRTH",
        (
            r"\b(?:ur\.?|data urodzenia[: ]|dob[: ])\s*"
            r"(?:\d{2}[./-]\d{2}[./-]\d{4}|\d{4}-\d{2}-\d{2})\b"
        ),
        "date_context",
        "date_of_birth",
        0.94,
        1,
        10,
        "Date of birth with context",
    ),
    (
        "DATE_OF_BIRTH",
        r"\b\d{2}[./-]\d{2}[./-]\d{4}\b",
        "identity",
        "date_of_birth",
        0.88,
        1,
        20,
        "Standalone date of birth candidate",
    ),
    (
        "DOCUMENT_NUMBER",
        r"\b(?:dow[oó]d(?:\s+osobisty)?|passport|paszport|nr dokumentu)"
        r"(?:[:\s#/-]+nr)?[:\s#/-]*[A-Z0-9-]*\d[A-Z0-9-]{4,23}\b",
        "upper_alnum",
        "document_number",
        0.92,
        1,
        10,
        "Document number with context",
    ),
    (
        "PASSPORT_NUMBER",
        r"\b(?:passport|paszport)(?:[:\s#/-]+nr)?[:\s#/-]*[A-Z0-9-]*\d[A-Z0-9-]{4,23}\b",
        "upper_alnum",
        "document_number",
        0.93,
        1,
        12,
        "Passport number with context",
    ),
    (
        "ID_CARD_NUMBER",
        r"\b(?:dow[oó]d(?:\s+osobisty)?|id card|nr dowodu)"
        r"(?:[:\s#/-]+nr)?[:\s#/-]*[A-Z0-9-]*\d[A-Z0-9-]{4,23}\b",
        "upper_alnum",
        "document_number",
        0.93,
        1,
        12,
        "ID card number with context",
    ),
    (
        "DRIVER_LICENSE_NUMBER",
        r"\b(?:prawo jazdy|driver'?s license)"
        r"(?:[:\s#/-]+nr)?[:\s#/-]*[A-Z0-9-]*\d[A-Z0-9-]{4,23}\b",
        "upper_alnum",
        "document_number",
        0.92,
        1,
        12,
        "Driver license number with context",
    ),
    (
        "CASE_NUMBER",
        r"\b(?:sygn\.?\s*akt|case\s*no\.?|sprawa)[:\s]*[A-Z]{1,6}\s*[A-Z]?\s*\d+/\d{2,4}\b",
        "case_identifier",
        "case_number",
        0.94,
        1,
        10,
        "Case number",
    ),
    (
        "CONTRACT_NUMBER",
        r"\b(?:umowa\s*nr|contract\s*(?:number|no\.?|nr)|agreement\s*(?:number|no\.?|nr))[:\s#/-]*[A-Z0-9/_-]*\d[A-Z0-9/_-]{2,24}\b",
        "case_identifier",
        "contract_number",
        0.92,
        1,
        10,
        "Contract number",
    ),
    (
        "INVOICE_NUMBER",
        r"\b(?:faktura\s*nr|invoice\s*(?:number|no\.?|nr)|fv)[:\s#/-]*[A-Z0-9/_-]*\d[A-Z0-9/_-]{2,32}\b",
        "case_identifier",
        "generic_reference",
        0.93,
        1,
        10,
        "Invoice number",
    ),
    (
        "ORDER_NUMBER",
        r"\b(?:zam[oó]wienie\s*nr|order\s*(?:number|no\.?|nr))[:\s#/-]*[A-Z0-9/_-]*\d[A-Z0-9/_-]{2,32}\b",
        "case_identifier",
        "generic_reference",
        0.92,
        1,
        10,
        "Order number",
    ),
    (
        "POLICY_NUMBER",
        r"\b(?:polisa\s*nr|policy\s*(?:number|no\.?|nr))[:\s#/-]*[A-Z0-9/_-]*\d[A-Z0-9/_-]{2,32}\b",
        "case_identifier",
        "generic_reference",
        0.92,
        1,
        10,
        "Policy number",
    ),
    (
        "CLAIM_NUMBER",
        r"\b(?:szkoda\s*nr|claim\s*(?:number|no\.?|nr))[:\s#/-]*[A-Z0-9/_-]*\d[A-Z0-9/_-]{2,32}\b",
        "case_identifier",
        "generic_reference",
        0.91,
        1,
        10,
        "Claim number",
    ),
    (
        "CLIENT_ID",
        r"\b(?:client|klient)[:\s#/-]+(?:id|nr)[:\s#/-]*[A-Z0-9/_-]*\d[A-Z0-9/_-]{2,24}\b",
        "case_identifier",
        "generic_reference",
        0.9,
        1,
        15,
        "Client identifier",
    ),
    (
        "EMPLOYEE_ID",
        r"\b(?:employee|pracownik)[:\s#/-]+(?:id|nr)[:\s#/-]*[A-Z0-9/_-]*\d[A-Z0-9/_-]{2,24}\b",
        "case_identifier",
        "generic_reference",
        0.9,
        1,
        15,
        "Employee identifier",
    ),
    (
        "ADDRESS",
        (
            r"\b(?:ul\.|al\.|pl\.|os\.|ulica|aleja)\s+"
            r"[A-ZĄĆĘŁŃÓŚŹŻ0-9][A-ZĄĆĘŁŃÓŚŹŻ0-9 .-]{1,40}\s+"
            r"\d+[A-Z]?(?:/\d+[A-Z]?)?"
            r"(?:,\s*\d{2}-\d{3}\s+[A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż -]+)?\b"
        ),
        "identity",
        "address",
        0.93,
        1,
        10,
        "Street address with house number",
    ),
    (
        "ADDRESS",
        (
            r"\b\d{2}-\d{3}\s+[A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż -]+"
            r"(?:,\s*(?:ul\.|al\.|pl\.|os\.)\s+"
            r"[A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż0-9 .-]+\s+\d+[A-Z]?"
            r"(?:/\d+[A-Z]?)?)?\b"
        ),
        "identity",
        "address",
        0.9,
        1,
        20,
        "Postal code plus city address",
    ),
)

MANAGED_RULE_DESCRIPTIONS: tuple[str, ...] = tuple({rule[7] for rule in DEFAULT_REGEX_RULES})


class RegexCatalogStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def bootstrap(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.executescript(SCHEMA_SQL)
            connection.executemany(
                "INSERT OR IGNORE INTO entity_types(entity_type, description) VALUES (?, ?)",
                DEFAULT_ENTITY_TYPES,
            )
            placeholders = ", ".join("?" for _ in MANAGED_RULE_DESCRIPTIONS)
            connection.execute(
                f"DELETE FROM regex_rules WHERE description IN ({placeholders})",
                MANAGED_RULE_DESCRIPTIONS,
            )
            connection.executemany(
                """
                INSERT INTO regex_rules(
                    entity_type,
                    pattern_text,
                    normalizer_name,
                    validator_name,
                    confidence,
                    context_required,
                    priority,
                    enabled,
                    description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                DEFAULT_REGEX_RULES,
            )
            connection.commit()

    def load_rules(self, allowed_entity_types: set[str] | None = None) -> list[RegexRule]:
        self.bootstrap()
        query = """
            SELECT
                entity_type,
                pattern_text,
                normalizer_name,
                validator_name,
                confidence,
                context_required
            FROM regex_rules
            WHERE enabled = 1
        """
        params: list[str] = []
        if allowed_entity_types:
            placeholders = ",".join("?" for _ in allowed_entity_types)
            query += f" AND entity_type IN ({placeholders})"
            params.extend(sorted(allowed_entity_types))
        query += " ORDER BY priority ASC, rule_id ASC"

        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            RegexRule(
                entity_type=row[0],
                pattern_text=row[1],
                normalizer_name=row[2],
                validator_name=row[3],
                confidence=row[4],
                context_required=bool(row[5]),
            )
            for row in rows
        ]

    def list_rules(self) -> list[dict]:
        self.bootstrap()
        query = """
            SELECT
                rule_id,
                entity_type,
                pattern_text,
                normalizer_name,
                validator_name,
                confidence,
                context_required,
                priority,
                enabled,
                description
            FROM regex_rules
            ORDER BY priority ASC, rule_id ASC
        """
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(query).fetchall()
        return [
            {
                "rule_id": row[0],
                "entity_type": row[1],
                "pattern_text": row[2],
                "normalizer_name": row[3],
                "validator_name": row[4],
                "confidence": row[5],
                "context_required": bool(row[6]),
                "priority": row[7],
                "enabled": bool(row[8]),
                "description": row[9],
            }
            for row in rows
        ]

    def add_rule(
        self,
        *,
        entity_type: str,
        pattern_text: str,
        normalizer_name: str,
        validator_name: str,
        confidence: float,
        context_required: bool,
        priority: int,
        description: str,
    ) -> int:
        self.bootstrap()
        self._validate_entity_type_exists(entity_type)
        self._validate_rule_inputs(
            normalizer_name=normalizer_name,
            validator_name=validator_name,
            confidence=confidence,
        )
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO regex_rules(
                    entity_type,
                    pattern_text,
                    normalizer_name,
                    validator_name,
                    confidence,
                    context_required,
                    priority,
                    enabled,
                    description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    entity_type,
                    pattern_text,
                    normalizer_name,
                    validator_name,
                    confidence,
                    int(context_required),
                    priority,
                    description,
                ),
            )
            connection.commit()
            lastrowid = cursor.lastrowid
            if lastrowid is None:
                raise RuntimeError("Failed to retrieve lastrowid after INSERT.")
            return int(lastrowid)

    def list_entity_types(self) -> list[dict]:
        return self._list_entity_types()

    def add_entity_type(self, entity_type: str, description: str) -> bool:
        self.bootstrap()
        normalized = entity_type.strip().upper()
        if not normalized:
            raise InvalidRegexCatalogError("Entity type must not be empty.")
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO entity_types(entity_type, description)
                VALUES (?, ?)
                """,
                (normalized, description.strip()),
            )
            connection.commit()
            return cursor.rowcount > 0

    def disable_rule(self, rule_id: int) -> bool:
        self.bootstrap()
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute(
                "UPDATE regex_rules SET enabled = 0 WHERE rule_id = ?",
                (rule_id,),
            )
            connection.commit()
            return cursor.rowcount > 0

    def export_rules(self, output_path: str) -> Path:
        import json

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "entity_types": self._list_entity_types(),
            "rules": self.list_rules(),
        }
        output.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return output

    def import_rules(self, input_path: str, *, replace: bool = False) -> int:
        import json

        self.bootstrap()
        payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
        imported = 0
        with sqlite3.connect(self.db_path) as connection:
            if replace:
                connection.execute("DELETE FROM regex_rules")
                connection.execute("DELETE FROM entity_types")
            for entity in payload.get("entity_types", []):
                connection.execute(
                    """
                    INSERT OR IGNORE INTO entity_types(entity_type, description)
                    VALUES (?, ?)
                    """,
                    (entity["entity_type"], entity["description"]),
                )
            for rule in payload.get("rules", []):
                self._validate_entity_type_exists(rule["entity_type"], connection=connection)
                self._validate_rule_inputs(
                    normalizer_name=rule["normalizer_name"],
                    validator_name=rule["validator_name"],
                    confidence=rule["confidence"],
                )
                connection.execute(
                    """
                    INSERT INTO regex_rules(
                        entity_type,
                        pattern_text,
                        normalizer_name,
                        validator_name,
                        confidence,
                        context_required,
                        priority,
                        enabled,
                        description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rule["entity_type"],
                        rule["pattern_text"],
                        rule["normalizer_name"],
                        rule["validator_name"],
                        rule["confidence"],
                        int(rule["context_required"]),
                        rule["priority"],
                        int(rule["enabled"]),
                        rule["description"],
                    ),
                )
                imported += 1
            connection.commit()
        return imported

    def _list_entity_types(self) -> list[dict]:
        self.bootstrap()
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT entity_type, description FROM entity_types ORDER BY entity_type ASC"
            ).fetchall()
        return [{"entity_type": row[0], "description": row[1]} for row in rows]

    def _validate_entity_type_exists(
        self,
        entity_type: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        owns_connection = connection is None
        conn = connection or sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM entity_types WHERE entity_type = ?",
                (entity_type.strip().upper(),),
            ).fetchone()
            if row is None:
                raise InvalidRegexCatalogError(f"Unknown entity type: {entity_type}")
        finally:
            if owns_connection:
                conn.close()

    @staticmethod
    def _validate_rule_inputs(
        *,
        normalizer_name: str,
        validator_name: str,
        confidence: float,
    ) -> None:
        if normalizer_name not in NORMALIZERS:
            raise InvalidRegexCatalogError(f"Unknown normalizer: {normalizer_name}")
        if validator_name not in VALIDATORS:
            raise InvalidRegexCatalogError(f"Unknown validator: {validator_name}")
        if not 0.0 <= confidence <= 1.0:
            raise InvalidRegexCatalogError("Confidence must be between 0.0 and 1.0.")
