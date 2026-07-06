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


# --- Senaryo 1: Normal PDF, title'lar var ---

def test_two_sections_correct_content():
    elements = [
        make_title("Dozaj"),
        make_narrative("500mg"),
        make_narrative("günde 2 kez"),
        make_title("Yan Etkiler"),
        make_narrative("Bulantı"),
    ]
    chunks = chunk_by_sections(elements)

    assert len(chunks) == 2
    assert chunks[0].section_title == "Dozaj"
    assert "500mg" in chunks[0].content
    assert "günde 2 kez" in chunks[0].content
    assert chunks[1].section_title == "Yan Etkiler"
    assert chunks[1].content == "Bulantı"


def test_section_title_not_in_content():
    elements = [
        make_title("Kontrendikasyonlar"),
        make_narrative("Böbrek yetmezliğinde kullanılmaz."),
    ]
    chunks = chunk_by_sections(elements)

    assert "Kontrendikasyonlar" not in chunks[0].content
    assert chunks[0].section_title == "Kontrendikasyonlar"


def test_section_title_in_metadata():
    elements = [
        make_title("Endikasyonlar"),
        make_narrative("Tip 2 diyabet tedavisinde kullanılır."),
    ]
    chunks = chunk_by_sections(elements)

    assert chunks[0].metadata["section"] == "Endikasyonlar"


# --- Senaryo 2: Title yok, fallback ---

def test_fallback_when_no_titles():
    elements = [
        make_narrative("Birinci paragraf."),
        make_narrative("İkinci paragraf."),
    ]
    chunks = chunk_by_sections(elements)

    assert len(chunks) == 2
    assert all(c.metadata.get("fallback") is True for c in chunks)


def test_fallback_section_title_is_unknown():
    elements = [make_narrative("Herhangi bir metin.")]
    chunks = chunk_by_sections(elements)

    assert chunks[0].section_title == "Unknown Section"


# --- Senaryo 3: Table ayrı chunk ---

def test_table_gets_own_chunk():
    elements = [
        make_title("Dozaj Tablosu"),
        make_narrative("Aşağıdaki tabloya bakınız."),
        make_table("Doz | Frekans\n500mg | 2x"),
    ]
    chunks = chunk_by_sections(elements)

    assert len(chunks) == 2
    table_chunk = next(c for c in chunks if c.metadata.get("element_type") == "table")
    assert "500mg" in table_chunk.content


def test_table_metadata_has_element_type():
    elements = [
        make_title("Farmakokinetik"),
        make_table("T1/2 | 6 saat"),
    ]
    chunks = chunk_by_sections(elements)

    assert any(c.metadata.get("element_type") == "table" for c in chunks)


# --- Senaryo 4: Boş metin görmezden gelinir ---

def test_empty_text_elements_ignored():
    elements = [
        make_title("Dozaj"),
        make_narrative("   "),
        make_narrative("500mg"),
    ]
    chunks = chunk_by_sections(elements)

    assert len(chunks) == 1
    assert chunks[0].content == "500mg"
