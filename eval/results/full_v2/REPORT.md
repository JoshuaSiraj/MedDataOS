# MedDataOS Technical Evaluation — `full_v2` run

- System under test: `gemini-3.1-pro-preview`
- Judge: `gpt-5.5-2026-04-23` (seed 7)
- Date: 2026-07-24
- Queries: 100 | judged for citations: 92 | KB sets: 40
- Median end-to-end latency: 14.81s

## Routing

| tier | n | exact (tolerant) | precision | recall | F1 |
|---|---|---|---|---|---|
| simple | 40 | 100% | 1.00 | 1.00 | 1.00 |
| cross_modal | 30 | 70% | 0.88 | 0.97 | 0.92 |
| multi_hop | 30 | 87% | 0.99 | 0.97 | 0.98 |
| ALL | 100 | 87% | 0.95 | 0.97 | 0.96 |

**Routing failures (exact-tolerant misses):**

- `C02` (cross_modal): missed ['medication'] — required=['lab_results', 'medication'], invoked=['clinical_notes', 'lab_results']
- `C05` (cross_modal): extra ['echo', 'medication'] — required=['clinical_notes', 'ecg'], invoked=['clinical_notes', 'ecg', 'echo', 'lab_results', 'medication']
- `C07` (cross_modal): extra ['lab_results'] — required=['ecg', 'echo', 'heart_sounds'], invoked=['chest_xray', 'clinical_notes', 'ecg', 'echo', 'heart_sounds', 'lab_results']
- `C09` (cross_modal): extra ['chest_xray'] — required=['echo', 'heart_sounds'], invoked=['chest_xray', 'echo', 'heart_sounds']
- `C13` (cross_modal): missed ['echo']; extra ['lab_results'] — required=['ecg', 'echo'], invoked=['clinical_notes', 'ecg', 'heart_sounds', 'lab_results']
- `C14` (cross_modal): extra ['ecg'] — required=['echo', 'lab_results'], invoked=['clinical_notes', 'ecg', 'echo', 'lab_results']
- `C19` (cross_modal): extra ['echo'] — required=['clinical_notes', 'ecg', 'heart_sounds'], invoked=['clinical_notes', 'ecg', 'echo', 'heart_sounds']
- `C22` (cross_modal): extra ['lab_results'] — required=['ecg', 'echo', 'heart_sounds'], invoked=['chest_xray', 'clinical_notes', 'ecg', 'echo', 'heart_sounds', 'lab_results']
- `C29` (cross_modal): extra ['ecg'] — required=['clinical_notes', 'echo'], invoked=['clinical_notes', 'ecg', 'echo']
- `M07` (multi_hop): missed ['clinical_notes'] — required=['clinical_notes', 'ecg', 'echo', 'heart_sounds'], invoked=['ecg', 'echo', 'heart_sounds']
- `M09` (multi_hop): extra ['chest_xray'] — required=['clinical_notes', 'echo', 'heart_sounds'], invoked=['chest_xray', 'clinical_notes', 'ecg', 'echo', 'heart_sounds']
- `M11` (multi_hop): missed ['ecg'] — required=['ecg', 'lab_results', 'medication'], invoked=['clinical_notes', 'lab_results', 'medication']
- `M28` (multi_hop): missed ['clinical_notes'] — required=['clinical_notes', 'ecg', 'echo'], invoked=['ecg', 'echo']

## Citations

- cited claims: **1541** — faithful 1484, overstated 23, fabricated 34
- **faithfulness: 96%**  (overstatement 1%, fabrication 2%)
- uncited factual claims: 39 — grounded 35, ungrounded 4
- **hallucination rate: 10%**  (ungrounded / uncited factual)

**Example flagged claims:**

- [fabricated] The cardiac silhouette has no concerning features.
- [fabricated] The patient has worsening cardiac function correlating with the current presentation.
- [fabricated] There is multi-modality evidence of myocardial ischemia.
- [fabricated] Grade I diastolic dysfunction is a frequent consequence of chronic hypertension.
- [overstated] Laboratory results further confirm an acute bacterial etiology.
- [overstated] An echocardiogram further rules out a primary cardiac origin.

## Knowledge Bus

- seeded recall (majority): 28/30 = 93%
- clean false-positive rate: 0/10 = 0%
- mean consistency across reps: 99%
