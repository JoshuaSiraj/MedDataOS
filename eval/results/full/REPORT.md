# MedDataOS Technical Evaluation — `full` run

- System under test: `gemini-3.1-pro-preview`
- Judge: `gpt-5.5-2026-04-23` (seed 7)
- Date: 2026-07-24
- Queries: 100 | judged for citations: 91 | KB sets: 40
- Median end-to-end latency: 11.77s

## Routing

| tier | n | exact (tolerant) | precision | recall | F1 |
|---|---|---|---|---|---|
| simple | 40 | 88% | 0.83 | 1.00 | 0.91 |
| cross_modal | 30 | 57% | 0.81 | 0.96 | 0.88 |
| multi_hop | 30 | 77% | 0.98 | 0.95 | 0.96 |
| ALL | 100 | 75% | 0.89 | 0.96 | 0.92 |

**Routing failures (exact-tolerant misses):**

- `S10` (simple): extra ['clinical_notes'] — required=['echo'], invoked=['clinical_notes', 'echo']
- `S15` (simple): extra ['ecg', 'lab_results'] — required=['clinical_notes'], invoked=['clinical_notes', 'ecg', 'lab_results']
- `S21` (simple): extra ['clinical_notes'] — required=['medication'], invoked=['clinical_notes', 'medication']
- `S29` (simple): extra ['clinical_notes'] — required=['echo'], invoked=['clinical_notes', 'echo']
- `P08` (simple): extra ['clinical_notes'] — required=[], invoked=['clinical_notes']
- `C05` (cross_modal): extra ['chest_xray', 'medication'] — required=['clinical_notes', 'ecg'], invoked=['chest_xray', 'clinical_notes', 'ecg', 'lab_results', 'medication']
- `C06` (cross_modal): extra ['chest_xray', 'clinical_notes'] — required=['ecg', 'echo', 'heart_sounds'], invoked=['chest_xray', 'clinical_notes', 'ecg', 'echo', 'heart_sounds', 'lab_results']
- `C07` (cross_modal): extra ['lab_results'] — required=['ecg', 'echo', 'heart_sounds'], invoked=['chest_xray', 'clinical_notes', 'ecg', 'echo', 'heart_sounds', 'lab_results']
- `C09` (cross_modal): extra ['chest_xray'] — required=['echo', 'heart_sounds'], invoked=['chest_xray', 'echo', 'heart_sounds']
- `C11` (cross_modal): extra ['medication'] — required=['ecg', 'heart_sounds'], invoked=['clinical_notes', 'ecg', 'heart_sounds', 'medication']
- `C12` (cross_modal): extra ['clinical_notes'] — required=['echo', 'heart_sounds'], invoked=['clinical_notes', 'echo', 'heart_sounds']
- `C13` (cross_modal): missed ['echo']; extra ['lab_results'] — required=['ecg', 'echo'], invoked=['clinical_notes', 'ecg', 'lab_results']
- `C14` (cross_modal): extra ['ecg'] — required=['echo', 'lab_results'], invoked=['clinical_notes', 'ecg', 'echo', 'lab_results']
- `C16` (cross_modal): extra ['clinical_notes'] — required=['ecg', 'echo'], invoked=['chest_xray', 'clinical_notes', 'ecg', 'echo', 'heart_sounds']
- `C21` (cross_modal): missed ['chest_xray']; extra ['clinical_notes'] — required=['chest_xray', 'echo'], invoked=['clinical_notes', 'ecg', 'echo']
- `C22` (cross_modal): missed ['heart_sounds']; extra ['lab_results'] — required=['ecg', 'echo', 'heart_sounds'], invoked=['chest_xray', 'clinical_notes', 'ecg', 'echo', 'lab_results']
- `C29` (cross_modal): extra ['ecg'] — required=['clinical_notes', 'echo'], invoked=['clinical_notes', 'ecg', 'echo']
- `C30` (cross_modal): extra ['echo'] — required=['clinical_notes', 'medication'], invoked=['clinical_notes', 'echo', 'lab_results', 'medication']
- `M01` (multi_hop): missed ['clinical_notes'] — required=['clinical_notes', 'ecg', 'echo', 'lab_results'], invoked=['ecg', 'echo', 'lab_results']
- `M05` (multi_hop): extra ['lab_results'] — required=['clinical_notes', 'ecg', 'echo'], invoked=['clinical_notes', 'ecg', 'echo', 'lab_results']
- `M07` (multi_hop): missed ['clinical_notes'] — required=['clinical_notes', 'ecg', 'echo', 'heart_sounds'], invoked=['ecg', 'echo', 'heart_sounds']
- `M09` (multi_hop): extra ['chest_xray'] — required=['clinical_notes', 'echo', 'heart_sounds'], invoked=['chest_xray', 'clinical_notes', 'echo', 'heart_sounds']
- `M11` (multi_hop): missed ['ecg'] — required=['ecg', 'lab_results', 'medication'], invoked=['clinical_notes', 'lab_results', 'medication']
- `M12` (multi_hop): missed ['clinical_notes'] — required=['clinical_notes', 'echo', 'heart_sounds'], invoked=['echo', 'heart_sounds']
- `M28` (multi_hop): missed ['clinical_notes'] — required=['clinical_notes', 'ecg', 'echo'], invoked=['ecg', 'echo']

## Citations

- cited claims: **855** — faithful 785, overstated 26, fabricated 44
- **faithfulness: 92%**  (overstatement 3%, fabrication 5%)
- uncited factual claims: 620 — grounded 546, ungrounded 74
- **hallucination rate: 12%**  (ungrounded / uncited factual)

**Example flagged claims:**

- [ungrounded] The cardiac silhouette appears completely normal in contour.
- [fabricated] Maria Lopez presented as the patient.
- [fabricated] The echocardiographic findings correlate directly with her recent clinical deterioration.
- [ungrounded] The combination of worsened ejection fraction, decreased urine output, severe volume overload, and chronic kid
- [ungrounded] Decompensated Heart Failure
- [ungrounded] The patient has a severe fluid overload state.

## Knowledge Bus

- seeded recall (majority): 28/30 = 93%
- clean false-positive rate: 0/10 = 0%
- mean consistency across reps: 99%
