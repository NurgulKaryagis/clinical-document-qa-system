# ADR-006: Cohere Rerank top_n

## Status

Accepted

## Context

Per ADR-005, MMR is deliberately set to favor diversity (`lambda_mult = 0.3`)
so that the candidate pool spans multiple sections of a drug/protocol
document (e.g., Dosage and Contraindications), not several near-duplicate
chunks from one section. Cohere Rerank then re-scores every candidate in
that pool with a cross-encoder and returns the top `top_n`, in relevance
order, as the LLM's final context.

`top_n` determines whether MMR's diversity work actually survives to the
LLM. If `top_n` is too small, Rerank can still re-collapse the pool back
toward relevance alone — if it judges several Dosage-phrased chunks as more
directly on-topic than a differently-worded Contraindications chunk, a
narrow `top_n` may exclude the latter even though MMR successfully retrieved
it. A larger `top_n` protects against this, at the cost of a longer LLM
context, which carries its own risk ("lost in the middle" — LLMs are
documented to under-use information buried in a long context, even when
present). Cohere Rerank orders its output by relevance, which partly
mitigates this: the most relevant chunk is always first regardless of
`top_n`.

As with `alpha` (ADR-002) and `lambda_mult` (ADR-005), there is no real
clinical document corpus yet to determine empirically how many sections a
typical query actually needs. This is a reasoned starting point, not a
validated number — logged in `docs/known-gaps.md` alongside the other two.

## Decision

Set `top_n = 8`.

## Options Considered

### Option A: top_n = 3 (narrow)

- Pros: focused context, lowest cost/latency, minimizes lost-in-the-middle risk
- Cons: undermines the reason MMR was set to favor diversity in ADR-005 — not
  enough room to guarantee a differently-worded but critical section survives
  Rerank's re-scoring

### Option B: top_n = 5 (moderate)

- Pros: some room for 2-3 sections, shorter context than the wide option
- Cons: less margin than Option C for queries needing more than 2-3 sections
  (e.g., dosage + contraindications + interactions + warnings together)

### Option C: top_n = 8-10 (wide) — 8 selected

- Pros: maximizes the chance that MMR's diverse candidate set survives
  intact to the LLM; Rerank's relevance ordering means the most important
  chunk is still first even with more slots filled
- Cons: longer context increases lost-in-the-middle risk and cost/latency
  relative to a narrower `top_n`

## Reasoning

Same asymmetry as ADR-005: a section excluded from the final context can
never be used by the LLM at all, while a marginally relevant chunk that is
included but ranked last is a smaller, more recoverable cost (the LLM can
disregard it, and Rerank's ordering means it is not competing for attention
with the top result). Given clinical queries can plausibly need several
sections at once (dosage, contraindications, interactions, warnings), the
narrower options risk silently dropping one of them. 8, not 10, was chosen
as the lower end of the "wide" range to limit unnecessary context growth
while keeping the same reasoning as Option C.

## Consequences

- The LLM's context will typically include content from multiple sections
  per query, not a single narrowly-focused chunk set
- `top_n = 8` is a reasoned starting point, not a tuned value — added to
  `docs/known-gaps.md` for re-validation once real documents and a RAGAS
  evaluation pipeline exist
- Larger `top_n` increases per-query LLM cost and latency compared to a
  narrower value; this tradeoff has not been measured against real usage yet

## What Would Break If We Changed This

Reducing `top_n` toward Option A would risk silently undoing the diversity
ADR-005 was written to preserve — MMR would still retrieve a diverse
candidate pool, but Rerank would be free to discard most of that diversity
before the LLM ever sees it, defeating the purpose of ADR-005 without
changing that decision directly.
