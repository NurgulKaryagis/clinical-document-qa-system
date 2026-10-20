from dataclasses import dataclass

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider

from app.config import settings

nlp_configuration = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "en", "model_name": settings.presidio_spacy_model}],
}
nlp_engine = NlpEngineProvider(nlp_configuration=nlp_configuration).create_engine()

# Context words are part of the regex, not left to Presidio's score-based
# context enhancer: a bare number or date is not rejected (see ADR-003).
mrn_recognizer = PatternRecognizer(
    supported_entity="MRN",
    patterns=[
        Pattern(
            name="mrn_with_context",
            regex=r"\b(?:MRN|medical\s+record(?:\s+(?:number|no\.?))?|record\s+(?:number|no\.?))\s*[:#]?\s*[A-Z0-9-]{5,15}\b",
            score=0.9,
        )
    ],
)

_DATE = (
    r"(?:\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}"
    r"|\d{4}-\d{1,2}-\d{1,2}"
    r"|[A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4}"
    r"|\d{1,2}\s+[A-Z][a-z]+\.?\s+\d{4})"
)
dob_recognizer = PatternRecognizer(
    supported_entity="DATE_OF_BIRTH",
    patterns=[
        Pattern(
            name="dob_with_context",
            regex=rf"\b(?:born(?:\s+on)?|D\.?O\.?B\.?|date\s+of\s+birth)\s*[:\-]?\s*{_DATE}",
            score=0.9,
        )
    ],
)

analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
analyzer.registry.add_recognizer(mrn_recognizer)
analyzer.registry.add_recognizer(dob_recognizer)

REJECTED_ENTITIES = {
    "PERSON",
    "US_SSN",
    "UK_NHS",
    "US_PASSPORT",
    "US_ITIN",
    "MRN",
    "DATE_OF_BIRTH",
}

ALLOWLIST = {name.lower() for name in settings.allowlist}

@dataclass
class QueryValidationResult:
    is_valid: bool
    rejection_message: str | None = None

def validate_query(query: str) -> QueryValidationResult:
    results = analyzer.analyze(text=query, language="en")

    for result in results:
        if result.entity_type not in REJECTED_ENTITIES:
            continue
        # The allowlist only suppresses PERSON false positives, never identifiers.
        if result.entity_type == "PERSON" and query[result.start:result.end].lower() in ALLOWLIST:
            continue
        return QueryValidationResult(
            is_valid=False,
            rejection_message="Personal information is not allowed, try without personal information",
        )

    return QueryValidationResult(is_valid=True)
