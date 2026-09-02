import pytest

from posejdon import ProcessingMode, TextAnonymizer
from posejdon.core.enums import DocumentKind, PolicyProfileName
from posejdon.detectors.fusion import DetectorFusion
from posejdon.detectors.gliner_detector import _DEFAULT_LABELS, GLiNERDetector
from posejdon.detectors.mention_memory import expand_person_mentions
from posejdon.detectors.regex_detector import RegexDetector
from posejdon.domain.entities import SensitiveEntity
from posejdon.domain.policies import DEFAULT_POLICY_PROFILES
from posejdon.planners.replacement_planner import ReplacementPlanner


class _FakeModel:
    """Stand-in for a loaded GLiNER model so tests stay offline and fast."""

    def __init__(self, predictions):
        self._predictions = predictions
        self.calls: list[list[str]] = []

    def predict_entities(self, text, labels):
        self.calls.append(labels)
        return self._predictions


def _detector_with(model, *, threshold=0.45) -> GLiNERDetector:
    detector = GLiNERDetector.__new__(GLiNERDetector)
    detector.name = "gliner"
    detector.model_name = "fake"
    detector.local_files_only = True
    detector.threshold = threshold
    detector._model = model
    return detector


def test_detect_prompts_default_labels_when_caller_gives_none():
    model = _FakeModel([])
    detector = _detector_with(model)

    detector.detect("Kwiaciarnia Różyczka w Krakowie")

    assert model.calls == [list(_DEFAULT_LABELS)]


def test_detect_maps_gliner_label_to_canonical_entity_type():
    model = _FakeModel(
        [
            {
                "text": "Kwiaciarnia Różyczka",
                "label": "organization",
                "start": 0,
                "end": 20,
                "score": 0.9,
            },
            {"text": "Krakowie", "label": "location", "start": 24, "end": 32, "score": 0.9},
        ]
    )
    detector = _detector_with(model)

    entities = detector.detect("Kwiaciarnia Różyczka w Krakowie")

    assert [e.entity_type for e in entities] == ["ORG", "CITY"]


def test_detect_propagates_model_failure():
    class _FailingModel:
        def predict_entities(self, text, labels):
            raise RuntimeError("inference failed")

    detector = _detector_with(_FailingModel())

    with pytest.raises(RuntimeError, match="inference failed"):
        detector.detect("Anna")


def test_detect_drops_predictions_below_threshold():
    model = _FakeModel([{"text": "Anna", "label": "person", "start": 0, "end": 4, "score": 0.3}])
    detector = _detector_with(model, threshold=0.45)

    assert detector.detect("Anna") == []


_EMPLOYMENT_TEXT = (
    "Pracownik wykonuje obowiązki określone w umowie o pracę. "
    "Jan Kowalski podpisał umowę w imieniu Pracownika. "
    "Administratora danych informuje się o zakresie przetwarzania."
)
_CONTRACT_ROLE_TEXT = (
    "Wykonawca świadczy usługi na rzecz Zamawiającego. "
    "Strony zawierają Umowy w zakresie Zamówienia. "
    "Poufne informacje pozostają u Jan Kowalski."
)
_CONTRACT_ROLE_SURFACES = (
    "Wykonawca",
    "Zamawiającego",
    "Strony",
    "Umowy",
    "Zamówienia",
    "Poufne",
)
# Runtime evidence from Posejdon v0.1.2: solitary GLiNER person at 0.672.
_GLINER_ROLE_SCORE = 0.6721977591514587
_GLINER_NAME_SCORE = 0.969257
_GLINER_ROLE_GENITIVE_SCORE = 0.791867


def _employment_gliner_predictions() -> list[dict]:
    pracownik = _EMPLOYMENT_TEXT.index("Pracownik")
    jan = _EMPLOYMENT_TEXT.index("Jan Kowalski")
    pracownika = _EMPLOYMENT_TEXT.index("Pracownika")
    administratora = _EMPLOYMENT_TEXT.index("Administratora")
    return [
        {
            "text": "Pracownik",
            "label": "person",
            "start": pracownik,
            "end": pracownik + len("Pracownik"),
            "score": _GLINER_ROLE_SCORE,
        },
        {
            "text": "Jan Kowalski",
            "label": "person",
            "start": jan,
            "end": jan + len("Jan Kowalski"),
            "score": _GLINER_NAME_SCORE,
        },
        {
            "text": "Pracownika",
            "label": "organization",
            "start": pracownika,
            "end": pracownika + len("Pracownika"),
            "score": _GLINER_ROLE_GENITIVE_SCORE,
        },
        {
            "text": "Administratora",
            "label": "person",
            "start": administratora,
            "end": administratora + len("Administratora"),
            "score": 0.62,
        },
    ]


def _production_path_entities(text: str, gliner: GLiNERDetector) -> list[SensitiveEntity]:
    candidates = RegexDetector().detect(text) + gliner.detect(text)
    return expand_person_mentions(text, DetectorFusion().merge(candidates))


def _replacement_plan(entities: list[SensitiveEntity]):
    policy = DEFAULT_POLICY_PROFILES[PolicyProfileName.EXTERNAL_IRREVERSIBLE]
    return ReplacementPlanner(policy=policy).plan(
        entities=entities,
        document_kind=DocumentKind.TEXT,
        processing_mode=ProcessingMode.REVERSIBLE,
    )


def test_gliner_does_not_emit_generic_polish_role_as_person():
    detector = _detector_with(_FakeModel(_employment_gliner_predictions()))

    entities = detector.detect(_EMPLOYMENT_TEXT)

    role_entities = [
        entity
        for entity in entities
        if entity.raw_text in {"Pracownik", "Pracownika", "Administratora"}
    ]
    name_entities = [entity for entity in entities if entity.raw_text == "Jan Kowalski"]
    assert role_entities == []
    assert [entity.entity_type for entity in name_entities] == ["PERSON"]


def test_fusion_and_planner_drop_solitary_gliner_role_before_replacement():
    gliner = _detector_with(_FakeModel(_employment_gliner_predictions()))
    fused = _production_path_entities(_EMPLOYMENT_TEXT, gliner)
    plan = _replacement_plan(fused)

    fused_surfaces = {entity.raw_text for entity in fused}
    replaced = {replacement.source_text for replacement in plan.replacements}
    assert "Pracownik" not in fused_surfaces
    assert "Pracownika" not in fused_surfaces
    assert "Administratora" not in fused_surfaces
    assert "Jan Kowalski" in fused_surfaces
    assert "Pracownik" not in replaced
    assert "Pracownika" not in replaced
    assert "Administratora" not in replaced
    assert "Jan Kowalski" in replaced
    assert all(
        replacement.replacement_text.startswith("[OSOBA_")
        for replacement in plan.replacements
        if replacement.source_text == "Jan Kowalski"
    )


def test_anonymizer_preserves_generic_role_while_replacing_named_person(monkeypatch):
    gliner = _detector_with(_FakeModel(_employment_gliner_predictions()))
    monkeypatch.setattr(
        "posejdon.anonymizer.GLiNERDetector._load_model",
        lambda *args, **kwargs: gliner._model,
    )
    anonymizer = TextAnonymizer(
        gliner_enabled=True,
        processing_mode=ProcessingMode.REVERSIBLE,
    )
    anonymizer.detectors = [RegexDetector(), gliner]

    result = anonymizer.anonymize(_EMPLOYMENT_TEXT)

    assert "Pracownik" in result.text
    assert "Pracownika" in result.text
    assert "Administratora" in result.text
    assert "Jan Kowalski" not in result.text
    assert "[OSOBA_" in result.text
    assert result.findings.get("PERSON", 0) == 1
    assert "ORG" not in result.findings


def _contract_gliner_predictions() -> list[dict]:
    predictions = []
    for surface in _CONTRACT_ROLE_SURFACES:
        start = _CONTRACT_ROLE_TEXT.index(surface)
        predictions.append(
            {
                "text": surface,
                "label": "person" if surface != "Zamawiającego" else "organization",
                "start": start,
                "end": start + len(surface),
                "score": _GLINER_ROLE_GENITIVE_SCORE,
            }
        )
    jan = _CONTRACT_ROLE_TEXT.index("Jan Kowalski")
    predictions.append(
        {
            "text": "Jan Kowalski",
            "label": "person",
            "start": jan,
            "end": jan + len("Jan Kowalski"),
            "score": _GLINER_NAME_SCORE,
        }
    )
    return predictions


def test_gliner_does_not_emit_inflected_contract_role_nouns():
    detector = _detector_with(_FakeModel(_contract_gliner_predictions()))

    entities = detector.detect(_CONTRACT_ROLE_TEXT)

    role_entities = [entity for entity in entities if entity.raw_text in _CONTRACT_ROLE_SURFACES]
    name_entities = [entity for entity in entities if entity.raw_text == "Jan Kowalski"]
    assert role_entities == []
    assert [entity.entity_type for entity in name_entities] == ["PERSON"]


def test_fusion_and_planner_drop_inflected_contract_role_before_replacement():
    gliner = _detector_with(_FakeModel(_contract_gliner_predictions()))
    fused = _production_path_entities(_CONTRACT_ROLE_TEXT, gliner)
    plan = _replacement_plan(fused)

    fused_surfaces = {entity.raw_text for entity in fused}
    replaced = {replacement.source_text for replacement in plan.replacements}
    assert fused_surfaces.isdisjoint(_CONTRACT_ROLE_SURFACES)
    assert "Jan Kowalski" in fused_surfaces
    assert replaced.isdisjoint(_CONTRACT_ROLE_SURFACES)
    assert "Jan Kowalski" in replaced


def test_gliner_does_not_emit_exact_osoba_role_inflections_as_person():
    role_surfaces = (
        "Osoba",
        "Osoby",
        "Osobie",
        "Osobę",
        "Osobą",
        "Osobami",
        "Osobom",
        "Osobach",
        "Osób",
    )
    text = " ".join((*role_surfaces, "Osowski"))
    predictions = [
        {
            "text": surface,
            "label": "person",
            "start": text.index(surface),
            "end": text.index(surface) + len(surface),
            "score": 0.81,
        }
        for surface in (*role_surfaces, "Osowski")
    ]

    entities = _detector_with(_FakeModel(predictions)).detect(text)

    assert [entity.raw_text for entity in entities] == ["Osowski"]


def test_gliner_drops_false_nip_without_checksum():
    text = "Nr NIP: 1234563218."
    nr_start = text.index("Nr")
    nip_start = text.index("1234563218")
    detector = _detector_with(
        _FakeModel(
            [
                {
                    "text": "Nr",
                    "label": "NIP",
                    "start": nr_start,
                    "end": nr_start + len("Nr"),
                    "score": 0.72,
                },
                {
                    "text": "1234563218",
                    "label": "NIP",
                    "start": nip_start,
                    "end": nip_start + len("1234563218"),
                    "score": 0.91,
                },
            ]
        )
    )

    entities = detector.detect(text, labels=["NIP"])

    assert [entity.raw_text for entity in entities] == ["1234563218"]
    assert [entity.entity_type for entity in entities] == ["NIP"]


def test_gliner_drops_inflected_payment_and_order_nouns():
    text = "Zapłaty wynikają ze Zlecenia. „Umowy” potwierdza Jan Kowalski."
    detector = _detector_with(
        _FakeModel(
            [
                {
                    "text": "Zapłaty",
                    "label": "person",
                    "start": text.index("Zapłaty"),
                    "end": text.index("Zapłaty") + len("Zapłaty"),
                    "score": 0.75,
                },
                {
                    "text": "Zlecenia",
                    "label": "organization",
                    "start": text.index("Zlecenia"),
                    "end": text.index("Zlecenia") + len("Zlecenia"),
                    "score": 0.75,
                },
                {
                    "text": "„Umowy”",
                    "label": "organization",
                    "start": text.index("„Umowy”"),
                    "end": text.index("„Umowy”") + len("„Umowy”"),
                    "score": 0.75,
                },
                {
                    "text": "Jan Kowalski",
                    "label": "person",
                    "start": text.index("Jan Kowalski"),
                    "end": text.index("Jan Kowalski") + len("Jan Kowalski"),
                    "score": 0.96,
                },
            ]
        )
    )

    entities = detector.detect(text)

    assert [entity.raw_text for entity in entities] == ["Jan Kowalski"]


def test_gliner_does_not_suppress_surname_sharing_umowa_prefix():

    # Stem "umow" would swallow "Umowski"; keep contract-document matching exact.
    text = "Umowski potwierdził odbiór."
    start = text.index("Umowski")
    detector = _detector_with(
        _FakeModel(
            [
                {
                    "text": "Umowski",
                    "label": "person",
                    "start": start,
                    "end": start + len("Umowski"),
                    "score": 0.88,
                }
            ]
        )
    )

    entities = detector.detect(text)

    assert [entity.raw_text for entity in entities] == ["Umowski"]


def test_gliner_does_not_suppress_capitalized_single_token_polish_names():
    text = "Anna podpisała umowę. Nowak potwierdził odbiór."
    anna_start = text.index("Anna")
    nowak_start = text.index("Nowak")
    detector = _detector_with(
        _FakeModel(
            [
                {
                    "text": "Anna",
                    "label": "person",
                    "start": anna_start,
                    "end": anna_start + len("Anna"),
                    "score": 0.91,
                },
                {
                    "text": "Nowak",
                    "label": "person",
                    "start": nowak_start,
                    "end": nowak_start + len("Nowak"),
                    "score": 0.88,
                },
            ]
        )
    )

    entities = detector.detect(text)

    assert [entity.raw_text for entity in entities] == ["Anna", "Nowak"]
    assert {entity.entity_type for entity in entities} == {"PERSON"}


def test_live_gliner_model_still_scores_pracownik_above_threshold_then_drops_it():
    detector = GLiNERDetector()
    if not detector.available:
        pytest.skip("GLiNER model is not available")

    raw_predictions = detector._model.predict_entities(
        _EMPLOYMENT_TEXT,
        labels=list(_DEFAULT_LABELS),
    )
    pracownik = next(
        item
        for item in raw_predictions
        if item["text"] == "Pracownik" and str(item["label"]).casefold() == "person"
    )
    assert float(pracownik["score"]) >= detector.threshold

    fused = _production_path_entities(_EMPLOYMENT_TEXT, detector)
    plan = _replacement_plan(fused)
    replaced = {replacement.source_text for replacement in plan.replacements}
    assert "Pracownik" not in {entity.raw_text for entity in fused}
    assert "Jan Kowalski" in {entity.raw_text for entity in fused}
    assert "Pracownik" not in replaced
    assert "Jan Kowalski" in replaced


def test_gliner_does_not_emit_related_party_legal_phrase_as_person():
    text = "Podmiot Powiązany przekazuje dane. Jan Kowalski podpisuje."
    start = text.index("Podmiot Powiązany")
    jan = text.index("Jan Kowalski")
    detector = _detector_with(
        _FakeModel(
            [
                {
                    "text": "Podmiot Powiązany",
                    "label": "person",
                    "start": start,
                    "end": start + len("Podmiot Powiązany"),
                    "score": 0.81,
                },
                {
                    "text": "Jan Kowalski",
                    "label": "person",
                    "start": jan,
                    "end": jan + len("Jan Kowalski"),
                    "score": 0.96,
                },
            ]
        )
    )

    entities = detector.detect(text)

    assert [entity.raw_text for entity in entities] == ["Jan Kowalski"]


def test_mention_memory_expands_unique_title_case_single_token_person():
    text = "Axos podpisuje. Druga strona to Axos i RODO."
    start = text.index("Axos")
    entities = [
        SensitiveEntity(
            entity_id="person-1",
            entity_type="PERSON",
            raw_text="Axos",
            normalized_text="Axos",
            confidence=0.75,
            source_detector="spacy",
            start_offset=start,
            end_offset=start + 4,
        )
    ]

    expanded = expand_person_mentions(text, entities)
    derived = [entity for entity in expanded if entity.source_detector == "mention_memory"]

    assert [entity.raw_text for entity in derived] == ["Axos"]
    assert derived[0].start_offset == text.index("Axos", start + 4)
    assert derived[0].mention_provenance().mention_rule == "person_exact_repeat"
    assert "RODO" not in {entity.raw_text for entity in derived}


def test_mention_memory_does_not_expand_first_name_form_as_single_token_person():
    text = "Anna podpisuje. Druga strona to Anna."
    start = text.index("Anna")
    entities = [
        SensitiveEntity(
            entity_id="person-1",
            entity_type="PERSON",
            raw_text="Anna",
            normalized_text="Anna",
            confidence=0.91,
            source_detector="spacy",
            start_offset=start,
            end_offset=start + 4,
        )
    ]

    expanded = expand_person_mentions(text, entities)

    assert [entity for entity in expanded if entity.source_detector == "mention_memory"] == []


def test_mention_memory_does_not_expand_related_party_legal_phrase():
    text = "Podmiot Powiązany przekazuje dane. Drugi Podmiot Powiązany."
    start = text.index("Podmiot Powiązany")
    entities = [
        SensitiveEntity(
            entity_id="person-1",
            entity_type="PERSON",
            raw_text="Podmiot Powiązany",
            normalized_text="Podmiot Powiązany",
            confidence=0.81,
            source_detector="spacy",
            start_offset=start,
            end_offset=start + len("Podmiot Powiązany"),
        )
    ]

    expanded = expand_person_mentions(text, entities)

    assert [entity for entity in expanded if entity.source_detector == "mention_memory"] == []
    assert [entity.raw_text for entity in expanded] == ["Podmiot Powiązany"]
