from unittest.mock import MagicMock

from app.idp.document_classifier import ClassificationResult
from app.idp.document_router import RoutingResult, route_document


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


# --- quality gate must win regardless of genre (regression) ---

def test_needs_remediation_is_held_even_if_genre_looks_like_drug_leaflet():
    elements = [make_title("Dosage"), make_narrative("500mg")]
    classification = ClassificationResult(quality="needs_remediation", genre="drug_leaflet")

    result = route_document(classification=classification, elements=elements)

    assert result == RoutingResult(status="held_for_remediation", chunks=None)


def test_needs_remediation_is_held_even_if_genre_looks_like_lab_report():
    elements = [make_narrative("garbled")]
    classification = ClassificationResult(quality="needs_remediation", genre="lab_report")

    result = route_document(classification=classification, elements=elements)

    assert result == RoutingResult(status="held_for_remediation", chunks=None)


def test_needs_remediation_never_calls_chunk_by_sections():
    elements = [make_title("Dosage"), make_narrative("500mg")]
    classification = ClassificationResult(quality="needs_remediation", genre="drug_leaflet")

    result = route_document(classification=classification, elements=elements)

    assert result.chunks is None


# --- clean + chunkable genres -> actually chunked ---

def test_clean_drug_leaflet_is_chunked():
    elements = [make_title("Dosage"), make_narrative("500mg twice daily")]
    classification = ClassificationResult(quality="clean", genre="drug_leaflet")

    result = route_document(classification=classification, elements=elements)

    assert result.status == "chunked"
    assert len(result.chunks) == 1
    assert result.chunks[0].section_title == "Dosage"
    assert "500mg twice daily" in result.chunks[0].content


def test_clean_clinical_protocol_is_chunked():
    elements = [make_title("Diagnosis Criteria"), make_narrative("Fasting glucose above threshold.")]
    classification = ClassificationResult(quality="clean", genre="clinical_protocol")

    result = route_document(classification=classification, elements=elements)

    assert result.status == "chunked"
    assert len(result.chunks) == 1


# --- clean + no chunking strategy yet ---

def test_clean_lab_report_has_no_chunking_strategy():
    elements = [make_narrative("some table content")]
    classification = ClassificationResult(quality="clean", genre="lab_report")

    result = route_document(classification=classification, elements=elements)

    assert result == RoutingResult(status="no_chunking_strategy", chunks=None)


def test_clean_unclassified_has_no_chunking_strategy():
    elements = [make_narrative("ambiguous content")]
    classification = ClassificationResult(quality="clean", genre="unclassified")

    result = route_document(classification=classification, elements=elements)

    assert result == RoutingResult(status="no_chunking_strategy", chunks=None)
