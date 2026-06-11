from posejdon import ProcessingMode, TextAnonymizer


def test_text_anonymizer_compatibility_anonymizes_pii() -> None:
    anonymizer = TextAnonymizer()
    text = "Jan Kowalski ma PESEL 44051401359 oraz NIP 8567346215"
    result = anonymizer.anonymize(text)

    assert "Jan Kowalski" not in result.text
    assert "44051401359" not in result.text
    assert "8567346215" not in result.text

    assert result.text.count("****") == 3

    assert result.findings["PERSON"] == 1
    assert result.findings["PESEL"] == 1
    assert result.findings["NIP"] == 1


def test_text_anonymizer_reversible_mode_keeps_reinjectable_placeholders() -> None:
    anonymizer = TextAnonymizer(processing_mode=ProcessingMode.REVERSIBLE)
    text = "Jan Kowalski ma PESEL 44051401359 oraz NIP 8567346215"
    result = anonymizer.anonymize(text)

    assert "Jan Kowalski" not in result.text
    assert "44051401359" not in result.text
    assert "8567346215" not in result.text

    assert "[OSOBA_1]" in result.text
    assert "[PESEL_1]" in result.text
    assert "[NIP_1]" in result.text
    assert "****" not in result.text


def test_text_anonymizer_expands_unambiguous_person_mentions() -> None:
    anonymizer = TextAnonymizer()
    text = (
        "Piotr Malec podpisał umowę. "
        "W notatkach wskazano „Piotr”, „P. Malec”, konto piotr i telefon piotr. "
        "Przekazano też panu Malec."
    )
    result = anonymizer.anonymize(text)

    assert "Piotr Malec" not in result.text
    assert "„Piotr”" not in result.text
    assert "P. Malec" not in result.text
    assert "konto piotr" not in result.text
    assert "telefon piotr" not in result.text
    assert "panu Malec" not in result.text
    assert result.findings["PERSON"] >= 6


def test_text_anonymizer_does_not_expand_ambiguous_first_name_mentions() -> None:
    anonymizer = TextAnonymizer()
    text = (
        "Jan Kowalski podpisał umowę. Jan Nowak podpisał aneks. "
        "W notatkach wskazano „Jan”, konto jan i telefon jan."
    )
    result = anonymizer.anonymize(text)

    assert "Jan Kowalski" not in result.text
    assert "Jan Nowak" not in result.text
    assert "„Jan”" in result.text
    assert "konto jan" in result.text
    assert "telefon jan" in result.text


def test_text_anonymizer_anonymizes_segments_with_document_scope_mentions() -> None:
    anonymizer = TextAnonymizer()
    result = anonymizer.anonymize_segments(
        [
            "Piotr Malec podpisał umowę.",
            "W kolejnym segmencie wskazano „Piotr”, konto piotr i „P. Malec”.",
        ]
    )

    assert len(result.texts) == 2
    assert "Piotr Malec" not in result.texts[0]
    assert "„Piotr”" not in result.texts[1]
    assert "konto piotr" not in result.texts[1]
    assert "P. Malec" not in result.texts[1]
    assert result.findings["PERSON"] >= 4
