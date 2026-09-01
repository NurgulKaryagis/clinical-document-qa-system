# ADR-002: Hybrid Search Weight Configuration

## Status

Accepted

## Context

Weaviate hybrid search combines dense (embedding) and sparse (BM25) retrieval
via an `alpha` parameter. Clinical documents contain precise terminology —
drug names, dosages, ICD codes — where exact term matching matters.
At the same time, users may query with natural language that does not contain
the exact clinical term.

The question: what `alpha` value balances these two retrieval modes?

## Decision

Set `alpha = 0.40` as the starting value — slightly BM25-weighted.
Re-evaluate after testing with real clinical documents using RAGAS scores.

## Options Considered

### Option A: alpha = 0.75 (dense-heavy)

- Pros:
  - Handles natural language queries well
  - Finds semantically related content even without exact terms
- Cons:
  - Risks missing exact drug names, dosages, and clinical codes
  - A query for "metformin" may return "oral antidiabetic agent" chunks instead

### Option B: alpha = 0.50 (balanced)

- Pros:
  - Safe default, no strong bias
  - Reasonable starting point for most domains
- Cons:
  - Does not account for the higher importance of exact term matching
    in clinical documents specifically

### Option C: alpha = 0.25 (BM25-heavy)

- Pros:
  - Strong exact match — drug names and dosages are rarely missed
- Cons:
  - Struggles with natural language queries that omit the exact clinical term
  - "kidney problems with diabetes medication" would miss metformin chunks

### Selected: alpha = 0.40

Between Option B and C. Slightly BM25-weighted to prioritize exact clinical
term matching, while keeping enough dense weight for natural language queries.

## Reasoning

Clinical documents are terminology-dense. Exact match on drug names, dosages,
and contraindication terms is more safety-critical than semantic breadth.
A missed "metformin" is more dangerous than a missed paraphrase.
However, users do not always query with exact terms — dense retrieval handles this.
0.40 reflects the relative importance of exact matching in this domain without
abandoning semantic retrieval.

This value is a reasoned starting point, not a tuned value. It must be validated
against real clinical documents using RAGAS faithfulness and context_precision scores.

## Consequences

- BM25 carries slightly more weight — exact drug names and dosages surface first
- Dense retrieval still active — natural language queries remain functional
- `alpha` is a single config value; adjusting it does not require code changes
- RAGAS evaluation will determine whether 0.40 holds or needs adjustment

## What Would Break If We Changed This

Increasing alpha toward 1.0: exact clinical term queries (drug name, dosage, ICD code)
risk returning semantically similar but terminologically incorrect chunks.
Decreasing alpha toward 0.0: natural language queries without exact terms return
empty or irrelevant results. Either direction degrades retrieval quality in
different failure modes.
