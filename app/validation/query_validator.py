from dataclasses import dataclass

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

from app.config import settings

nlp_configuration = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "en", "model_name": settings.presidio_spacy_model}],
}
nlp_engine = NlpEngineProvider(nlp_configuration=nlp_configuration).create_engine()
analyzer = AnalyzerEngine(nlp_engine=nlp_engine)

ALLOWLIST = {name.lower() for name in settings.allowlist}

@dataclass
class QueryValidationResult:
    is_valid: bool
    rejection_message: str | None = None

def validate_query(query: str) -> QueryValidationResult:
    results = analyzer.analyze(text=query, language="en")

    for result in results:
        if result.entity_type != "PERSON":
            continue
        if query[result.start:result.end].lower() in ALLOWLIST:
            continue
        return QueryValidationResult(
            is_valid=False,
            rejection_message="Personal information is not allowed, try without personal information",
        )

    return QueryValidationResult(is_valid=True)