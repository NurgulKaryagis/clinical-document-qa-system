from unittest.mock import MagicMock
from app.chunking.section_chunker import chunk_by_sections, SectionChunk


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


# --- Scenario 1: Normal PDF with titles ---

def test_two_sections_correct_content():
    elements = [
        make_title("Dosage"),
        make_narrative("500mg"),
        make_narrative("twice daily"),
        make_title("Side Effects"),
        make_narrative("Nausea"),
    ]
    chunks = chunk_by_sections(elements)

    assert len(chunks) == 2
    assert chunks[0].section_title == "Dosage"
    assert "500mg" in chunks[0].content
    assert "twice daily" in chunks[0].content
    assert chunks[1].section_title == "Side Effects"
    assert chunks[1].content == "Nausea"


def test_section_title_not_in_content():
    elements = [
        make_title("Contraindications"),
        make_narrative("Do not use in patients with renal failure."),
    ]
    chunks = chunk_by_sections(elements)

    assert "Contraindications" not in chunks[0].content
    assert chunks[0].section_title == "Contraindications"


def test_section_title_in_metadata():
    elements = [
        make_title("Indications"),
        make_narrative("Used in the treatment of type 2 diabetes."),
    ]
    chunks = chunk_by_sections(elements)

    assert chunks[0].metadata["section"] == "Indications"


# --- Scenario 2: No titles, fallback ---

def test_fallback_when_no_titles():
    elements = [
        make_narrative("First paragraph."),
        make_narrative("Second paragraph."),
    ]
    chunks = chunk_by_sections(elements)

    assert len(chunks) == 2
    assert all(c.metadata.get("fallback") is True for c in chunks)


def test_fallback_section_title_is_unknown():
    elements = [make_narrative("Some text.")]
    chunks = chunk_by_sections(elements)

    assert chunks[0].section_title == "Unknown Section"


# --- Scenario 3: Table gets its own chunk ---

def test_table_gets_own_chunk():
    elements = [
        make_title("Dosage Table"),
        make_narrative("See the table below."),
        make_table("Dose | Frequency\n500mg | 2x"),
    ]
    chunks = chunk_by_sections(elements)

    assert len(chunks) == 2
    table_chunk = next(c for c in chunks if c.metadata.get("element_type") == "table")
    assert "500mg" in table_chunk.content


def test_table_metadata_has_element_type():
    elements = [
        make_title("Pharmacokinetics"),
        make_table("T1/2 | 6 hours"),
    ]
    chunks = chunk_by_sections(elements)

    assert any(c.metadata.get("element_type") == "table" for c in chunks)


# --- Scenario 4: Empty text elements are ignored ---

def test_empty_text_elements_ignored():
    elements = [
        make_title("Dosage"),
        make_narrative("   "),
        make_narrative("500mg"),
    ]
    chunks = chunk_by_sections(elements)

    assert len(chunks) == 1
    assert chunks[0].content == "500mg"
