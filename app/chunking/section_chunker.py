from dataclasses import dataclass, field
from typing import List
from unstructured.documents.elements import Element, Title, Table


@dataclass
class SectionChunk:
    section_title: str
    content: str
    metadata: dict = field(default_factory=dict)


def chunk_by_sections(elements: List[Element]) -> List[SectionChunk]:
    has_titles = any(isinstance(el, Title) for el in elements)

    if not has_titles:
        return _fallback_paragraph_chunks(elements)

    chunks: List[SectionChunk] = []
    current_title = "Unknown Section"
    current_texts: List[str] = []

    for element in elements:
        if isinstance(element, Title):
            if current_texts:
                chunks.append(_build_chunk(current_title, current_texts))
                current_texts = []
            current_title = element.text.strip()

        elif isinstance(element, Table):
            if current_texts:
                chunks.append(_build_chunk(current_title, current_texts))
                current_texts = []
            chunks.append(SectionChunk(
                section_title=current_title,
                content=element.text.strip(),
                metadata={"section": current_title, "element_type": "table"},
            ))

        else:
            if element.text.strip():
                current_texts.append(element.text.strip())

    if current_texts:
        chunks.append(_build_chunk(current_title, current_texts))

    return chunks


def _build_chunk(title: str, texts: List[str]) -> SectionChunk:
    return SectionChunk(
        section_title=title,
        content="\n\n".join(texts),
        metadata={"section": title},
    )


def _fallback_paragraph_chunks(elements: List[Element]) -> List[SectionChunk]:
    return [
        SectionChunk(
            section_title="Unknown Section",
            content=el.text.strip(),
            metadata={"section": "Unknown Section", "fallback": True},
        )
        for el in elements
        if el.text.strip()
    ]
