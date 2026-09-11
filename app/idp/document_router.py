from dataclasses import dataclass
from typing import Literal

from unstructured.documents.elements import Element

from app.chunking.section_chunker import SectionChunk, chunk_by_sections
from app.idp.document_classifier import ClassificationResult


@dataclass
class RoutingResult:
    status: Literal["chunked", "held_for_remediation", "no_chunking_strategy"]
    chunks: list[SectionChunk] | None = None
    

def route_document(classification: ClassificationResult, elements: list[Element]) -> RoutingResult:
    if classification.quality == "needs_remediation":
        status = "held_for_remediation"
        chunks = None
    else:
        if classification.genre == "drug_leaflet" or classification.genre == "clinical_protocol":
            chunks = chunk_by_sections(elements=elements)
            status = "chunked"
        if classification.genre == "lab_report" or classification.genre == "unclassified" :
            status = "no_chunking_strategy"
            chunks = None
    return RoutingResult(
        status=status,
        chunks=chunks
    )