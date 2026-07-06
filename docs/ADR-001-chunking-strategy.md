# ADR-001: Chunking Strategy — Section Boundary Detection

## Status

Accepted

## Context

Clinical protocols, drug leaflets, and medical guidelines are section-structured
documents (Indications, Dosage, Side Effects, Contraindications, etc.).
The system's core constraint: section content must not be mixed across chunks.
Each chunk must belong to a single section, with the section title stored as metadata.

The question: how do we detect section boundaries from Unstructured.io output?

## Decision

Trust Unstructured.io's own element types.
`Title` element → start a new chunk.
`NarrativeText` and `Table` elements → append to the current section.
No additional post-processing.

## Options Considered

### Option A: Trust Unstructured element types (Selected)

- Pros:
  - Minimal code, low maintenance overhead
  - Clinical documents are typically well-structured — Unstructured detection is sufficient
  - Easy to iterate; switching to Option B is straightforward if issues arise
- Cons:
  - `Title` detection may be inaccurate for poorly scanned or malformatted PDFs
  - We depend on Unstructured's classification quality

### Option B: Unstructured + custom post-processing

- Pros:
  - More control: short `Title` elements treated as real headings, `Table` always isolated
  - Recoverable if Unstructured misclassifies
- Cons:
  - Extra code and complexity
  - Not necessary for well-structured clinical documents at this stage

### Option C: Rule-based (regex + character analysis)

- Pros:
  - No dependency on Unstructured's classification
- Cons:
  - Brittle — requires separate rules per PDF format
  - High maintenance cost

### Why Not Semantic Chunking?

Semantic chunking splits by meaning shift, not by headings. In clinical documents,
"Metformin 500mg taken twice daily" and "Contraindicated in renal failure" may appear
semantically close — but they belong to different sections (Dosage vs. Contraindications).
Semantic chunking risks merging them. This violates the hard rule: section content must
not be mixed across chunks. It was excluded from consideration on that basis.

## Reasoning

Clinical documents are structured documents and Unstructured.io is optimized for them.
Option A is sufficient for now. If real-document testing reveals weak `Title` detection,
migrating to Option B is low-cost. Avoiding premature complexity.

## Consequences

- Unstructured.io's element detection directly affects pipeline accuracy
- `Title` element quality must be verified during initial document testing
- Adding post-processing later is always possible — this decision is reversible

## What Would Break If We Changed This

Switching to Option B or C: all unit tests and integration tests that depend on
Unstructured output would need to be rewritten. The chunk format stored in Weaviate
would not change, but chunk boundaries would — RAGAS faithfulness scores could be affected.
