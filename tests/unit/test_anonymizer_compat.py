from posejdon import TextAnonymizer


def test_text_anonymizer_compatibility_anonymizes_pii() -> None:
    anonymizer = TextAnonymizer()
    text = "Jan Kowalski ma PESEL 44051401359 oraz NIP 8567346215"
    result = anonymizer.anonymize(text)

    assert "Jan Kowalski" not in result.text
    assert "44051401359" not in result.text
    assert "8567346215" not in result.text

    assert "[OSOBA" in result.text
    assert "[PESEL" in result.text
    assert "[NIP" in result.text

    assert result.findings["PERSON"] == 1
    assert result.findings["PESEL"] == 1
    assert result.findings["NIP"] == 1
