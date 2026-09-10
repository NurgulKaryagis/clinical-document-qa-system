# ADR-008: RAGAS Metric Set and Faithfulness Threshold for CI/CD Deploy Gating

## Status

Accepted

## Context

RAGAS evaluates the pipeline's output against an eval dataset on every
deploy. Several of its metrics are relevant here, covering two different
axes of quality:

- **Generation groundedness**: `faithfulness` breaks a generated answer
  into individual claims and checks each one against the retrieved
  context, reporting the fraction of claims actually supported by that
  context (1.0 = every claim is grounded, 0.0 = the answer is entirely
  unsupported).
- **Retrieval quality**, which itself splits into two distinct failure
  modes:
  - `context_precision` — of the chunks retrieved, how many were actually
    relevant (catches noisy, unfocused retrieval)
  - `context_recall` — of the information actually needed to answer, how
    much was retrieved at all (catches retrieval that silently missed
    something critical)

These are not interchangeable. An answer can score perfectly on
`faithfulness` (no hallucinated claims) while still being dangerously
incomplete, if retrieval never surfaced a critical section in the first
place — the answer only reports on what it was given, not on what was
missing. `context_precision` alone does not catch this either: a retrieval
that returns three irrelevant-but-harmless chunks and misses the one
critical chunk can still score reasonably on precision for the chunks it
did return. Retrieval completeness needs its own metric.

This distinction matters concretely for this project: the MMR and Rerank
configuration was deliberately tuned to favor retrieving chunks from
multiple sections of a document (e.g., Dosage and Contraindications
together) rather than several near-duplicate chunks from one section, on
the reasoning that a missing section is a worse failure than an
imperfectly-relevant one. Without a metric that measures whether that
retrieval actually happens, that design goal has no way to be verified —
faithfulness and context_precision alone would not detect a regression in
it.

Two further RAGAS metrics were considered and set aside for now:
`answer_relevancy` (whether the answer addresses the question asked, not
just whether it's grounded) and `answer_correctness` (comparison against a
full reference answer). Both address a different failure mode — wrong or
off-topic answers — from the retrieval-completeness gap this project is
scoping toward. `answer_correctness` in particular requires a reference
answer for every eval question, a substantially larger authoring effort
than referencing what should be retrieved.

The questions this ADR resolves: which of these metrics should run on
every deploy, which one(s) should be able to block a deploy outright, and
at what threshold.

A high faithfulness threshold's apparent cost — CI blocking more often —
is not a development-friction tradeoff to weigh against safety, since
anything that reaches deploy reaches the actual answers clinicians see.
Where a high threshold could genuinely cause a problem is if it blocks
deploys due to *measurement noise* rather than a real quality regression:
with a small or synthetic eval dataset, a single borderline result can
swing the average score enough to trigger a false block. That risk is not
an argument for a lower threshold — it is an argument that the eval
dataset itself must be strong enough for the threshold to mean something.
Loosening the threshold to compensate for a weak eval set would hide the
real problem instead of fixing it.

## Decision

Run three metrics on every deploy: `faithfulness`, `context_precision`,
and `context_recall`. Only `faithfulness` gates deploy: block deploy in CI
if the eval dataset's mean `faithfulness` score falls below `0.85`.
`context_precision` and `context_recall` are computed and logged as
tracked trends, not blocking gates.

This is only meaningful if the eval dataset itself meets the following
criteria, which must be true before this ADR's threshold can be trusted:

- **Size**: large enough that adding or removing any single eval question
  changes the mean score by no more than ~1-2% — a rough guide is on the
  order of 150-200+ questions, not a handful
- **Real documents, not synthetic ones**: built from the actual clinical
  document corpus (drug leaflets, protocols), since real documents carry
  ambiguities and formatting quirks that synthetic questions do not
  reproduce
- **Section diversity**: includes questions answerable from a single
  section and questions that require combining multiple sections (e.g.
  Dosage + Contraindications) — the property `context_recall` is meant to
  verify
- **Negative cases**: includes questions the system should decline to
  answer (drugs not in the corpus, out-of-scope questions), so the
  confidence threshold's calibration is actually exercised, not just the
  answerable cases
- **Reference retrieval targets**: each eval question needs a reference of
  what information should be retrievable, so `context_recall` can be
  computed, not just a question and an expected answer
- **Measurement stability**: the same eval set, run against unchanged
  code, should produce a stable score (RAGAS's own faithfulness judge is
  itself LLM-based and carries some variance) — a large score swing on
  unchanged code indicates the measurement is unreliable, not that the
  system changed
- **Grows from real usage**: once in production, answers a clinician flags
  as wrong should be added to the eval set as regression cases over time

## Options Considered

### Metric set

#### Option A: `faithfulness` only

- Pros: simplest, one number to reason about
- Cons: no visibility into retrieval quality at all; a retrieval
  regression could go completely undetected as long as the LLM stays
  faithful to whatever (possibly wrong or incomplete) context it receives

#### Option B: `faithfulness` + `context_precision` only

- Pros: adds visibility into retrieval noise
- Cons: still cannot detect the specific failure mode this project's
  retrieval design (ADR-005/006) was built to prevent — a missing section
  never surfaces as a precision problem, since precision only evaluates
  chunks that were actually retrieved

#### Option C: `faithfulness` + `context_precision` + `context_recall` (Selected)

- Pros: covers both retrieval failure modes (noisy retrieval and
  incomplete retrieval), and `context_recall` specifically verifies
  whether the diversity-favoring retrieval design is achieving its actual
  goal
- Cons: requires eval dataset entries to include a reference of what
  should be retrieved, more authoring effort than Option A or B

### Faithfulness threshold value

#### Option A: Low threshold (~0.6-0.7)

- Pros: CI rarely blocks a deploy
- Cons: allows a meaningfully more hallucination-prone version of the
  system to reach production; provides little real protection

#### Option B: Moderate threshold (~0.75-0.8)

- Pros: a common default in general-purpose RAG projects
- Cons: not reasoned for this domain specifically; a generic default has
  no stronger basis than that it is commonly used elsewhere

#### Option C: High threshold (~0.85-0.9) (Selected, 0.85)

- Pros: consistent with the same asymmetry behind every other retrieval
  and caching decision in this project — a wrong or unsupported answer is
  a worse failure than blocking a deploy; deploy gating is the last
  automated checkpoint before a change reaches real answers, with no later
  stage able to catch a faithfulness regression once shipped
- Cons: only trustworthy if the eval dataset meets the criteria above; on
  a weak eval dataset this threshold produces false blocks from
  measurement noise, not real signal

## Reasoning

For the metric set: Option A leaves retrieval quality completely
unmeasured. Option B measures retrieval noise but not retrieval
completeness — and completeness is exactly the property this project's
retrieval tuning was designed around, so leaving it unmeasured would mean
a real design goal has no way to be verified or protected against
regression. Option C closes that gap directly. `answer_relevancy` and
`answer_correctness` were not selected because they address a different
failure mode (wrong or off-topic answers, not incomplete retrieval) and,
for `answer_correctness`, require reference-answer authoring this project
has not committed to.

For the threshold: low and moderate options trade safety for a lower rate
of friction, in a domain where the friction side (a blocked deploy, or a
re-run of CI) is recoverable and the safety side (a hallucination-prone
version reaching a clinician) is not. The high threshold's real cost is
exposure to eval-set measurement noise, which is a property of the eval
dataset, not of the threshold — the correct response to that risk is
making the eval dataset strong enough (per the criteria in Decision), not
weakening the safety bar to compensate for a weak dataset. Only
`faithfulness` gates deploy, rather than also gating on
`context_precision`/`context_recall`, to avoid managing multiple
independent CI failure conditions when the retrieval metrics are better
used as trends to investigate than as hard pass/fail gates at this stage.

## Consequences

- No deploy proceeds if mean faithfulness falls below 0.85, regardless of
  what other checks pass
- `context_precision` and `context_recall` are computed and logged on
  every deploy; a sustained downward trend in either is a signal to
  investigate retrieval quality, not an automatic CI failure
- The eval dataset's adequacy (size, real-document basis, section
  diversity, negative cases, reference retrieval targets, measurement
  stability) becomes a prerequisite for this ADR's threshold to be
  meaningful
- `0.85` is a reasoned starting point, not a value validated against this
  project's actual score distribution, since no real corpus or eval
  pipeline exists yet
- `answer_relevancy`/`answer_correctness` remain open for a future
  decision if a specific failure mode (e.g., observed off-topic or
  factually wrong-but-faithful answers) motivates adding them

## What Would Break If We Changed This

Dropping `context_recall` would remove the only signal that would catch
the retrieval-diversity design (MMR/Rerank tuning) silently regressing —
a future change to those parameters could degrade completeness without
affecting faithfulness or precision, and the failure would only surface
later, in production, rather than in CI. Lowering the faithfulness
threshold toward the low or moderate options would remove the project's
only automated, CI-enforced defense against a faithfulness regression
reaching production. Running this threshold against a weak eval dataset
(rather than fixing the dataset) would produce a check that either blocks
deploys on noise or passes deploys it shouldn't, without anyone being able
to tell which is happening from the number alone.
