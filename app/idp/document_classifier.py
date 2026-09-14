from dataclasses import dataclass
from typing import Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from unstructured.documents.elements import Element, NarrativeText, Table, Title

from app.config import settings

CLASSIFICATION_PROMPT:str = """You are classifying a clinical document based on its section titles.

                            The document's section titles, in order, are:
                            {titles}

                            Classify the document into exactly one of these categories:
                            - drug_leaflet: a drug/medication package insert — sections like dosage, contraindications, side effects, indications
                            - clinical_protocol: a clinical treatment protocol or guideline — sections like diagnosis criteria, treatment steps, follow-up
                            - lab_report: a laboratory or diagnostic report — test results, reference ranges, measurements
                            - unclassified: none of the above clearly fit, or the titles are too sparse or ambiguous to tell

                            Choose the single best-fitting category. If you are not confident, choose unclassified rather than guessing."""
                            
@dataclass
class ClassificationResult:
    quality: Literal["clean", "needs_remediation"]
    genre: Literal["drug_leaflet", "clinical_protocol", "lab_report", "unclassified"]


def classify_quality(elements: list[Element]) -> Literal["clean", "needs_remediation"]:
    has_titles = any(isinstance(element, Title) for element in elements)
    return "clean" if has_titles else "needs_remediation"
    
def classify_genre(elements: list[Element]) -> Literal["drug_leaflet", "clinical_protocol", "lab_report", "unclassified"]:
    table_count = sum(1 for element in elements if isinstance(element, Table))
    narrative_count = sum(1 for element in elements if isinstance(element, NarrativeText))

    if table_count > narrative_count:
        return "lab_report"

    for element in elements:
        if not isinstance(element, Title):
            continue
        words = element.text.strip().lower()
        if "dosage" in words or "contraindications" in words:
            return "drug_leaflet"
        if "diagnosis" in words or "treatment" in words:
            return "clinical_protocol"

    return "unclassified"

class GenreClassification(BaseModel):
    genre: Literal["drug_leaflet", "clinical_protocol", "lab_report", "unclassified"]

def classify_genre_llm(elements: list[Element]) -> GenreClassification:
    titles = ",".join(element.text.strip() for element in elements if isinstance(element, Title))
    
    return ChatOpenAI(
                model=settings.idp_classifier_model,
                temperature=0,
                max_retries=2,
                api_key=settings.openai_api_key,
            ).with_structured_output(GenreClassification).invoke(CLASSIFICATION_PROMPT.format(titles=titles))

def classify_document(elements: list[Element]) -> ClassificationResult:
    quality = classify_quality(elements=elements)
    heuristic_genre = classify_genre(elements=elements)
    genre =  heuristic_genre if heuristic_genre != "unclassified" else classify_genre_llm(elements=elements).genre
    return ClassificationResult(
        quality=quality,
        genre=genre
    )