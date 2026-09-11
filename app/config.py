from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # API keys / connection info — secrets, must come from environment
    openai_api_key: str = ""
    cohere_api_key: str = ""
    weaviate_url: str = ""
    weaviate_api_key: str = ""
    langsmith_api_key: str = ""

    # Decided architecture values (ADR-backed) — safe defaults, overridable via env
    presidio_spacy_model: str = "en_core_web_lg"
    hybrid_alpha: float = 0.40
    mmr_fetch_k: int = 20
    top_k: int = 10

    allowlist: list = [
        "Xarelto"
    ]

    redis_ttl_seconds: int = 3 * 60 * 60
    mmr_lambda_mult: float = 0.3
    rerank_top_n: int = 8
    rerank_model : str = "rerank-english-v3.0"
    
    confidence_threshold: float = 0.7
    fallback_message: str = "I don't have sufficiently reliable information in the available documents to answer this question with confidence. Please consult the official drug leaflet or a clinical pharmacist."

    idp_classifier_model: str = "gpt-4o-mini"
    CLASSIFICATION_PROMPT:str = """You are classifying a clinical document based on its section titles.

                            The document's section titles, in order, are:
                            {titles}

                            Classify the document into exactly one of these categories:
                            - drug_leaflet: a drug/medication package insert — sections like dosage, contraindications, side effects, indications
                            - clinical_protocol: a clinical treatment protocol or guideline — sections like diagnosis criteria, treatment steps, follow-up
                            - lab_report: a laboratory or diagnostic report — test results, reference ranges, measurements
                            - unclassified: none of the above clearly fit, or the titles are too sparse or ambiguous to tell

                            Choose the single best-fitting category. If you are not confident, choose unclassified rather than guessing."""

settings = Settings()
