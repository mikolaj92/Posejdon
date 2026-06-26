from __future__ import annotations

import hashlib

from posejdon.domain.entities import SensitiveEntity


class SpacyDetector:
    name = "spacy"
    _GENERIC_SINGLE_TOKEN_ENTITIES = {
        "page",
        "strona",
    }

    def __init__(self, model_name: str = "pl_core_news_sm") -> None:
        self.model_name = model_name
        self._nlp = None
        try:
            import spacy

            self._nlp = spacy.load(model_name)
        except Exception:
            self._nlp = None

    @property
    def available(self) -> bool:
        return self._nlp is not None

    def detect(self, text: str) -> list[SensitiveEntity]:
        if self._nlp is None:
            return []
        try:
            doc = self._nlp(text)
        except Exception:
            return []

        entities: list[SensitiveEntity] = []
        for ent in doc.ents:
            normalized = ent.text.strip()
            if not normalized or not any(char.isalnum() for char in normalized):
                continue
            if self._is_generic_single_token_entity(normalized):
                continue
            digest = hashlib.sha1(
                f"spacy|{ent.label_}|{ent.start_char}|{ent.end_char}|{ent.text}".encode(),
                usedforsecurity=False,
            ).hexdigest()[:12]
            entities.append(
                SensitiveEntity(
                    entity_id=f"ENT_{digest}",
                    entity_type=ent.label_.upper(),
                    raw_text=ent.text,
                    normalized_text=normalized,
                    confidence=0.75,
                    source_detector=self.name,
                    start_offset=ent.start_char,
                    end_offset=ent.end_char,
                    metadata={"model_name": self.model_name},
                )
            )
        return entities

    @classmethod
    def _is_generic_single_token_entity(cls, text: str) -> bool:
        normalized = text.casefold().strip()
        return normalized in cls._GENERIC_SINGLE_TOKEN_ENTITIES and len(normalized.split()) == 1
