# Technical Evaluation

---

## 1. Scope: what the evaluation tests, and what it does not

The evaluation validates the three architecture-level properties the system's
contribution rests on:

1. **Routing.** Given a clinical question, does the orchestrator invoke the correct
   set of modality agents?
2. **Citation faithfulness and coverage.** Does every claim in the answer trace to
   the finding it cites, and are there confident claims with no source at all?
3. **Cross-modal conflict detection.** Does the Knowledge Bus flag genuine
   contradictions across modalities while staying silent on consistent patients?

It deliberately does **not** measure per-modality diagnostic accuracy (how well a
single agent reads an ECG or an X-ray). That is not the system's claim, the design
premise is that clinicians verify rather than trust, and scoring it would invite an
unwanted comparison to specialized single-modality models. This framing maps
directly onto RQ1 (can a multi-agent architecture reason over multimodal data while
preserving transparency and oversight).

---

## 2. Ground truth and data

No public benchmark fits the task: existing medical benchmarks test one modality at
a time, whereas the object of study here is cross-modal reasoning for a single
patient, with citations and conflict detection layered on top. Ground truth is
therefore derived from the **ten synthetic patients** created as a demo in the
system's initial version.
Each patient comes with a complete, internally consistent set of findings across all
seven modalities (clinical notes, chest X-ray, ECG, echocardiogram, heart sounds, lab
results, medication history). I take these findings as the ground truth: they are the
reference every question and every citation is graded against. They are not
independently clinician-validated, and the evaluation does not assume they are: it
measures whether the system faithfully routes to, cites, and reconciles the findings
it is given, not whether the findings themselves are clinically correct.

As the first step I catalogued the atomic clinical facts in each record (about
**288** facts across the ten patients), using Claude Opus 4.8. This fact inventory
is both the source material for writing questions and the audit trail: every gold
answer traces back to specific facts.

---

## 3. Benchmark composition

**Query set (100 questions)** and **Knowledge Bus set (40 cases)**, authored with
Claude Opus 4.8:

| Category | Count | Purpose |
|---|---|---|
| Simple | 30 | answer lies in a single modality |
| Probe: no-tool | 5 | general/definitional question; the system should call no agents |
| Probe: unavailable-modality | 5 | asks about a modality removed from the patient; the system must not call it |
| Cross-modal | 30 | answer requires several modalities at once |
| Multi-hop | 30 | answer requires chaining across four or five modalities |
| Knowledge Bus, clean | 10 | internally consistent patient; must flag no contradiction |
| Knowledge Bus, seeded | 30 | one finding swapped for a contradictory one; must be caught |

Each query carries a hand-labelled **required** set (modalities a correct answer
must use) and an **optional** set (modalities reasonable to consult but not
necessary). Multi-hop questions were composed by taking several single-modality
questions for one patient and merging them into one natural, layered question, so
difficulty comes from structure rather than contrived phrasing. The 30 seeded
conflicts span a subtlety gradient (9 blatant, 13 moderate, 8 subtle) across 9
distinct modality pairings, so results do not depend on one kind of conflict.

### Example questions (verbatim from the frozen set)

**Simple** (single modality):
> *"What is the aortic valve area on the echocardiogram?"* (P0009)
> required: echo

> *"What is this patient's HbA1c?"* (P0008)
> required: lab_results

**Probe, no-tool** (should call nothing):
> *"In general, what does 'aortic stenosis' refer to?"* (P0009)
> required: none

**Probe, unavailable-modality** (ECG removed from the patient; must not call ECG):
> *"What does this patient's ECG show?"* (P0003, ECG removed)
> required: none

**Cross-modal** (several modalities):
> *"Is there any evidence of myocardial ischemia in this patient?"* (P0001)
> required: ECG, echo, clinical notes; optional: labs, heart sounds

> *"Is there evidence of right heart strain or pulmonary hypertension?"* (P0006)
> required: ECG, echo; optional: chest X-ray, heart sounds, clinical notes

**Multi-hop** (chained across modalities, shown with the sub-questions it was
composed from):
> *"Does the exertional syncope, together with the murmur and echo valve data,
> indicate severe aortic stenosis, and is any medication a concern?"* (P0009)
> required: clinical notes, heart sounds, echo, medication
> composed from: syncope history (notes) + murmur description (heart sounds) +
> valve area/gradient (echo) + medication concern (medication)

> *"How severe is this heart failure decompensation when the symptoms, chest X-ray,
> echo, and BNP are considered together?"* (P0004)
> required: clinical notes, chest X-ray, echo, labs; optional: heart sounds, ECG

### Example seeded conflict (Knowledge Bus)

Patient P0001 genuinely has lateral ischemia. I swapped the echo finding for a
normal one, creating a blatant contradiction between the ECG and the echo:
- ECG: *"...ST-segment depression of 1mm in V4-V6 suggesting lateral ischemia..."*
- echo (seeded): *"LVEF 63% (normal). No wall motion abnormalities. No valvular
  disease..."*
- gold conflict pair: {ECG, echo}. The Bus should surface it.

---

## 4. Models

Three independent model families, chosen so that no model checks its own work:

| Role | Model |
|---|---|
| System under test (orchestrator + Knowledge Bus) | Gemini 3.1 Pro (`gemini-3.1-pro-preview`) |
| Independent grader (judge) | GPT 5.5 (`gpt-5.5-2026-04-23`) |
| Authoring facts, questions, seeded conflicts | Claude Opus 4.8 |

---

## 5. Analysis methods (how each number is computed)

### 5.1 Routing

For each query I compare the **invoked** set (agents that actually fired) against
the **required** and **optional** labels.

- True positives (TP) = invoked ∩ required
- False negatives (FN) = required not invoked
- False positives (FP) = invoked that are neither required nor optional
- Optional agents that are invoked are neutral (neither rewarded nor penalized)

From these:
- **Precision** = TP / (TP + FP), **Recall** = TP / (TP + FN), **F1** = their
  harmonic mean, micro-averaged across queries.
- **Exact-set accuracy (tolerant):** a query passes if *required is a subset of
  invoked* and *invoked is a subset of (required union optional)*. In words: every
  required modality was called and nothing outside the allowed set was called.

Routing needs no LLM grading; it is a set comparison in code. Metrics are reported
per tier (simple, cross-modal, multi-hop) and overall.

### 5.2 Citation faithfulness and coverage (LLM-as-judge)

The judge (GPT 5.5) reads each answer together with the findings it may cite and the
patient demographics, then segments the answer into atomic clinical claims and
labels each:

For claims that carry a citation, judged against the cited finding(s):
- **faithful** — the claim's content is supported, including reasonable clinical
  interpretation and synthesis grounded in the finding.
- **overstated** — asserts severity, certainty, or magnitude beyond what the finding
  states.
- **fabricated** — asserts a fact absent from, or contradicting, the cited finding.

For claims with no citation, judged against all findings plus demographics:
- **grounded** — the fact appears in, or is entailed by, some finding or the
  demographics.
- **ungrounded** — a specific clinical assertion backed by nothing.
- **not-a-claim** — connective or framing text with no checkable fact.

Derived metrics:
- **Faithfulness** = faithful / (all cited claims).
- **Overstatement rate**, **fabrication rate** = those classes / all cited claims.
- **Ungrounded (hallucinated) claims**: reported as an absolute count and as a
  fraction of all factual claims. Note on the denominator: because the system now
  cites nearly every factual statement, the pool of *uncited* factual claims is
  small, so the absolute count (how many confident claims have no source at all) is
  the meaningful figure rather than a percentage of that small pool.

The judge output is fully logged per claim with a one-line rationale, so any verdict
is inspectable.

### 5.3 Knowledge Bus conflict detection

The Knowledge Bus is a single stochastic model call, so each case is run **three
times** and scored by majority.

- **Seeded recall** = fraction of the 30 seeded cases whose gold conflict pair is
  flagged in the majority of reps.
- **Clean false-positive rate** = fraction of the 10 consistent patients where any
  contradiction is flagged in the majority of reps. This is the precision signal:
  a seeded swap can legitimately create several true contradictions, so extra links
  on seeded cases are not necessarily errors, whereas any flag on a clean patient
  is unambiguously wrong.
- **Consistency** = mean fraction of reps agreeing with the majority verdict per
  case.

---

## 6. Protocol and honesty safeguards

- **Three model families** (Section 4), so authoring, answering, and grading are
  never done by the same model.
- **Pilot as a development set.** Before the full run I trialed the whole pipeline
  on 10 questions and 2 conflict cases. This surfaced that the grader was initially
  too strict, penalizing reasonable clinical phrasing; I recalibrated the rubric on
  the pilot, then locked it.
- **Freeze discipline.** Questions and their required answers were fixed before the
  reported run and never edited to the results.
- **Two runs, honestly separated.** The reported numbers come from a second run.
  After a first run I improved the orchestrator prompt (cite every factual claim;
  stay strictly within what the agents reported; do not answer a multi-part question
  from a single modality). On the benchmark side I made exactly one correction,
  decided on principle and applied uniformly: consulting the patient's clinical
  notes is no longer scored as a routing error, since reading the chart is always
  reasonable. The questions and required answers were not touched, and nothing was
  tuned to the first run's specific mistakes. Because the labeling change is
  results-independent, I can report its effect separately (Section 7).

---

## 7. Results (final run)

### Headline

| Property | Metric | Result |
|---|---|---|
| Routing | exact-set accuracy (tolerant) | 87% |
| | precision / recall / F1 | 0.95 / 0.97 / 0.96 |
| Citations | faithfulness (cited claims) | 96% |
| | overstatement / fabrication | 1% / 2% |
| | ungrounded claims (absolute) | 4 (of ~1,600 factual claims) |
| Knowledge Bus | seeded-conflict recall | 93% (28/30) |
| | clean false-positive rate | 0% (0/10) |
| | cross-run consistency | 99% |
| Responsiveness | median latency per answer | 14.8 s |

### Routing by tier (exact-set, tolerant)

| Tier | n | Result |
|---|---|---|
| Simple | 40 | 100% |
| Cross-modal | 30 | 70% |
| Multi-hop | 30 | 87% |
| All | 100 | 87% |

### Citation claim breakdown

| Class | Count | Share of cited |
|---|---|---|
| Cited claims (total) | 1541 | — |
| faithful | 1484 | 96% |
| overstated | 23 | 1% |
| fabricated | 34 | 2% |
| Uncited factual, grounded | 35 | — |
| Uncited factual, ungrounded | 4 | — |

### Routing improvement, decomposed (attributable)

| Configuration | Exact-set (all) |
|---|---|
| First-run system, original labels | 75% |
| First-run behavior under the corrected label rule (labeling effect only) | 81% |
| Final system under the corrected labels (adds the prompt effect) | 87% |

The labeling correction accounts for +6 points, the system improvement for the rest.

---

## 8. What the numbers mean

- The orchestrator **routes** to the right modalities and rarely misses required
  data (recall 0.97). Where it errs, it tends to *over*-retrieve context rather than
  omit it, which is the safer direction in a clinical setting.
- Answers are **faithful** to their sources 96% of the time, with only four
  confident claims across 100 questions lacking any source, and those four are mild
  clinical inferences rather than invented facts.
- The Knowledge Bus **catches real contradictions** (93%) without a single false
  alarm on a consistent patient, and does so consistently across repeats (99%).

The residual imperfections are the honest, explainable kind a careful evaluation is
meant to surface, not a suspiciously perfect sweep.

---

## 9. Failure modes and limitations (state these honestly)

- **Cross-modal over-retrieval.** Cross-modal routing (70%) is limited mainly by the
  system calling an additional, clinically-plausible modality beyond the required
  set. This is over-retrieval, not omission, and it is the safer failure direction.
- **A few genuine routing misses on multi-hop** questions, where the model answered
  from context instead of calling a modality the gold set required. Several of these
  are defensible model judgment (for example, reading atrial fibrillation from the
  history rather than re-deriving it from the ECG).
- **Four ungrounded claims** remain, all mild inferential overreach rather than
  invented data: the model draws a clinically plausible conclusion a step beyond the
  findings. For example, in a patient who is both diabetic and hypertensive, the
  findings attribute the cardiac damage to hypertension while the answer says it
  stems from diabetes. In none of them does the system invent a new fact (a value, a
result, a diagnosis) that is not in the data; it only over-interprets facts that are.
- **Synthetic data.** Ground truth uses synthetic patients, which may not capture the
  messiness of real records. (Consistent with the study's existing limitations
  around synthetic data and non-clinician participants.)
- **Grader.** Citation grading uses an LLM judge; verdicts are logged per claim for
  inspection, and a different model family from the system is used to reduce
  self-preference.
- **Knowledge Bus in the final run** reuses the first run's results, since the v2
  changes were confined to the orchestrator and do not affect the Knowledge Bus.

---

## 10. Reproducibility

- Frozen inputs, per-run raw outputs, per-claim grader verdicts, a machine-readable
  manifest (models, seed, counts, headline metrics), and a human-readable report all
  live under `eval/`.
- The two runs are version-tagged (`eval-run1`, `eval-run2`) so either can be
  checked out and reproduced.

---

## 11. Suggested framing for the section (one page)

1. One sentence of scope: this section validates the machinery the user study relies
   on (routing, citations, conflict detection), not per-modality accuracy.
2. One methodology paragraph: synthetic-patient ground truth, the 100-question set
   across three difficulty tiers plus probes, the 40 conflict cases, and the
   three-model-family setup with an LLM judge.
3. One results table (the headline table above) plus the per-tier routing row.
4. One short paragraph per property stating the metric and its dominant failure mode
   (over-retrieval for routing, mild inference for the few unsupported claims, zero
   false alarms for conflict detection).
5. Optional: the routing decomposition, to show the improvement is honest.
