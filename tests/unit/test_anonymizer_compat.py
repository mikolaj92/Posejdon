from posejdon import ProcessingMode, ReplacementKind, TextAnonymizer


def test_text_anonymizer_compatibility_anonymizes_pii() -> None:
    anonymizer = TextAnonymizer()
    text = "Jan Kowalski ma PESEL 44051401359 oraz NIP 8567346215"
    result = anonymizer.anonymize(text)

    assert "Jan Kowalski" not in result.text
    assert "44051401359" not in result.text
    assert "8567346215" not in result.text

    # The default EXTERNAL_IRREVERSIBLE policy uses a CATEGORY_PLACEHOLDER style,
    # so the compatibility anonymizer emits labeled placeholders (an irreversible
    # run simply keeps no restore mapping). A fixed "****" mask is only produced
    # by an explicit MASK style.
    assert "[OSOBA_1]" in result.text
    assert "[PESEL_1]" in result.text
    assert "[NIP_1]" in result.text
    assert "****" not in result.text

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


def test_text_anonymizer_category_style_keeps_labels_without_reversible_mode() -> None:
    anonymizer = TextAnonymizer(replacement_style=ReplacementKind.CATEGORY_PLACEHOLDER)
    text = "Jan Kowalski ma PESEL 44051401359 oraz NIP 8567346215"
    result = anonymizer.anonymize(text)

    assert "[OSOBA_1]" in result.text
    assert "[PESEL_1]" in result.text
    assert "[NIP_1]" in result.text
    assert "****" not in result.text


def test_text_anonymizer_per_call_style_overrides_default() -> None:
    anonymizer = TextAnonymizer(replacement_style=ReplacementKind.CATEGORY_PLACEHOLDER)
    text = "Jan Kowalski ma PESEL 44051401359 oraz NIP 8567346215"

    masked = anonymizer.anonymize(text, replacement_style=ReplacementKind.MASK)

    assert "[OSOBA_1]" not in masked.text
    assert masked.text.count("****") == 3


def test_text_anonymizer_segments_honor_category_style() -> None:
    anonymizer = TextAnonymizer(replacement_style=ReplacementKind.CATEGORY_PLACEHOLDER)
    result = anonymizer.anonymize_segments(
        [
            "Jan Kowalski podpisał umowę.",
            "PESEL 44051401359 widnieje w aktach.",
        ]
    )

    joined = "".join(result.texts)
    assert "[OSOBA_1]" in joined
    assert "[PESEL_1]" in joined
    assert "****" not in joined


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


def test_text_anonymizer_remembers_ec_surname_genitive_mentions() -> None:
    result = TextAnonymizer().anonymize(
        "Piotr Malec podpisał umowę. W notatce wskazano pana Malca."
    )

    assert "Piotr Malec" not in result.text
    assert "Malca" not in result.text
    assert result.findings["PERSON"] >= 2


def test_text_anonymizer_reuses_person_token_for_close_first_name_typo() -> None:
    anonymizer = TextAnonymizer()
    text = "Patryka Kowalskiego wskazano w umowie. Patyrk Kowalski podpisał aneks."

    result = anonymizer.anonymize(text)

    assert "Patryka Kowalskiego" not in result.text
    assert "Patyrk Kowalski" not in result.text
    assert result.text.count("[OSOBA_1]") == 2
    assert "[OSOBA_2]" not in result.text


def test_text_anonymizer_does_not_merge_distinct_close_surnames() -> None:
    anonymizer = TextAnonymizer()
    text = "Jan Mikołajczyk podpisał umowę. Jan Mikołajczak podpisał aneks."

    result = anonymizer.anonymize(text)

    assert "Mikołajczyk" not in result.text
    assert "Mikołajczak" not in result.text
    assert "[OSOBA_1]" in result.text
    assert "[OSOBA_2]" in result.text


def test_text_anonymizer_does_not_merge_gendered_surname_forms_as_one_person() -> None:
    anonymizer = TextAnonymizer()
    text = "Jan Majewski podpisał umowę. Anna Majewska podpisała aneks."

    result = anonymizer.anonymize(text)

    assert "Jan Majewski" not in result.text
    assert "Anna Majewska" not in result.text
    assert "[OSOBA_1]" in result.text
    assert "[OSOBA_2]" in result.text


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
