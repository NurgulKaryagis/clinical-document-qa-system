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
    top_k: int = 10

    allowlist: list = [
        "Xarelto"
    ]


settings = Settings()
