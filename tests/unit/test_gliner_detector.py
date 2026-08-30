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
    model = _FakeModel(
        [{"text": "Anna", "label": "person", "start": 0, "end": 4, "score": 0.3}]
    )
    detector = _detector_with(model, threshold=0.45)

    assert detector.detect("Anna") == []


_EMPLOYMENT_TEXT = (
    "Pracownik wykonuje obowiązki określone w umowie o pracę. "
    "Jan Kowalski podpisał umowę w imieniu Pracownika. "
    "Administratora danych informuje się o zakresie przetwarzania."
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
