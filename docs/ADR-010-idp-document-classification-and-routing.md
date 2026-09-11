# ADR-010: IDP Document Classification and Routing

## Status

Accepted

## Context

A real clinical document corpus is not uniform. Documents vary along two
independent dimensions that matter to how they should be processed:

- **Quality**: a clean, natively-digital PDF extracts reliably; a scanned
  or poorly-produced document may extract with garbled text or fail to
  expose clear structural markers at all.
- **Genre**: a drug leaflet, a clinical protocol, and a lab/diagnostic
  report are structured completely differently. A drug leaflet's Dosage/
  Contraindications/Side Effects sections and a lab report's tabular
  reference ranges are not the same kind of document and do not suit the
  same chunking approach.

The existing chunking strategy trusts Unstructured.io's own `Title`
element detection to find section boundaries, with a fallback for
documents where no titles are found at all. That strategy was designed
for, and validated against, narrative section-structured documents like
drug leaflets — it was never meant to be the single chunking approach for
every kind of document this system might ingest.

Before documents can be routed to the chunking strategy appropriate for
their genre, or flagged for quality remediation before chunking at all,
they must first be classified. This ADR establishes how that
classification happens and what categories it produces. It does not
define new chunking strategies for genres other than the one the existing
chunker already serves — a document type that needs its own chunking
approach gets that approach designed in its own future ADR, not this one.

## Decision

Classify every ingested document along two independent axes:

1. **Quality**: `clean` or `needs_remediation`
2. **Genre**: one of `drug_leaflet`, `clinical_protocol`, `lab_report`,
   `unclassified`

Classification uses a hybrid approach. Cheap, deterministic heuristics run
first, based on signals Unstructured.io already produces during
extraction: whether `Title` elements were detected reliably, the
distribution of element types (a `Table`-dominated document suggests a lab
report; a `NarrativeText`-dominated document with clear titles suggests a
leaflet or protocol), and characteristic section-header keywords per
genre. When the heuristics produce an ambiguous or low-confidence result,
an LLM classifier is invoked as a fallback, given a summary of the
extracted structure, to make the final call.

Routing: `clean` documents proceed directly to chunking; `needs_remediation`
documents are held before chunking (the remediation process itself —
re-OCR, manual review, or rejection — is not designed by this ADR and
remains open). `drug_leaflet` and `clinical_protocol` currently route to
the existing section-based chunker, since both are narrative,
section-structured documents the existing strategy was built for.
`lab_report` and `unclassified` are flagged as needing their own chunking
strategy, which does not yet exist.

## Options Considered

### Classification scope

#### Option A: Quality only

- Pros: smaller scope, addresses a real problem (extraction reliability)
  without touching document-genre diversity
- Cons: still forces every document through the same chunking strategy
  regardless of actual structure — a lab report would still be chunked as
  if it were a narrative leaflet

#### Option B: Genre only

- Pros: addresses structural diversity across document types
- Cons: ignores extraction-quality variance — a garbled, poorly-OCR'd
  document would still be classified by genre and chunked with
  unreliable, low-confidence section boundaries

#### Option C: Both quality and genre (Selected)

- Pros: covers both real axes of variation independently — a document can
  be simultaneously "a clean lab report" or "a leaflet needing
  remediation," and routing decisions for each axis are made separately
- Cons: largest scope of the three; two independent classification
  outputs and routing paths to design and maintain

### Classification mechanism

#### Option A: Heuristics only

- Pros: cheap, deterministic, easy to test exhaustively — consistent with
  the existing chunker's preference for trusting Unstructured.io's own
  signals over building custom logic
- Cons: brittle against document formats the heuristics were not written
  for; a genuinely novel structure gets misclassified with no recovery
  path

#### Option B: LLM-based only

- Pros: more robust to format variation than fixed heuristics
- Cons: per-document cost and latency at ingestion time for every
  document, including the easy, unambiguous cases that heuristics would
  have handled correctly for free

#### Option C: Hybrid — heuristics first, LLM as fallback (Selected)

- Pros: the common, confident cases are classified for free by the same
  cheap signals already computed during extraction; the LLM is only
  invoked for the genuinely ambiguous cases, where its added robustness is
  actually needed
- Cons: two-stage logic is more complex than either option alone, and
  requires a defined confidence threshold for when heuristics defer to the
  LLM

## Reasoning

Option C was selected on the scope axis because the two variables
(quality, genre) are independent — a document's extraction quality says
nothing about its genre, and vice versa — so collapsing them into a single
classification would conflate two different problems with two different
remediation paths. Restricting scope to only one axis (Options A or B)
would leave the other kind of document silently mishandled: a
poorly-extracted leaflet chunked as if it were reliable, or a lab report
chunked as if it were a narrative document.

Option C was selected on the mechanism axis for the same reason the
existing chunker prefers trusting Unstructured.io's own signals over
custom logic where possible: heuristics computed from information already
produced during extraction cost nothing extra and handle the common case.
The LLM fallback exists specifically for the cases heuristics cannot
confidently resolve, rather than being used as the default path — this
keeps the added robustness without paying its cost on every document.

## Consequences

- A new classification step runs before chunking for every ingested
  document, producing a `(quality, genre)` pair that determines its
  downstream path
- `drug_leaflet` and `clinical_protocol` documents continue through the
  existing section-based chunker; `lab_report` and `unclassified`
  documents are held pending a chunking strategy that does not exist yet
- `needs_remediation` documents are held pending a remediation process
  that is not designed by this ADR — what actually happens to such a
  document (automatic re-OCR, a human review queue, outright rejection) is
  an open question, not resolved here
- The LLM fallback adds a per-document cost and latency at ingestion time,
  not at query time — a different cost profile than the pipeline's
  runtime LLM calls, and less time-sensitive, but still a real cost that
  scales with ingestion volume
- The confidence threshold at which heuristics defer to the LLM fallback
  is not yet specified and needs its own decision once real, varied
  documents are available to calibrate against

## What Would Break If We Changed This

Removing genre classification would force every document — leaflets,
protocols, lab reports, anything else — through the one chunking strategy
designed for narrative, section-structured documents, producing poor
section boundaries for any document that doesn't match that shape.
Removing quality classification would let poorly-extracted documents
proceed straight to chunking and indexing with unreliable section
metadata, silently undermining every downstream retrieval decision
(hybrid search weighting, MMR diversity, confidence gating) that assumes
chunk content and metadata are trustworthy.
