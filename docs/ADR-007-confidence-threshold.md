# ADR-007: Confidence Threshold Value and Fallback Response

## Status

Accepted

## Context

Retrieval never returns zero results — even for a question the corpus has
no good answer to, hybrid search, MMR, and Rerank will still return the
*least bad* candidates available, each carrying a `relevance_score` from
Cohere Rerank (ADR-006 established this as the final, most accurate score
in the pipeline). Without a gate on that score, the LLM would generate an
answer from weak or irrelevant context — a confident-sounding but
unreliable response, with nothing distinguishing it from a well-supported
one.

The system must be able to say "I don't know" rather than let the LLM
answer when the best available context is not actually relevant. The
question: what `relevance_score` threshold on the top-ranked chunk should
trigger a fallback response instead of an LLM call, and what should that
fallback say?

As with `alpha` (ADR-002), `lambda_mult` (ADR-005), and `top_n` (ADR-006),
there is no real clinical document corpus or Cohere rerank score
distribution to tune this threshold against yet. This is a reasoned
direction, not a validated number, and must be re-evaluated once real
documents and real Rerank score distributions are available.

## Decision

If the top-ranked chunk's `relevance_score` after Rerank is below `0.7`,
skip the LLM call and return a fixed fallback response indicating the
system does not have reliable information to answer the question.

## Options Considered

### Option A: Low threshold (~0.1-0.2)

- Pros:
  - Fallback rarely triggers; the system answers most queries
- Cons:
  - Provides almost no protection against answering from weak or
    irrelevant context — close to the "confidence threshold set to 0"
    failure mode this project explicitly treats as dangerous

### Option B: Moderate threshold (~0.4-0.5)

- Pros:
  - A conventional middle-ground default
- Cons:
  - Not reasoned for this domain specifically — no basis stronger than
    "a typical default," when the domain's stated priority (faithfulness
    over answering) argues for leaning further toward refusal

### Option C: High threshold (~0.6-0.7) (Selected, 0.7)

- Pros:
  - Directly reflects the project's established asymmetry: a wrong answer
    is a more severe failure than an unnecessary refusal, consistent with
    every prior ADR's reasoning (ADR-002, ADR-004, ADR-005, ADR-006)
- Cons:
  - Risks the opposite failure mode: over-refusing questions the system
    could have answered correctly, making the tool less useful. This
    failure mode is real but was judged less severe than a wrong clinical
    answer, and it is measurable and correctable through real testing in a
    way a wrong answer already served to a clinician is not.

## Reasoning

Every ADR in this project so far has resolved a hit-rate-vs-risk tradeoff
in favor of the option that fails toward refusal or exclusion rather than
toward a wrong or unverified answer (ADR-002's exact-match bias, ADR-004's
rejection of semantic caching, ADR-005/006's diversity-over-relevance
bias). The confidence threshold is the final gate in the pipeline before an
answer reaches a clinician, so the same asymmetry applies with the least
room for a downstream step to compensate — there is no later stage that
can catch or correct a wrong answer once it is given. 0.7 was chosen as a
high but not extreme value: high enough to reflect that priority, without
assuming a score distribution this project has no real data for yet.

The fallback response was written to state plainly that the system lacks
reliable information, rather than hedging or offering a partial answer,
since a hedged answer still risks being read as authoritative.

## Consequences

- Any query whose best-ranked chunk scores below 0.7 receives a fixed
  fallback message instead of an LLM-generated answer, regardless of how
  the LLM might otherwise have answered
- The fallback response must be logged as an event (query resulted in
  fallback), without logging the query text itself if it could contain
  free-text content — consistent with the PII logging rule
- `0.7` is a reasoned starting point, not a tuned value. It may prove too
  high (over-refusing) once tested against real documents and real Cohere
  rerank score distributions, and should be re-evaluated at that point
- Cache hit rate and RAGAS metrics should be tracked separately for
  fallback vs. answered queries, since a fallback is not a retrieval
  failure to be optimized away, but is the intended safe behavior when
  context is weak

## What Would Break If We Changed This

Lowering the threshold toward Option A or B would remove the protection
this ADR exists to provide — the LLM would begin answering from context
that Rerank itself scored as weakly relevant, reintroducing the "confident
wrong answer" failure mode this project has treated as its top risk since
ADR-001. Removing the threshold entirely (always calling the LLM) would
violate the hard rule that confidence threshold or fallback logic must
never be removed.
