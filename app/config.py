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
    
settings = Settings()
