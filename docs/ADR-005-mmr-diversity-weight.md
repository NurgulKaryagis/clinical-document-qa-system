# ADR-005: MMR Diversity Weight (lambda_mult)

## Status

Accepted

## Context

Per the architecture, retrieval flows: hybrid search (Weaviate, dense + BM25)
→ query rewrite → MMR → Cohere Rerank → LLM. Hybrid search and MMR both use
embedding similarity ("semantic search," a bi-encoder approach: query and
chunk are embedded independently, then compared by cosine similarity) — fast
enough to run over the full corpus, but a cruder relevance judge than what
comes next. Cohere Rerank is a cross-encoder: query and chunk are fed into
the model together, so it can judge relevance far more precisely, but only
scales to a small candidate set (it re-scores every candidate on every
query, with no precomputation possible).

MMR (Maximal Marginal Relevance) selects the candidate set that Rerank will
then score. It balances relevance against diversity via `lambda_mult`
(0 = pure diversity, 1 = pure relevance). Because ADR-001 chunks are strict,
non-overlapping, single-section units, "near-duplicate chunks" in this
corpus usually means "several chunks restating the same section" (e.g.,
multiple Dosage-adjacent chunks), not stylistic repetition — a
relevance-heavy MMR setting risks filling the candidate pool with several
chunks from one section while a highly relevant chunk from a different
section (e.g., Contraindications) never makes it into the pool at all.

As with ADR-002's `alpha`, there is no real clinical document corpus or RAGAS
evaluation pipeline yet to empirically tune this value. This decision fixes
a reasoned **direction**, not a validated final number — already logged in
`docs/known-gaps.md` alongside `alpha` and the future RAGAS threshold as
values requiring re-validation once real documents and RAGAS scoring exist.

## Decision

Set `lambda_mult = 0.3` (diversity-leaning) as the starting value.

## Options Considered

### Option A: lambda_mult = 0.8 (relevance-heavy)

- Pros:
  - Stays tightly on-topic, low risk of pulling clearly irrelevant content
    into the candidate pool
- Cons:
  - Reintroduces the problem MMR exists to solve: with strict single-section
    chunks, this setting is likely to fill the pool with several
    near-duplicate chunks from one section, crowding out a highly relevant
    chunk from a different section
  - A chunk excluded here never reaches Rerank — Rerank cannot recover from
    a candidate pool that never contained the right chunk

### Option B: lambda_mult = 0.5 (LangChain default)

- Pros:
  - Safe, well-tested generic default, no strong bias
- Cons:
  - Not reasoned for this domain — ignores that ADR-001's chunking already
    makes cross-section diversity more valuable here than in a generic RAG
    corpus

### Option C: lambda_mult = 0.3 (diversity-leaning) (Selected)

- Pros:
  - Favors pulling chunks from different sections into the candidate pool,
    directly supporting complete, faithful answers (e.g., Dosage +
    Contraindications for the same drug, not five Dosage variants)
  - The downstream Cohere Rerank step is a strictly more accurate relevance
    judge than MMR's embedding similarity — Rerank can demote a chunk that
    turns out to be only marginally relevant, but it can never promote a
    chunk that was never retrieved into the pool in the first place. This
    makes the cost of the two failure modes asymmetric.
- Cons:
  - Some risk of pulling a chunk into the pool mainly because it differs
    from the others, not because it is relevant — diluting the pool Rerank
    has to work with

## Reasoning

The three options differ in how they trade off two failure modes: a
relevant chunk missing from the candidate pool entirely (unrecoverable — no
downstream step can fix a retrieval that never happened) versus a
marginally-relevant chunk taking a slot in the pool (recoverable — Rerank
demotes it, or the LLM simply doesn't use it). Given "wrong answers have
real consequences" and that a missed contraindication is a more severe
failure than an unused, borderline-relevant chunk, the option that biases
toward the recoverable failure mode is preferred. 0.3 (not 0.0) was chosen
over the most extreme diversity setting to avoid excessively diluting the
pool with chunks that differ from each other but share no real relevance to
the query.

## Consequences

- The MMR candidate pool will more often include chunks from multiple
  sections of the same drug/protocol document, rather than several chunks
  from one section
- Some marginally relevant chunks may occupy pool slots; this is expected to
  be corrected by Cohere Rerank, not by MMR itself
- `lambda_mult = 0.3` is a reasoned starting point, not a tuned value — see
  `docs/known-gaps.md` for the required re-validation once real documents
  and a RAGAS evaluation pipeline exist
- This decision assumes Cohere Rerank is not skipped (already a hard rule in
  the project) — if Rerank were ever removed, this diversity-leaning setting
  would need to be revisited, since nothing would then correct for
  marginally-relevant chunks reaching the LLM

## What Would Break If We Changed This

Moving toward Option A (relevance-heavy) would risk silently dropping
clinically important chunks (e.g., contraindications) from the candidate
pool for queries that skew toward one section, with no way for Rerank to
recover them. This is a structural risk specific to this project's strict
single-section chunking (ADR-001) — a corpus without that constraint would
face this risk less acutely.
