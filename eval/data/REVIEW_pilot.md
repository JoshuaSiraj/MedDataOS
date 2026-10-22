# Pilot Review Sheet
Approve or correct each gold label. This locks question style, gold-set philosophy, and schema before the full set.

## Queries (10)
### Q01 — simple
- **Patient:** P0009
- **Query:** What is this patient's aortic valve area and mean gradient?
- **Gold agents:** ['echo']
- **Rationale:** AVA 0.7 cm2 / mean gradient 52 are echo-only quantitative facts (P0009 echo).

### Q02 — simple
- **Patient:** P0001
- **Query:** What is this patient's most recent HbA1c?
- **Gold agents:** ['lab_results']
- **Rationale:** HbA1c 7.2% is a lab value only (P0001 lab_results).

### Q03 — simple — probe: no_tool
- **Patient:** P0003
- **Query:** In general, what does left ventricular ejection fraction measure?
- **Gold agents:** (none — should call no tools)
- **Rationale:** Definitional question answerable from general knowledge; no agent should fire.

### Q04 — simple — probe: unavailable_modality
- **Patient:** P0003
- **Query:** What did this patient's echocardiogram show about LV function?
- **Gold agents:** (none — should call no tools)
- **Stripped modalities:** ['echo']
- **Rationale:** Echo removed from data_dates; prompt says only call available modalities, so echo must NOT fire.

### Q05 — cross_modal
- **Patient:** P0001
- **Query:** Is there any evidence of myocardial ischemia in this patient?
- **Gold agents:** ['ecg', 'echo', 'clinical_notes']
- **Optional (no penalty):** ['lab_results', 'heart_sounds']
- **Rationale:** Ischemia signal spans ECG (ST-dep V4-V6), echo (lateral hypokinesis), notes (exertional angina); troponin/BNP optional supporting.

### Q06 — cross_modal
- **Patient:** P0004
- **Query:** Assess this patient's volume status and heart failure severity.
- **Gold agents:** ['clinical_notes', 'chest_xray', 'echo', 'lab_results']
- **Optional (no penalty):** ['heart_sounds', 'ecg']
- **Rationale:** HF severity: notes (orthopnea/edema), CXR (congestion/effusions), echo (EF 25%), labs (BNP 1840); S3/AFib optional.

### Q07 — cross_modal
- **Patient:** P0006
- **Query:** Is there evidence of right heart strain or pulmonary hypertension?
- **Gold agents:** ['ecg', 'echo']
- **Optional (no penalty):** ['chest_xray', 'heart_sounds']
- **Rationale:** RV strain: ECG (P pulmonale, RAD, RV strain) + echo (RV dilation, RVSP 42, D-sign); CXR hyperinflation and loud P2 optional.

### Q08 — multi_hop
- **Patient:** P0009
- **Query:** This patient has had exertional syncope. What do the murmur and valve findings point to, and is any current medication a concern for that diagnosis?
- **Gold agents:** ['clinical_notes', 'heart_sounds', 'echo', 'medication']
- **Composed from:**
    - What is the cause of this patient's exertional syncope? (notes)
    - Describe the systolic murmur. (heart_sounds)
    - What is the aortic valve area and gradient? (echo)
    - Are any current medications a concern here? (medication)
- **Rationale:** Severe AS chain: syncope (notes) + 4/6 murmur to carotids (heart_sounds) + AVA 0.7 (echo) + amlodipine caution in severe AS (medication).

### Q09 — multi_hop
- **Patient:** P0008
- **Query:** How well controlled is this patient's diabetes, is there evidence of cardiac end-organ damage, and does the medication regimen address the cardiorenal risk?
- **Gold agents:** ['lab_results', 'ecg', 'echo', 'medication']
- **Optional (no penalty):** ['clinical_notes', 'heart_sounds']
- **Composed from:**
    - What is the HbA1c and renal status? (lab_results)
    - Is there LVH or strain on the ECG? (ecg)
    - Does the echo show hypertensive cardiac changes? (echo)
    - Does the medication list cover cardiorenal protection? (medication)
- **Rationale:** DM control (HbA1c 10.2, ACR 280) + LVH strain (ecg) + concentric LVH/diastolic dysfx (echo) + SGLT2/GLP-1 gap (medication).

### Q10 — multi_hop
- **Patient:** P0010
- **Query:** What do the ECG and echocardiogram tell us about this patient's prior heart attack, and is the current antiplatelet regimen appropriate?
- **Gold agents:** ['ecg', 'echo', 'medication']
- **Optional (no penalty):** ['clinical_notes']
- **Composed from:**
    - What does the ECG show of the prior infarct? (ecg)
    - What is the EF and wall motion? (echo)
    - Is the antiplatelet regimen appropriate? (medication)
- **Rationale:** Post-anterior STEMI: Q waves V1-V3 (ecg) + EF 42% anterior hypokinesis (echo) + DAPT aspirin+clopidogrel 9mo remaining (medication).

## Knowledge Bus sets (2)
### KB01 — clean — base P0003
- **Gold:** no contradictions (clean)
- **Rationale:** Healthy wellness exam; all modalities internally consistent (normal). Bus must flag NO contradictions.
- **Findings handed to the Bus:**
    - `clinical_notes`: 45yo male presenting for annual wellness examination with no acute complaints. Reports mild exercise intoleran...
    - `chest_xray`: No acute cardiopulmonary abnormality. Lung fields clear bilaterally, no infiltrates, consolidation, or effusio...
    - `ecg`: Normal sinus rhythm at 74 bpm. Normal axis. PR interval 156ms (normal). QRS duration 86ms (normal). No ST-segm...
    - `echo`: Normal left ventricular size and function, LVEF 60%. No wall motion abnormalities. Normal diastolic function. ...
    - `heart_sounds`: S1 and S2 normal intensity and splitting. Regular rate and rhythm at 74 bpm. No murmurs, gallops, or rubs. No ...
    - `lab_results`: CBC within normal limits. WBC 6.8 x10³/µL. Hemoglobin 14.6 g/dL. BMP normal: sodium 139 mEq/L, creatinine 0.9 ...
    - `medication`: Active medications: Sertraline 50mg daily (generalized anxiety disorder). No cardiac medications. Daily multiv...

### KB02 — seeded — base P0001
- **Gold conflict pair:** ['ecg', 'echo']
- **Rationale:** Echo swapped to fully normal LV function, contradicting the ECG's lateral ischemia (ST-dep V4-V6) and lateral-territory story.
- **Findings handed to the Bus:**
    - `clinical_notes`: 58yo male presenting with 2-3 week history of exertional substernal chest pressure, 4/10, triggered by moderat...
    - `chest_xray`: Mild cardiomegaly with cardiothoracic ratio 0.55. Lung fields clear bilaterally, no infiltrates, consolidation...
    - `ecg`: Normal sinus rhythm at 72 bpm. PR interval 160ms (normal). QRS duration 88ms (normal). Normal axis. ST-segment...
    - `echo`: Left ventricular ejection fraction estimated at 62% (normal). No regional wall motion abnormalities. Normal le...
    - `heart_sounds`: S1 and S2 normal intensity and splitting. Grade II/VI systolic murmur at the apex, non-radiating, consistent w...
    - `lab_results`: Troponin I: 0.04 ng/mL (borderline, normal <0.03). BNP: 180 pg/mL (mildly elevated, normal <100). HbA1c: 7.2% ...
    - `medication`: Active medications: Lisinopril 20mg daily (ACE inhibitor for HTN), Metformin 1000mg BID (diabetes), Atorvastat...

