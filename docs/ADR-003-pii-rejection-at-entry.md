# ADR-003: PII Detection and Rejection at Query Entry

## Status

Accepted

## Context

Before the Redis TTL and invalidation decision (next ADR) can be made, the
system needs an explicit stance on patient-identifying information in queries.

This system supports pure reference lookup queries only — questions about the
knowledge base (drug leaflets, protocols, guidelines), never about a specific
patient. A query mentioning a patient (by name or otherwise) is a misuse case
to catch, not a supported input the system must answer correctly.

## Decision

Detect PII at query entry — before query rewriting, retrieval, MMR, Cohere
Rerank, the LLM call, or the cache — using Presidio's `AnalyzerEngine` only.
If a PII entity is detected above a confidence threshold, reject the query
immediately with a message telling the user to rephrase without
patient-identifying information (name, MRN, date of birth, national ID, or
similar). No anonymized or partial version of the query is constructed or
passed downstream — the query either passes validation unchanged, or it does
not proceed at all.

Concretely: a function `validate_query(query: str) -> QueryValidationResult`,
where `QueryValidationResult` carries `is_valid: bool` and an optional
`rejection_message: str`. The function has no dependency on the FastAPI layer
(which does not exist yet) and can be implemented and tested now in isolation;
the future API layer is responsible for turning a failed validation into an
HTTP response.

Because a rejected query never proceeds, every downstream component —
retrieval, rerank, the LLM, and the cache — only ever sees text that has
already passed validation. `RedisCache` can be used directly in the next ADR,
with no custom subclass.

## Options Considered

### Option A: Anonymize and continue

- Pros:
  - Preserves the general intent of a query while removing the identifying
    detail
- Cons:
  - Does not fit this system's scope: a patient-specific query is not made
    answerable by removing the name (see Context)
  - Fails silently on a false positive — a misclassified non-PII term is
    masked with no feedback to the user
  - Requires `presidio-anonymizer` and a placeholder-uniqueness decision for
    no benefit under this scope

### Option B: Detect and reject (Selected)

- Pros:
  - Matches the system's actual scope — a patient-specific query is refused
    outright, not partially processed
  - Simpler: only `presidio-analyzer` is needed, no anonymizer package, no
    placeholder logic
  - A false positive is visible and correctable: the user sees a rejection
    message and can rephrase, rather than the query being silently altered
  - Downstream components never see anything but validated queries
- Cons:
  - Worse UX in the rare case where a name appears incidentally in an
    otherwise-fine general question — the whole query is refused, not just
    the name
  - Still relies on Presidio's detection quality (false negatives/positives),
    same residual risk as any Presidio-based approach

### Option C: No detection at entry, guard only at the cache boundary

- Pros:
  - Smallest, most isolated change
- Cons:
  - Does not prevent PII from reaching the LLM or Cohere Rerank — only
    protects Redis persistence, missing the larger exposure
  - Breaks cache read/write key consistency if PII handling differs between
    `lookup()` and `update()`
  - Rejected for the same reasons as in the prior version of this ADR

## Reasoning

Option A was rejected because it solves the wrong problem for this system's
scope: once a query is patient-specific, removing the name doesn't turn it
into a valid reference-lookup question, and it introduces a silent-corruption
failure mode on false positives. Option C was rejected because it only
protects the cache, not the LLM/Cohere exposure, and reintroduces a
correctness problem between cache reads and writes.

Option B is the only option where "safe" is a property of what is allowed to
enter the system at all, and where a detection error (false positive) is
visible to the user rather than silently changing their query's meaning.

## Consequences

- New dependencies: `presidio-analyzer` and a spaCy English NER model, added
  to `requirements.txt`. `presidio-anonymizer` is not needed.
- `validate_query` runs on every query (not just cache misses), so its cost is
  a fixed per-request cost
- A rejected query is logged as an event only ("query rejected: PII detected")
  — never the flagged text itself, per the PII logging rule
- False negatives remain possible (Presidio is probabilistic, not a
  guarantee) — a missed detection still reaches downstream components
- False positives cause a legitimate general question to be refused; the
  rejection message must be clear enough that the user understands why and
  can rephrase, rather than treating it as a system error
- Known drug/protocol names that Presidio may misclassify as `PERSON` (e.g.
  "Xarelto") are handled with a static, developer-maintained allowlist —
  a plain list loaded from config, updated via normal code review and
  deploy, not a runtime-editable list. A runtime-editable allowlist would
  itself be a security control needing access control and an audit trail,
  which does not exist until the Auth mechanism & PHI access control design
  decision is made. That decision should be revisited once Auth/PHI is
  decided, not before.
- **The allowlist must only contain terms that are not plausible person
  names.** During implementation, the word "max" was added to suppress a
  false-positive rejection on "what is the max daily dose" (Presidio
  misclassified "max" as `PERSON`, score 0.85). This was reverted after
  testing showed it also silently passed "Is metformin safe for Max?" — a
  query naming a real patient — because Presidio scores both occurrences of
  the string identically; a confidence threshold cannot distinguish them,
  since the ambiguity is in the word itself, not the model's certainty.
  "Xarelto" is safe to allowlist because no real patient is plausibly named
  Xarelto; "max" is not, because Max is a common given name. Any future
  allowlist addition must be checked against this criterion, not just
  against whether it currently triggers a false positive.
- The Redis TTL/invalidation ADR (next) can assume the cache only ever
  receives already-validated queries and can use plain `RedisCache`

## What Would Break If We Changed This

Reverting to anonymize-and-continue would reintroduce the silent-corruption
failure mode on false positives and require deciding placeholder uniqueness
again, for a use case (patient-specific queries) this system does not support
anyway. Removing detection entirely would mean PII-bearing queries reach the
LLM and Cohere Rerank unfiltered, with only the (separately decided) upstream
input-length validation as a control — which does not check for PII content
at all.
