# ADR-004: Redis TTL Value and Cache Invalidation Logic

## Status

Accepted

## Context

The RAG pipeline (query rewrite → MMR → Cohere rerank → LLM → faithfulness
check) is expensive: every cache miss pays for a rerank API call, an LLM
call, and a RAGAS faithfulness check. Repeated questions (e.g., multiple
clinicians asking about the same drug during the same shift) are common, so
caching query→answer pairs in Redis reduces both cost and latency.

The risk: clinical source documents (protocols, drug leaflets) can be
updated. If a cached answer outlives the document it was generated from, the
system serves outdated clinical information with no indication that it is
stale. A missed invalidation is not a performance bug — it is a
patient-safety bug.

This decision assumes ADR-003 (PII Detection and Rejection at Query Entry):
every query reaching the cache has already passed `validate_query` and
contains no detected patient-identifying information. This ADR is therefore
only about caching mechanics — how long an entry lives and when it is
cleared — not about what is safe to persist. Plain `RedisCache` (LangChain)
is used directly; no custom subclass is needed.

The question: how long should a cached answer live (TTL), and how is it
invalidated when the underlying document changes?

## Decision

Set TTL = 3 hours. On every document ingestion/re-processing event in the IDP
pipeline, flush the entire query-answer cache (not just entries related to
the updated document).

## Options Considered

### Option A: Short TTL (5-15 min), no explicit invalidation

- Pros:
  - Minimal staleness risk — worst case is a few minutes of outdated data
- Cons:
  - Cache hit rate stays low for realistic query patterns spread across a shift
  - Most of the cost/latency benefit of caching is lost

### Option B: Medium TTL (1-6h) + invalidation on document update (Selected)

- Pros:
  - Meaningful cache hit rate within a clinical shift/session
  - Explicit invalidation means staleness is bounded by the update event, not
    just by TTL — an updated document takes effect immediately, not after
    TTL expiry
- Cons:
  - Requires wiring invalidation into the IDP ingestion pipeline (extra
    integration point)

### Option C: Long TTL (24h+), rely solely on invalidation

- Pros:
  - Highest cache hit rate, lowest cost
- Cons:
  - Fully dependent on invalidation working correctly every time. Any missed
    or buggy invalidation path serves stale clinical data for up to 24 hours.
  - Unacceptable risk given "wrong answers have real consequences"

### Option D: RedisSemanticCache (similarity-based matching) instead of exact-match RedisCache

- Pros:
  - Higher cache hit rate — catches paraphrased queries that plain
    `RedisCache`'s exact hash match would miss entirely
- Cons:
  - Introduces an error class this domain cannot tolerate: two structurally
    similar questions about two different drugs can embed close enough
    together to be treated as the same cached question, regardless of how
    different the drugs actually are. A hit above the similarity threshold
    would silently return one drug's cached answer for a query about a
    different drug, with no error raised and no way for the user to detect
    it. This is a wrong-drug-information failure, not a staleness failure.
    Plain `RedisCache`'s exact `hash(prompt + llm_string)` key cannot
    produce this failure mode — two distinct prompts never collide.
  - `RedisSemanticCache`'s own source carries `# TODO - implement a TTL
    policy in Redis` — it has no native TTL support, which directly
    conflicts with this project's hard rule that Redis TTL must always be
    set.

### Invalidation granularity: full flush vs. targeted per-document keys

- Targeted (per-document/section key deletion): more efficient, preserves
  unrelated cache entries, but requires a correct mapping from cache key to
  source document. A wrong or missing mapping silently leaves a stale entry
  in the cache.
- Full cache flush (Selected): simpler, no mapping to get wrong. Clinical
  document updates are infrequent (not a high-frequency event), so the
  efficiency cost of flushing the whole cache on each update is small
  relative to the safety gained.

## Reasoning

Between A, B, and C, B is the only option that balances a real cache hit rate
against a bounded staleness window. A gives up too much of the caching
benefit; C accepts an unbounded staleness window that depends entirely on
invalidation correctness, which is not acceptable for clinical data.

3 hours was chosen as a middle value: long enough to cover repeated questions
within a clinical session, short enough that even if invalidation fails to
fire, the staleness window is bounded to a fraction of a working shift, not a
full day.

TTL is not redundant with invalidation — it is a backstop for cases
invalidation cannot cover:

- **Invalidation may not fire at all**: the IDP pipeline could crash after
  processing a document but before the flush runs, or a document could be
  written directly to Weaviate bypassing the IDP pipeline entirely. TTL
  guarantees an upper bound on staleness even when the "known" invalidation
  trigger never happens.
- **The document may not have changed, but the pipeline that answers
  questions about it did**: an embedding model update, a rerank
  configuration change, or a prompt change all produce a different correct
  answer for the same document, and none of them trigger flush-on-ingest
  (which only fires on document changes).
- **Unbounded cache growth**: without TTL, memory usage grows indefinitely
  with query volume, regardless of whether any document ever changes.

Option D was rejected on a stricter basis than A/B/C's hit-rate-vs-staleness
tradeoff: this is not a domain where an approximate cache hit is an
acceptable risk to trade for a higher hit rate. A wrong-drug-information
error from a semantic-similarity false match is categorically worse than
the stale-data risk this ADR otherwise manages — consistent with ADR-002's
reasoning that exact matching matters more than semantic breadth for
clinical terminology.

Full-cache-flush invalidation was chosen over targeted invalidation because a
missed key mapping is a silent failure mode — the exact kind of bug that is
hard to detect and dangerous in a clinical context. Flushing everything on
every document update trades a small, measurable efficiency cost for the
removal of an entire class of invalidation bugs.

## Consequences

- Every document ingestion event must trigger a full Redis cache flush
- Cache hit rate will dip immediately after any document update (expected,
  and logged per the Production Standards cache-hit-rate requirement)
- No per-document cache key tagging is needed, simplifying the caching layer
- Plain `RedisCache(redis_=client, ttl=10800)` is used — no custom subclass,
  since ADR-003 already guarantees no PII reaches this layer
- TTL and flush-on-ingest work together: TTL bounds staleness when no update
  occurs or invalidation fails to fire; flush-on-ingest bounds staleness to
  zero when a document update is correctly detected

## What Would Break If We Changed This

Moving to targeted invalidation later would require introducing a cache key
scheme that encodes which document(s) a cached answer depends on, and the
ingestion pipeline would need to resolve "which keys does this document
affect" correctly on every update — a new failure mode that does not exist
under full-flush. Removing TTL (invalidation-only) would remove the backstop
for the three failure modes in Reasoning and would fall back to Option C's
risk profile. Removing invalidation entirely (TTL-only) would mean a document
update takes up to 3 hours to take effect, violating the hard rule that stale
clinical data must not be served past a real document update.
