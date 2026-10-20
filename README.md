# Clinical Document QA System

A retrieval-augmented question answering system over clinical reference
documents: drug leaflets, clinical protocols and medical guidelines. It
includes an intelligent document processing (IDP) pipeline that classifies
and routes uploaded PDFs before they are indexed.

Wrong answers in this domain have real consequences, so the design puts
**faithfulness first**. The system must be able to say "I don't know"
instead of answering from weak context.

> **Status: work in progress.** The core components are built and
> unit-tested **in isolation**. They are not yet wired into an end-to-end
> pipeline, and there is no API. See [What is not built yet](#what-is-not-built-yet).

## Planned architecture

```text
PDF upload → classify → extract tables/forms → route
  → section-aware chunking → Weaviate (dense + BM25 hybrid)
  → query rewrite → MMR → Cohere Rerank → confidence gate → LLM
  → faithfulness check → response
```

Every incoming query passes PII validation before anything else runs. A
query that identifies a patient is rejected, not anonymized.

## What is built

| Component | Module | Decision record |
| --- | --- | --- |
| Section-aware chunking (section title kept as metadata) | [app/chunking/](app/chunking/) | [ADR-001](docs/ADR-001-chunking-strategy.md) |
| Hybrid search (dense + BM25, `alpha = 0.40`) | [app/retrieval/](app/retrieval/) | [ADR-002](docs/ADR-002-hybrid-search-weights.md) |
| PII rejection at query entry (names, MRN, DOB, national IDs) | [app/validation/](app/validation/) | [ADR-003](docs/ADR-003-pii-rejection-at-entry.md) |
| Redis cache with a 3-hour TTL and flush-on-reindex | [app/cache/](app/cache/) | [ADR-004](docs/ADR-004-redis-ttl-and-invalidation.md) |
| MMR diversity (`lambda_mult = 0.3`) | [app/retrieval/](app/retrieval/) | [ADR-005](docs/ADR-005-mmr-diversity-weight.md) |
| Cohere Rerank (`top_n = 8`) | [app/retrieval/](app/retrieval/) | [ADR-006](docs/ADR-006-rerank-top-n.md) |
| Confidence gate with fallback response (`>= 0.7`) | [app/confidence/](app/confidence/) | [ADR-007](docs/ADR-007-confidence-threshold.md) |
| RAGAS metrics (faithfulness, context precision/recall) | [eval/](eval/) | [ADR-008](docs/ADR-008-ragas-metrics-and-faithfulness-threshold.md) |
| IDP document classification and routing | [app/idp/](app/idp/) | [ADR-009](docs/ADR-009-idp-document-classification-and-routing.md) |
| Auth and audit log table definitions (not wired) | [app/auth/](app/auth/) | |

The numeric values above (`alpha`, `lambda_mult`, `top_n`, the confidence
threshold and the RAGAS faithfulness threshold of `0.85`) are reasoned
starting points. They have not been tuned against a real document corpus
yet.

## What is not built yet

- **Ingestion:** PDF upload and indexing into Weaviate
- **Query rewriting** and the **answer-generating LLM call**
- **Orchestration:** nothing yet calls the components above in sequence
- **API:** [app/api/](app/api/) is empty, so there is no FastAPI endpoint
- **Access control:** no API key validation and no audit log writing.
  **Do not expose this system beyond local development.**
- **RAGAS eval dataset and CI gate:** the metrics exist, but there is no
  dataset to run them on and no pipeline that blocks deploys
- **Docker / docker-compose**

## Stack

LangChain (LCEL) · Weaviate · Unstructured.io · Redis · Cohere Rerank ·
Presidio · RAGAS · LangSmith · FastAPI · pytest

## Local setup

Requires Python 3.12.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_lg   # NER model used for PII detection
cp .env.example .env                      # then fill in your API keys
pytest tests/
```

Every external call (LLM, Weaviate, Redis, Cohere) is mocked in the tests,
so `pytest` does not need API keys or running services.

### RAGAS evaluation environment

RAGAS needs an older LangChain line that conflicts with the app's
dependencies, so it gets its own virtual environment (see
[ADR-008](docs/ADR-008-ragas-metrics-and-faithfulness-threshold.md)):

```bash
python -m venv venv-eval
source venv-eval/bin/activate
pip install -r requirements-eval.txt
pytest eval/tests/
```

## Design decisions

Every architectural decision is recorded as an ADR in [docs/](docs/). Each
one lists the options considered, the reasoning, and what would break if
the decision changed.

## License

[MIT](LICENSE)
