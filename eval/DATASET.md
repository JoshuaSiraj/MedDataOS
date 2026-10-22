# Benchmark Dataset

The benchmark has two parts, both built over the ten synthetic patients created as a
demo in the system's initial version: a **question set** of 100 questions that
exercise routing and citation behavior, and a **conflict set** of 40 cases that
exercise the Knowledge Bus.

---

## 1. Question generation methodology

Every part of the benchmark, the fact inventory, the questions, their gold labels,
and the seeded conflicts, was generated with Claude Opus 4.8. The steps below
describe how.

**Step 1: Fact inventory.** Each of the ten patients comes with a short reference
summary for each of the seven modalities, so there are seventy summaries in total
(for example, an echo summary reads "LVEF 45 percent, mild lateral wall hypokinesis,
trace mitral regurgitation, grade I diastolic dysfunction"). I decomposed each
summary into its individual atomic facts: single, self-contained, checkable
assertions that cannot be usefully split further, such as "ejection fraction 45
percent" or "lateral ischemia on the ECG." Each summary yields roughly three to six
of these, and there are about 288 across all seventy summaries; 288 is simply what
the decomposition produced, not a target. The facts are derived only from the
patients' own findings, which is what guarantees that every question written from
them is answerable from the patient's data, and that every gold answer traces back
to a specific finding.

**Step 2: Writing the questions.** From the inventory I wrote 100 questions at three
levels of reasoning demand plus two kinds of probe:

- *Simple.* One question per selected fact, phrased so the answer lives in exactly
  one modality (for example, "What is the HbA1c?" is answered from labs alone).
  These are spread across all seven modalities and all ten patients.
- *Cross-modal.* For each patient I identified clinically related clusters of facts
  (for example, the signals of ischemia that appear across ECG, echo, notes, and
  labs) and wrote a question whose correct answer draws on several of them at once.
- *Multi-hop.* I took several single-modality questions for one patient and composed
  them into one natural, layered question. The required modalities are the union of
  the source questions, and the source sub-questions are
  stored alongside each item so the gold answer is auditable back to its parts.
  Difficulty here comes from structure, not from contrived phrasing.
- *Probes (10).* Five *no-tool* questions are general or definitional and need no
  patient data, so the correct behavior is to call no agent. Five
  *unavailable-modality* questions remove a modality from the patient's available
  data and then ask about exactly that modality, so the correct behavior is to not
  call it.

**Step 3: Gold labeling.** Each question carries a **required** set (modalities a
correct, complete answer must use) and an **optional** set (modalities
a clinician could reasonably consult, but the answer stands without them; invoking
them is neither rewarded nor penalized). One uniform rule was applied: the clinical
notes are optional by default wherever they are not themselves the answer, since
reading the patient's chart is always reasonable.

**Step 4: Conflict cases.** For the 30 seeded cases I took a real patient's finding
set and replaced exactly one finding with a clinically contradictory variant. The
contradiction is established by clinical domain knowledge (Claude Opus 4.8's), not
looked up externally and not arbitrary: the replacement is chosen to be clinically
inconsistent with the patient's other, unchanged findings. For example, when the ECG
shows lateral ischemia, replacing the echo with "normal function, no wall-motion
abnormality" is a genuine contradiction, since an ischemic territory should show a
matching wall-motion change. Because the inconsistency is introduced deliberately,
the ground truth is known by construction rather than detected, so I simply record
which modality pair conflicts (the gold pair) and how obvious the contradiction is
(a subtlety rating). The 10 clean cases use the patients' unmodified, internally
consistent findings, where the Knowledge Bus should flag nothing.

**Step 5: Balance and freeze.** Questions and conflicts are distributed across all
ten patients and seven modalities, with seeded conflicts spread over a subtlety
gradient and nine distinct modality pairings. A small pilot (10 questions, 2
conflicts) was used to calibrate the grader, after which the set was frozen and run
once.

---

## 2. Question set: composition

100 questions, by reasoning tier:

| Tier | Count | Required modalities per question |
|---|---|---|
| Simple (single modality) | 30 | 1 |
| Probe, no-tool | 5 | 0 (must call nothing) |
| Probe, unavailable-modality | 5 | 0 (must not call the removed one) |
| Cross-modal | 30 | 2 to 4 (avg 2.3) |
| Multi-hop | 30 | 3 to 4 (avg 3.2) |

Questions are spread roughly evenly across the ten patients (9 to 11 each; P0001 has
9, P0002 has 11, the rest 10).

**Required-modality coverage.** How many questions require each modality as part of a
correct answer (a multi-modality question counts once per required modality, so the
column sums to more than 100):

| Modality | Questions requiring it |
|---|---|
| Echocardiogram | 45 |
| ECG | 37 |
| Lab results | 30 |
| Clinical notes | 30 |
| Heart sounds | 24 |
| Medication | 17 |
| Chest X-ray | 12 |

The distribution leans toward echo and ECG and is lighter on chest X-ray and
medication. This reflects the cardiac focus of the ten demo patients rather than a
design choice, and it means the chest X-ray and medication cells rest on fewer
questions.

**Simple-tier targets.** The 30 single-modality questions, by the one modality each
targets:

| Modality | Simple questions |
|---|---|
| Lab results | 8 |
| ECG | 5 |
| Medication | 5 |
| Echocardiogram | 5 |
| Heart sounds | 3 |
| Chest X-ray | 2 |
| Clinical notes | 2 |

**Optional-modality labels.** Modalities marked optional (consultable but not
required) across the set, dominated by clinical notes under the default rule:

| Modality | Times marked optional |
|---|---|
| Clinical notes | 65 |
| Heart sounds | 15 |
| Chest X-ray | 14 |
| ECG | 10 |
| Lab results | 6 |
| Medication | 3 |
| Echocardiogram | 2 |

---

## 3. Conflict set: composition

40 cases for the Knowledge Bus: 10 clean and 30 seeded, three seeded per patient.

**Seeded difficulty**, rated when the contradictory finding was written:

| Subtlety | Count |
|---|---|
| Blatant | 9 |
| Moderate | 13 |
| Subtle | 8 |

**Conflict pairings.** The 30 seeded conflicts span nine distinct modality pairs, so
no single kind of contradiction dominates:

| Conflicting pair | Count |
|---|---|
| Clinical notes and lab results | 7 |
| ECG and echocardiogram | 7 |
| Clinical notes and echocardiogram | 3 |
| Echocardiogram and heart sounds | 4 |
| Chest X-ray and clinical notes | 2 |
| Chest X-ray and echocardiogram | 2 |
| ECG and heart sounds | 2 |
| ECG and lab results | 2 |
| Clinical notes and ECG | 1 |

---

## 4. Labeling reference

- **Required** modalities: a correct, complete answer cannot be given without them.
  These are what the routing recall metric is measured against.
- **Optional** modalities: reasonable to consult, but the answer holds without them;
  invoking them is neither rewarded nor penalized.
- **Gold conflict pair** (seeded cases): the two modalities whose findings
  contradict each other, which the Knowledge Bus is expected to flag.

Every question and conflict is stored as one line of JSON with its labels and, for
multi-hop questions, the sub-questions it was composed from.
