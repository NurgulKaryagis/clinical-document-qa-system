from unittest.mock import MagicMock, patch

from app.config import settings
from app.idp.document_classifier import (
    ClassificationResult,
    GenreClassification,
    classify_document,
    classify_genre,
    classify_genre_llm,
    classify_quality,
)


def make_element(type_name: str, text: str):
    from unstructured.documents import elements as el_module
    cls = getattr(el_module, type_name)
    mock = MagicMock(spec=cls)
    mock.text = text
    return mock


def make_title(text: str):
    return make_element("Title", text)


def make_narrative(text: str):
    return make_element("NarrativeText", text)


def make_table(text: str):
    return make_element("Table", text)


# --- classify_quality ---

def test_quality_is_clean_when_titles_present():
    elements = [make_title("Dosage"), make_narrative("500mg")]

    assert classify_quality(elements) == "clean"


def test_quality_is_needs_remediation_when_no_titles():
    elements = [make_narrative("Some text with no headings.")]

    assert classify_quality(elements) == "needs_remediation"


def test_quality_needs_remediation_on_empty_document():
    assert classify_quality([]) == "needs_remediation"


# --- classify_genre: table-dominated -> lab_report ---

def test_genre_is_lab_report_when_tables_dominate():
    elements = [make_table("T1"), make_table("T2"), make_table("T3"), make_narrative("N1")]

    assert classify_genre(elements) == "lab_report"


def test_genre_is_not_lab_report_on_tie():
    # table_count == narrative_count should not count as "dominated by tables"
    elements = [make_table("T1"), make_narrative("N1")]

    assert classify_genre(elements) != "lab_report"


# --- classify_genre: keyword matching ---

def test_genre_is_drug_leaflet_for_dosage_title():
    elements = [make_title("Dosage"), make_narrative("500mg twice daily")]

    assert classify_genre(elements) == "drug_leaflet"


def test_genre_is_drug_leaflet_for_contraindications_title():
    elements = [make_title("Contraindications")]

    assert classify_genre(elements) == "drug_leaflet"


def test_genre_is_clinical_protocol_for_diagnosis_title():
    elements = [make_title("Diagnosis Criteria")]

    assert classify_genre(elements) == "clinical_protocol"


def test_genre_is_clinical_protocol_for_treatment_title():
    elements = [make_title("Treatment Steps")]

    assert classify_genre(elements) == "clinical_protocol"


def test_genre_keyword_match_is_case_insensitive():
    elements = [make_title("DOSAGE")]

    assert classify_genre(elements) == "drug_leaflet"


def test_genre_is_unclassified_when_no_signal_matches():
    elements = [make_title("Overview"), make_narrative("General information.")]

    assert classify_genre(elements) == "unclassified"


# --- classify_genre: must not stop at the first non-matching title (regression) ---

def test_genre_checks_all_titles_not_just_the_first():
    elements = [make_title("Overview"), make_title("Dosage")]

    assert classify_genre(elements) == "drug_leaflet"


# --- classify_document ---

def test_classify_document_combines_quality_and_genre():
    elements = [make_title("Dosage"), make_narrative("500mg")]

    result = classify_document(elements)

    assert result == ClassificationResult(quality="clean", genre="drug_leaflet")


def test_classify_document_flags_needs_remediation_and_unclassified_together():
    elements = [make_narrative("Garbled text with no structure.")]

    with patch("app.idp.document_classifier.ChatOpenAI") as mock_chat:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = GenreClassification(genre="unclassified")
        mock_chat.return_value.with_structured_output.return_value = mock_chain

        result = classify_document(elements)

    assert result == ClassificationResult(quality="needs_remediation", genre="unclassified")


# --- classify_genre_llm ---

def test_classify_genre_llm_uses_configured_model():
    elements = [make_title("Dosage")]

    with patch("app.idp.document_classifier.ChatOpenAI") as mock_chat:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = GenreClassification(genre="drug_leaflet")
        mock_chat.return_value.with_structured_output.return_value = mock_chain

        classify_genre_llm(elements)

    call_kwargs = mock_chat.call_args.kwargs
    assert call_kwargs["model"] == settings.idp_classifier_model


def test_classify_genre_llm_includes_title_text_in_prompt():
    elements = [make_title("Dosage"), make_narrative("This text should not decide the prompt.")]

    with patch("app.idp.document_classifier.ChatOpenAI") as mock_chat:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = GenreClassification(genre="drug_leaflet")
        mock_chat.return_value.with_structured_output.return_value = mock_chain

        classify_genre_llm(elements)

    prompt = mock_chain.invoke.call_args.args[0]
    assert "Dosage" in prompt


def test_classify_genre_llm_returns_structured_output_result():
    elements = [make_title("Dosage")]

    with patch("app.idp.document_classifier.ChatOpenAI") as mock_chat:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = GenreClassification(genre="lab_report")
        mock_chat.return_value.with_structured_output.return_value = mock_chain

        result = classify_genre_llm(elements)

    assert result == GenreClassification(genre="lab_report")


# --- classify_document: LLM fallback wiring ---

def test_classify_document_does_not_call_llm_when_heuristic_is_confident():
    elements = [make_title("Dosage"), make_narrative("500mg")]

    with patch("app.idp.document_classifier.ChatOpenAI") as mock_chat:
        classify_document(elements)

    mock_chat.assert_not_called()


def test_classify_document_falls_back_to_llm_when_heuristic_is_unclassified():
    elements = [make_title("Overview")]

    with patch("app.idp.document_classifier.ChatOpenAI") as mock_chat:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = GenreClassification(genre="clinical_protocol")
        mock_chat.return_value.with_structured_output.return_value = mock_chain

        result = classify_document(elements)

    assert result.genre == "clinical_protocol"


def test_classify_document_genre_is_plain_string_after_llm_fallback():
    elements = [make_title("Overview")]

    with patch("app.idp.document_classifier.ChatOpenAI") as mock_chat:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = GenreClassification(genre="drug_leaflet")
        mock_chat.return_value.with_structured_output.return_value = mock_chain

        result = classify_document(elements)

    assert isinstance(result.genre, str)
