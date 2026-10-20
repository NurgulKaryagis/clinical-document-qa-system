# ADR-003: PII Detection and Rejection at Query Entry

## Status

Accepted (revised 2026-10-20: the rejected entity set is now explicit,
after an outside review found that only `PERSON` was enforced)

## Context

Before the Redis TTL and invalidation decision (next ADR) can be made, the
system needs an explicit stance on patient-identifying information in queries.

This system supports pure reference lookup queries only — questions about the
knowledge base (drug leaflets, protocols, guidelines), never about a specific
patient. A query mentioning a patient (by name or otherwise) is a misuse case
to catch, not a supported input the system must answer correctly.

**2026-10-20 revision.** The first implementation rejected only Presidio
`PERSON` entities and silently skipped every other type, so most of the
identifiers this ADR promises to reject were passed downstream. Running the
validator against real queries showed:

| Query | Rejected? | Why |
| --- | --- | --- |
| `Is metformin safe for John Smith?` | yes | `PERSON` |
| `Dosing for patient MRN 00482913?` | **no** | Presidio has no MRN recognizer |
| `Patient born 03/14/1958, max metformin dose?` | yes, **by accident** | "max" tagged `PERSON`; the DOB itself was ignored |
| `NHS number 943 476 5919 on apixaban, renal dosing?` | **no** | `UK_NHS` detected at score 1.0, then skipped |
| `Take amoxicillin for 7 days or 10 days?` | no (correct) | but `DATE_TIME` fires on "7 days" |

Cause: the implementation and its allowlist work were only tested against
`PERSON` false positives. The identifier list in this ADR was never turned
into test cases. The last row is the constraint on any fix: `DATE_TIME` and
`ORGANIZATION` (which tagged "apixaban") fire on ordinary clinical questions,
so rejecting every Presidio entity is not viable.

## Decision

Detect PII at query entry — before query rewriting, retrieval, MMR, Cohere
Rerank, the LLM call, or the cache — using Presidio's `AnalyzerEngine` only.
If an entity from the rejected set below is detected, at any score (fail
closed), reject the query immediately with a message telling the user to
rephrase without patient-identifying information (name, MRN, date of birth,
national ID, or similar). No anonymized or partial version of the query is
constructed or passed downstream — the query either passes validation
unchanged, or it does not proceed at all.

### Rejected entity set

- `PERSON`, with the allowlist below still applied
- National identifiers via Presidio's built-in recognizers: `US_SSN`,
  `UK_NHS`, `US_PASSPORT`, `US_ITIN`
- `MRN`: a custom recognizer for an identifier-shaped number near a context
  word such as "MRN", "medical record" or "record number"
- `DATE_OF_BIRTH`: a custom recognizer for a date near a context word such
  as "born", "DOB" or "date of birth"

Bare `DATE_TIME`, `ORGANIZATION` and other built-in types are not rejected.
Every entity type in the set has at least one positive and one negative
test case.

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

### Entity coverage (2026-10-20 revision)

#### Coverage 1: Explicit entity set plus custom MRN/DOB recognizers (Selected)

- Pros:
  - Covers every identifier class named in this ADR and the CLAUDE.md
    "Always PII" definition
  - Does not reject legitimate duration/dosing questions ("for 7 days")
  - Each rule is concrete and testable
- Cons:
  - The custom recognizer patterns are ours to maintain
  - MRN formats vary by institution; an MRN written without a context word
    can still slip through
  - New Presidio entity types are not covered until added to the set

#### Coverage 2: Reject every entity by default, exempt benign types

- Pros:
  - Fails closed for entity types we did not anticipate
- Cons:
  - `DATE_TIME` and `ORGANIZATION` appear in most dosing questions; either
    legitimate queries are rejected or those types are exempted, and
    exempting `DATE_TIME` reopens the DOB gap

#### Coverage 3: Narrow this ADR to names only

- Pros:
  - No code change
- Cons:
  - Leaves MRNs, DOBs and national IDs flowing downstream, contradicting the
    CLAUDE.md PII definition; documents the hole instead of closing it

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

For entity coverage, Coverage 1 is the only option that closes the gap
without making normal clinical questions unanswerable. Coverage 2's
fail-closed property is attractive, but the two types that make it unusable
are exactly the ones a DOB hides inside, so it collapses back into an
explicit list anyway. Context-word recognizers are what separate
"born 03/14/1958" from "for 7 days"; the date format alone cannot.

## Consequences

- New dependencies: `presidio-analyzer` and a spaCy English NER model, added
  to `requirements.txt`. `presidio-anonymizer` is not needed.
- `validate_query` runs on every query (not just cache misses), so its cost is
  a fixed per-request cost
- A rejected query is logged as an event only ("query rejected: PII detected")
  — never the flagged text itself, per the PII logging rule
- False negatives remain possible (Presidio is probabilistic, not a
  guarantee) — a missed detection still reaches downstream components.
  Known cases: an MRN or DOB without a context word, and national ID
  formats with no recognizer
- Adding an entity type to the rejected set is a reviewed code change with
  tests, like the allowlist. The allowlist applies only to `PERSON` and must
  never suppress an identifier type
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

Reverting the entity set to `PERSON` only would reopen the measured gap: an
NHS number detected at score 1.0 would again reach the LLM, Cohere and
Redis. Replacing the context-word DOB recognizer with bare `DATE_TIME` would
reject every question containing a duration ("take for 7 days"), making
dosing questions, the system's core use case, unanswerable.
