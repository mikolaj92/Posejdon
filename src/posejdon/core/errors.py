class PosejdonError(Exception):
    """Base exception for the subsystem."""


class UnsupportedDocumentError(PosejdonError):
    """Raised when a document kind is not supported by a parser or renderer."""


class ValidationFailureError(PosejdonError):
    """Raised when output validation fails."""


class UnsafeProcessingError(PosejdonError):
    """Raised when the system determines that continuing would be unsafe."""


class InvalidRegexCatalogError(PosejdonError):
    """Raised when regex catalog operations receive invalid inputs."""


class RestorePreconditionError(PosejdonError):
    """Raised when an archive-restore request fails explicit vault-backed preconditions."""


class InjectorExportCompatibilityError(PosejdonError):
    """Raised when injector export metadata is missing or incompatible.

    This covers the bounded reinjection contract reader.
    """


class ReinjectionIntegrityError(PosejdonError):
    """Raised when reinjection materials fail the integrity contract.

    This includes vault, export, anonymized output, and edited input checks.
    """


class VaultIntegrityError(PosejdonError):
    """Raised when vault HMAC verification fails or the vault is tampered."""
