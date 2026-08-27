from __future__ import annotations

import hashlib

from posejdon.detectors.regex_support import PERSON_BLOCKED_TOKENS
from posejdon.domain.entities import SensitiveEntity

# GLiNER only extracts the entity kinds it is prompted with, so callers that hand
# it a bare string (no labels) get nothing back. These are the recall gaps the
# regex/gazetteer detectors leave -- free-form names, organizations and places --
# each mapped to the canonical Posejdon entity type the planner expects.
_DEFAULT_LABELS: dict[str, str] = {
    "person": "PERSON",
    "organization": "ORG",
    "location": "CITY",
    "address": "ADDRESS",
}
# Stems for inflected Polish employment-role nouns. Exact blocked tokens such as
# "Pracownik" are also rejected via PERSON_BLOCKED_TOKENS; the stems catch forms
# like "Pracownika" that GLiNER may emit under a non-PERSON label.
_GENERIC_ROLE_STEMS: frozenset[str] = frozenset(
    {
        "pracownik",
        "pracownic",
        "klient",
        "pełnomocnik",
        "pełnomocnic",
    }
)
_GENERIC_ROLE_INFLECTION_MAX_LEN = 4
_BLOCKED_ROLE_TOKENS: frozenset[str] = frozenset(
    token.casefold() for token in PERSON_BLOCKED_TOKENS
)


class GLiNERDetector:
    name = "gliner"

    def __init__(
        self,
        model_name: str = "urchade/gliner_small-v2.1",
        *,
        local_files_only: bool = True,
        threshold: float = 0.45,
    ) -> None:
        self.model_name = model_name
        self.local_files_only = local_files_only
        self.threshold = threshold
        self._model = self._load_model(model_name, local_files_only)

    @staticmethod
    def _load_model(model_name: str, local_files_only: bool):
        try:
            from gliner import GLiNER
        except Exception:
            return None
        try:
            return GLiNER.from_pretrained(model_name, local_files_only=local_files_only)
        except Exception:
            # The weights are just a public NER model, not user data: if they are
            # not cached yet, fetch them once rather than silently no-op.
            if not local_files_only:
                return None
            try:
                return GLiNER.from_pretrained(model_name, local_files_only=False)
            except Exception:
                return None

    @property
    def available(self) -> bool:
        return self._model is not None

    def detect(self, text: str, labels: list[str] | None = None) -> list[SensitiveEntity]:
        if self._model is None:
            return []
        prompt_labels = labels or list(_DEFAULT_LABELS)
        predictions = self._model.predict_entities(text, labels=prompt_labels)

        entities: list[SensitiveEntity] = []
        for item in predictions:
            raw = item["text"]
            start = int(item["start"])
            end = int(item["end"])
            score = float(item.get("score", 0.65))
            if score < self.threshold:
                continue
            label = str(item["label"])
            entity_type = _DEFAULT_LABELS.get(label, label.upper())
            if self._is_generic_role_surface(raw):
                continue
            digest = hashlib.sha1(
                f"gliner|{label}|{start}|{end}|{raw}".encode(),
                usedforsecurity=False,
            ).hexdigest()[:12]
            entities.append(
                SensitiveEntity(
                    entity_id=f"ENT_{digest}",
                    entity_type=entity_type,
                    raw_text=raw,
                    normalized_text=raw.strip(),
                    confidence=score,
                    source_detector=self.name,
                    start_offset=start,
                    end_offset=end,
                    metadata={"model_name": self.model_name},
                )
            )
        return entities

    @staticmethod
    def _is_generic_role_surface(raw: str) -> bool:
        surface = raw.strip()
        if not surface:
            return False
        tokens = surface.split()
        if len(tokens) != 1:
            return False
        folded = tokens[0].casefold()
        if folded in _BLOCKED_ROLE_TOKENS:
            return True
        extra = _GENERIC_ROLE_INFLECTION_MAX_LEN
        return any(
            folded.startswith(stem) and 0 <= len(folded) - len(stem) <= extra
            for stem in _GENERIC_ROLE_STEMS
        )
