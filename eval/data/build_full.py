"""
Phase C+D: FROZEN full dataset. 100 queries (30 simple + 10 probes + 30 cross-modal
+ 30 multi-hop) + 40 KB sets (10 clean + 30 seeded). Authored from fact_inventory.json,
one gold set per query, researcher-reviewed at Checkpoint 2.

Gold-set philosophy (from pilot): required = modalities a correct answer MUST use;
optional = defensibly-relevant modalities that are neither rewarded nor penalized.

Run: python eval/data/build_full.py
Writes: queries.jsonl, kb_sets.jsonl, REVIEW.md, coverage_report.md
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STUBS = ROOT / "stubs"


def Q(qid, tier, pid, query, gold, optional=None, composed_from=None,
      modality_override=None, probe_type=None, rationale=""):
    return {"id": qid, "tier": tier, "patient_id": pid, "query": query,
            "gold_agents": gold, "optional_agents": optional or [],
            "composed_from": composed_from, "modality_override": modality_override,
            "probe_type": probe_type, "rationale": rationale}


# =========================================================================
# SIMPLE (30) -- single-modality lookups, 3 per patient, all 7 modalities covered
# =========================================================================
SIMPLE = [
    Q("S01", "simple", "P0001", "What is the QTc interval on this patient's ECG?", ["ecg"], rationale="QTc 420ms — ecg only."),
    Q("S02", "simple", "P0001", "What is this patient's LDL cholesterol level?", ["lab_results"], rationale="LDL 142 — labs only."),
    Q("S03", "simple", "P0001", "Which statin and dose is this patient currently taking?", ["medication"], rationale="Atorvastatin 40mg — medication only."),
    Q("S04", "simple", "P0002", "What does the chest X-ray show in the right lower lobe?", ["chest_xray"], rationale="RLL consolidation — CXR only."),
    Q("S05", "simple", "P0002", "What is this patient's white blood cell count?", ["lab_results"], rationale="WBC 15.2 — labs only."),
    Q("S06", "simple", "P0002", "What is the patient's fever history on presentation?", ["clinical_notes"], rationale="5-day fever 39.2C — notes only."),
    Q("S07", "simple", "P0003", "What is this patient's left ventricular ejection fraction?", ["echo"], rationale="LVEF 60% — echo only."),
    Q("S08", "simple", "P0003", "Are any murmurs heard on auscultation?", ["heart_sounds"], rationale="No murmurs — heart_sounds only."),
    Q("S09", "simple", "P0003", "What medication is this patient taking for anxiety?", ["medication"], rationale="Sertraline 50mg — medication only."),
    Q("S10", "simple", "P0004", "What is this patient's current ejection fraction?", ["echo"], rationale="LVEF 25% — echo only."),
    Q("S11", "simple", "P0004", "What is the patient's BNP level?", ["lab_results"], rationale="BNP 1840 — labs only."),
    Q("S12", "simple", "P0004", "What anticoagulant is this patient taking?", ["medication"], rationale="Apixaban — medication only."),
    Q("S13", "simple", "P0005", "What does the ECG show regarding premature beats?", ["ecg"], rationale="Isolated PACs — ecg only."),
    Q("S14", "simple", "P0005", "What is this patient's TSH level?", ["lab_results"], rationale="TSH 1.6 — labs only."),
    Q("S15", "simple", "P0005", "What triggers this patient's palpitations?", ["clinical_notes"], rationale="Caffeine/stress — notes only."),
    Q("S16", "simple", "P0006", "What do the arterial blood gas results show?", ["lab_results"], rationale="ABG type 2 resp failure — labs only."),
    Q("S17", "simple", "P0006", "What does the chest X-ray show about lung volumes?", ["chest_xray"], rationale="Hyperinflation — CXR only."),
    Q("S18", "simple", "P0006", "What is the estimated pulmonary artery pressure (RVSP) on echo?", ["echo"], rationale="RVSP 42 — echo only."),
    Q("S19", "simple", "P0007", "What cardiac rhythm does the ECG show?", ["ecg"], rationale="Atrial fibrillation — ecg only."),
    Q("S20", "simple", "P0007", "What is this patient's TSH level?", ["lab_results"], rationale="TSH 2.1 normal — labs only."),
    Q("S21", "simple", "P0007", "What rate-control medication was started for the AFib?", ["medication"], rationale="Metoprolol succinate — medication only."),
    Q("S22", "simple", "P0008", "What is this patient's HbA1c?", ["lab_results"], rationale="HbA1c 10.2% — labs only."),
    Q("S23", "simple", "P0008", "Does the ECG meet voltage criteria for left ventricular hypertrophy?", ["ecg"], rationale="LVH by Sokolow-Lyon — ecg only."),
    Q("S24", "simple", "P0008", "What extra heart sound is heard on auscultation?", ["heart_sounds"], rationale="S4 gallop — heart_sounds only."),
    Q("S25", "simple", "P0009", "Describe the murmur heard on auscultation.", ["heart_sounds"], rationale="4/6 systolic to carotids — heart_sounds only."),
    Q("S26", "simple", "P0009", "What is the aortic valve area on the echocardiogram?", ["echo"], rationale="AVA 0.7 cm2 — echo only."),
    Q("S27", "simple", "P0009", "What is this patient's BNP level?", ["lab_results"], rationale="BNP 480 — labs only."),
    Q("S28", "simple", "P0010", "What do the Q waves on the ECG indicate?", ["ecg"], rationale="Prior anterior MI — ecg only."),
    Q("S29", "simple", "P0010", "What is this patient's current ejection fraction?", ["echo"], rationale="LVEF 42% — echo only."),
    Q("S30", "simple", "P0010", "What is this patient's dual antiplatelet regimen?", ["medication"], rationale="Aspirin + clopidogrel — medication only."),
]

# =========================================================================
# PROBES (10) -- 5 no-tool (definitional), 5 unavailable-modality
# =========================================================================
PROBES = [
    Q("P01", "simple", "P0002", "In general, what is procalcitonin used to indicate?", [], probe_type="no_tool", rationale="Definitional; no patient data needed."),
    Q("P02", "simple", "P0004", "What does the term 'ejection fraction' mean in general?", [], probe_type="no_tool", rationale="Definitional; no tools."),
    Q("P03", "simple", "P0006", "In general terms, what is COPD?", [], probe_type="no_tool", rationale="Definitional; no tools."),
    Q("P04", "simple", "P0007", "Generally speaking, what is atrial fibrillation?", [], probe_type="no_tool", rationale="Definitional; no tools."),
    Q("P05", "simple", "P0009", "In general, what does 'aortic stenosis' refer to?", [], probe_type="no_tool", rationale="Definitional; no tools."),
    Q("P06", "simple", "P0005", "What did this patient's echocardiogram show about LV function?", [], modality_override=["echo"], probe_type="unavailable_modality", rationale="Echo stripped; must not call echo."),
    Q("P07", "simple", "P0003", "What does this patient's ECG show?", [], modality_override=["ecg"], probe_type="unavailable_modality", rationale="ECG stripped; must not call ecg."),
    Q("P08", "simple", "P0002", "What murmurs were heard on this patient's auscultation?", [], modality_override=["heart_sounds"], probe_type="unavailable_modality", rationale="Heart sounds stripped; must not call heart_sounds."),
    Q("P09", "simple", "P0008", "What did this patient's chest X-ray reveal?", [], modality_override=["chest_xray"], probe_type="unavailable_modality", rationale="CXR stripped; must not call chest_xray."),
    Q("P10", "simple", "P0010", "What are this patient's latest laboratory values?", [], modality_override=["lab_results"], probe_type="unavailable_modality", rationale="Labs stripped; must not call lab_results."),
]

# =========================================================================
# CROSS-MODAL (30) -- 3 per patient
# =========================================================================
CROSS = [
    Q("C01", "cross_modal", "P0001", "Is there any evidence of myocardial ischemia in this patient?", ["ecg", "echo", "clinical_notes"], ["lab_results", "heart_sounds"], rationale="ECG ST-dep, echo lateral hypokinesis, notes angina; troponin optional."),
    Q("C02", "cross_modal", "P0001", "How well controlled are this patient's diabetes and lipids?", ["lab_results", "medication"], ["clinical_notes"], rationale="Labs (HbA1c/LDL) + medication regimen."),
    Q("C03", "cross_modal", "P0001", "Does the imaging support hypertensive heart disease?", ["chest_xray", "echo"], ["ecg"], rationale="CXR cardiomegaly + echo diastolic dysfunction."),
    Q("C04", "cross_modal", "P0002", "Is there evidence of a pulmonary infection?", ["clinical_notes", "chest_xray", "lab_results"], ["ecg"], rationale="Notes fever/cough, CXR consolidation, labs WBC/CRP."),
    Q("C05", "cross_modal", "P0002", "Is the patient's tachycardia cardiac or secondary to another cause?", ["ecg", "clinical_notes"], ["lab_results", "heart_sounds"], rationale="ECG sinus tach + notes fever context."),
    Q("C06", "cross_modal", "P0002", "Is there any evidence of cardiac involvement from this illness?", ["echo", "ecg", "heart_sounds"], ["lab_results"], rationale="Echo normal, ECG no ischemia, auscultation normal — rule out cardiac."),
    Q("C07", "cross_modal", "P0003", "Is there any evidence of cardiac disease in this patient?", ["ecg", "echo", "heart_sounds"], ["chest_xray", "clinical_notes"], rationale="Wellness exam: ECG/echo/auscultation all normal."),
    Q("C08", "cross_modal", "P0003", "Do the labs and history suggest any metabolic abnormality?", ["lab_results", "clinical_notes"], ["medication"], rationale="Labs normal + history."),
    Q("C09", "cross_modal", "P0003", "Is the cardiac auscultation consistent with the imaging?", ["heart_sounds", "echo"], ["ecg"], rationale="Normal auscultation vs normal echo."),
    Q("C10", "cross_modal", "P0004", "Assess this patient's volume status and heart failure severity.", ["clinical_notes", "chest_xray", "echo", "lab_results"], ["heart_sounds", "ecg"], rationale="Notes edema, CXR congestion, echo EF25, BNP 1840."),
    Q("C11", "cross_modal", "P0004", "What evidence supports atrial fibrillation in this patient?", ["ecg", "heart_sounds"], ["clinical_notes"], rationale="ECG AFib + irregularly irregular auscultation."),
    Q("C12", "cross_modal", "P0004", "Is there evidence of mitral regurgitation?", ["echo", "heart_sounds"], ["chest_xray"], rationale="Echo moderate MR + holosystolic murmur."),
    Q("C13", "cross_modal", "P0005", "Are the palpitations caused by a dangerous arrhythmia?", ["ecg", "echo"], ["clinical_notes", "heart_sounds"], rationale="ECG benign PACs + structurally normal echo."),
    Q("C14", "cross_modal", "P0005", "Is there a structural or thyroid cause for the palpitations?", ["echo", "lab_results"], ["clinical_notes"], rationale="Echo normal + TSH normal."),
    Q("C15", "cross_modal", "P0005", "Do the auscultation and ECG agree about the rhythm?", ["heart_sounds", "ecg"], [], rationale="Both show PACs/normal rhythm."),
    Q("C16", "cross_modal", "P0006", "Is there evidence of right heart strain or pulmonary hypertension?", ["ecg", "echo"], ["chest_xray", "heart_sounds"], rationale="ECG RV strain/P pulmonale + echo RVSP42/D-sign."),
    Q("C17", "cross_modal", "P0006", "What evidence supports a COPD exacerbation?", ["clinical_notes", "chest_xray", "lab_results"], ["medication"], rationale="Notes dyspnea/sputum, CXR hyperinflation, ABG."),
    Q("C18", "cross_modal", "P0006", "Do the ECG and echo agree about right-sided heart involvement?", ["ecg", "echo"], ["heart_sounds"], rationale="ECG RAD/RV strain vs echo RV dilation."),
    Q("C19", "cross_modal", "P0007", "What is the evidence for new-onset atrial fibrillation?", ["ecg", "clinical_notes", "heart_sounds"], ["chest_xray"], rationale="ECG AFib, notes palpitations, irregular auscultation."),
    Q("C20", "cross_modal", "P0007", "Has a thyroid or structural cause for the AFib been evaluated?", ["lab_results", "echo"], ["clinical_notes"], rationale="TSH normal + echo LA size."),
    Q("C21", "cross_modal", "P0007", "Is there left atrial enlargement to support an AFib substrate?", ["echo", "chest_xray"], ["ecg"], rationale="Echo LA 4.1cm + CXR LA enlargement."),
    Q("C22", "cross_modal", "P0008", "Is there cardiac end-organ damage from hypertension and diabetes?", ["ecg", "echo", "heart_sounds"], ["chest_xray", "clinical_notes"], rationale="ECG LVH strain, echo concentric LVH, S4; CXR cardiomegaly optional (Q09 lesson)."),
    Q("C23", "cross_modal", "P0008", "How well controlled is the diabetes and is there renal involvement?", ["lab_results", "clinical_notes"], ["medication"], rationale="HbA1c 10.2, ACR 280 + history."),
    Q("C24", "cross_modal", "P0008", "Do the ECG and echo agree about left ventricular hypertrophy?", ["ecg", "echo"], ["heart_sounds"], rationale="ECG LVH voltage vs echo concentric LVH."),
    Q("C25", "cross_modal", "P0009", "What is the severity of this patient's aortic stenosis?", ["echo", "heart_sounds"], ["clinical_notes", "chest_xray", "ecg"], rationale="Echo AVA/gradient + murmur; clinical/CXR/ECG supportive."),
    Q("C26", "cross_modal", "P0009", "Is there evidence of pressure overload on the heart?", ["ecg", "echo"], ["heart_sounds", "chest_xray"], rationale="ECG LVH strain + echo concentric LVH."),
    Q("C27", "cross_modal", "P0009", "Do the murmur and valve findings correlate?", ["heart_sounds", "echo"], [], rationale="4/6 murmur vs severe AS on echo."),
    Q("C28", "cross_modal", "P0010", "What does the evidence show about the prior myocardial infarction?", ["ecg", "echo"], ["clinical_notes", "chest_xray"], rationale="ECG Q waves + echo anterior hypokinesis."),
    Q("C29", "cross_modal", "P0010", "Has left ventricular function recovered after the infarct?", ["echo", "clinical_notes"], ["lab_results"], rationale="Echo EF42 improved + notes improving tolerance."),
    Q("C30", "cross_modal", "P0010", "Is the secondary-prevention medication regimen appropriate post-MI?", ["medication", "clinical_notes"], ["lab_results"], rationale="DAPT/statin/BB/ARB + post-MI context."),
]

# =========================================================================
# MULTI-HOP (30) -- 3 per patient, composed from per-modality questions
# =========================================================================
def M(qid, pid, query, gold, optional, composed, rationale):
    return Q(qid, "multi_hop", pid, query, gold, optional, composed_from=composed, rationale=rationale)

MULTI = [
    M("M01", "P0001", "Given this patient's exertional chest pain, do the ECG and echo localize the ischemia to the same territory, and are the cardiac enzymes concerning?",
      ["clinical_notes", "ecg", "echo", "lab_results"], ["heart_sounds"],
      ["What is the chest pain history? (notes)", "Where is the ischemia on ECG? (ecg)", "Which wall is hypokinetic on echo? (echo)", "Is troponin elevated? (labs)"],
      "Lateral ischemia chain: notes angina + ECG V4-V6 + echo lateral wall + borderline troponin."),
    M("M02", "P0001", "Is this patient's cardiovascular risk being adequately managed by the current medications, given the lipid and glucose results and the ischemic ECG findings?",
      ["lab_results", "medication", "ecg"], ["clinical_notes", "echo"],
      ["What are the LDL and HbA1c? (labs)", "What lipid/glucose meds is the patient on? (medication)", "What do the ECG ischemic findings show? (ecg)"],
      "Risk management: LDL 142/HbA1c 7.2 vs atorvastatin 40 (subtherapeutic) + lateral ischemia on ECG."),
    M("M03", "P0001", "Do the structural imaging and auscultation agree about valvular status, and is it consistent with the reported symptoms?",
      ["echo", "heart_sounds", "clinical_notes"], [],
      ["What valvular disease on echo? (echo)", "What murmur on auscultation? (heart_sounds)", "What are the symptoms? (notes)"],
      "Trace MR on echo + grade II apical murmur, mild symptoms."),
    M("M04", "P0002", "Does the combination of imaging, labs, and symptoms confirm a bacterial pneumonia, and is the antibiotic choice appropriate?",
      ["chest_xray", "lab_results", "clinical_notes", "medication"], [],
      ["What does the CXR show? (cxr)", "What do inflammatory markers show? (labs)", "What are the symptoms? (notes)", "What antibiotics were started? (medication)"],
      "CAP: consolidation + WBC/procalcitonin + fever + ceftriaxone/azithromycin."),
    M("M05", "P0002", "Is the tachycardia explained by the infection rather than a primary cardiac problem, considering the ECG, echo, and clinical context?",
      ["ecg", "echo", "clinical_notes"], ["heart_sounds"],
      ["What does the ECG rhythm show? (ecg)", "Is the heart structurally normal? (echo)", "What is the fever/infection context? (notes)"],
      "Sinus tach secondary to fever; echo normal, no cardiac cause."),
    M("M06", "P0002", "Do the auscultation, echo, and ECG together exclude significant structural or ischemic heart disease in this acutely ill patient?",
      ["heart_sounds", "echo", "ecg"], [],
      ["What does auscultation reveal? (heart_sounds)", "What does the echo show? (echo)", "Does the ECG show ischemia? (ecg)"],
      "Normal auscultation + LVEF 62% + no ischemic ECG changes exclude cardiac disease."),
    M("M07", "P0003", "Across the ECG, echo, and auscultation, is there any objective evidence of cardiac disease to explain the exercise intolerance?",
      ["ecg", "echo", "heart_sounds", "clinical_notes"], ["chest_xray"],
      ["What does the ECG show? (ecg)", "What is the EF? (echo)", "Any murmurs? (heart_sounds)", "What is the exercise complaint? (notes)"],
      "All normal; deconditioning, no cardiac disease."),
    M("M08", "P0003", "Do the labs, medication review, and clinical history together indicate any cardiovascular risk requiring new treatment?",
      ["lab_results", "medication", "clinical_notes"], [],
      ["What is the lipid/metabolic panel? (labs)", "What medications is the patient on? (medication)", "What risk factors are in the history? (notes)"],
      "Normal lipids + no cardiac meds + low-risk history — no new treatment."),
    M("M09", "P0003", "Is the normal cardiac imaging consistent with both the physical exam and the resting vitals reported?",
      ["echo", "heart_sounds", "clinical_notes"], ["ecg"],
      ["What does the echo show? (echo)", "What are the auscultation findings? (heart_sounds)", "What are the vitals/exam? (notes)"],
      "Normal echo + normal exam + normal vitals all agree."),
    M("M10", "P0004", "How severe is this heart failure decompensation when the symptoms, chest X-ray, echo, and BNP are considered together?",
      ["clinical_notes", "chest_xray", "echo", "lab_results"], ["heart_sounds", "ecg"],
      ["What are the HF symptoms? (notes)", "What does the CXR show? (cxr)", "What is the EF? (echo)", "What is the BNP? (labs)"],
      "Severe ADHF: orthopnea/edema + congestion/effusions + EF25 + BNP1840."),
    M("M11", "P0004", "Is the anticoagulation and heart-failure medication regimen appropriate given the atrial fibrillation and reduced renal function?",
      ["ecg", "lab_results", "medication"], ["clinical_notes"],
      ["What rhythm is on ECG? (ecg)", "What is the renal function? (labs)", "What is the medication regimen? (medication)"],
      "AFib + eGFR32 + apixaban/carvedilol/losartan/furosemide (ACE allergy)."),
    M("M12", "P0004", "Do the echo and auscultation agree on the presence and severity of mitral regurgitation, and does it fit the heart-failure picture?",
      ["echo", "heart_sounds", "clinical_notes"], ["chest_xray"],
      ["What MR grade on echo? (echo)", "What murmur on auscultation? (heart_sounds)", "What is the HF context? (notes)"],
      "Moderate functional MR + holosystolic murmur in decompensated HFrEF."),
    M("M13", "P0005", "Taking the ECG, echo, and labs together, are these palpitations benign or is further workup warranted?",
      ["ecg", "echo", "lab_results"], ["clinical_notes", "heart_sounds"],
      ["What does the ECG show? (ecg)", "Is the heart structurally normal? (echo)", "Is thyroid function normal? (labs)"],
      "Benign PACs + normal echo + normal TSH."),
    M("M14", "P0005", "Do the history and ECG together identify a modifiable trigger for the palpitations, and is medication indicated?",
      ["clinical_notes", "ecg", "medication"], ["heart_sounds"],
      ["What triggers the palpitations? (notes)", "What arrhythmia is on ECG? (ecg)", "Is any medication indicated? (medication)"],
      "Caffeine trigger + benign PACs + no antiarrhythmic; counseling only."),
    M("M15", "P0005", "Is the rhythm seen on the ECG confirmed by auscultation, and is it structurally benign on echo?",
      ["ecg", "heart_sounds", "echo"], [],
      ["What does the ECG show? (ecg)", "What does auscultation reveal? (heart_sounds)", "Is the echo normal? (echo)"],
      "PACs on ECG + early beats on auscultation + normal echo."),
    M("M16", "P0006", "Does the evidence across ECG, echo, and chest X-ray establish cor pulmonale from this patient's COPD?",
      ["ecg", "echo", "chest_xray"], ["heart_sounds"],
      ["What right-heart signs on ECG? (ecg)", "What does the echo show about the RV? (echo)", "What does the CXR show? (cxr)"],
      "Cor pulmonale: P pulmonale/RV strain + RV dilation/RVSP42 + hyperinflation."),
    M("M17", "P0006", "Do the blood gas, symptoms, and medications together support the diagnosis and treatment of an acute COPD exacerbation?",
      ["lab_results", "clinical_notes", "medication"], ["chest_xray"],
      ["What does the ABG show? (labs)", "What are the symptoms? (notes)", "What treatment was started? (medication)"],
      "Type 2 resp failure ABG + dyspnea/sputum + prednisolone/doxycycline."),
    M("M18", "P0006", "Does the elevated pulmonary pressure on echo correlate with the auscultation and ECG findings of right heart involvement?",
      ["echo", "heart_sounds", "ecg"], [],
      ["What is the RVSP on echo? (echo)", "What does auscultation reveal? (heart_sounds)", "What ECG signs of RH strain? (ecg)"],
      "RVSP42 + loud P2 + RV strain/P pulmonale all correlate."),
    M("M19", "P0007", "Do the ECG, auscultation, and history together establish new-onset atrial fibrillation, and has a reversible cause been excluded?",
      ["ecg", "heart_sounds", "clinical_notes", "lab_results"], [],
      ["What rhythm on ECG? (ecg)", "What does auscultation reveal? (heart_sounds)", "What is the history? (notes)", "Is thyroid excluded? (labs)"],
      "New AFib: ECG + irregular auscultation + palpitations, TSH normal."),
    M("M20", "P0007", "Given the confirmed atrial fibrillation and stroke risk, is the anticoagulation and rate-control regimen appropriate?",
      ["ecg", "medication", "clinical_notes"], ["lab_results"],
      ["What rhythm on ECG? (ecg)", "What AFib medications were started? (medication)", "What are the stroke risk factors? (notes)"],
      "AFib + apixaban (CHA2DS2-VASc 3) + metoprolol rate control."),
    M("M21", "P0007", "Do the echo, chest X-ray, and ECG together support a left atrial substrate for the arrhythmia?",
      ["echo", "chest_xray", "ecg"], [],
      ["What is the LA size on echo? (echo)", "What does the CXR show about the LA? (cxr)", "What rhythm/atrial activity is on the ECG? (ecg)"],
      "Echo LA 4.1cm + CXR LA enlargement + AFib on ECG."),
    M("M22", "P0008", "Do the ECG, echo, and auscultation together demonstrate hypertensive cardiac end-organ damage in this diabetic patient?",
      ["ecg", "echo", "heart_sounds"], ["chest_xray", "clinical_notes"],
      ["What LVH signs on ECG? (ecg)", "What does the echo show? (echo)", "What extra heart sound? (heart_sounds)"],
      "LVH strain + concentric LVH/diastolic dysfx + S4 gallop."),
    M("M23", "P0008", "Given the HbA1c, renal markers, current medications, and echo evidence of cardiac damage, is the regimen adequate for cardiorenal protection?",
      ["lab_results", "medication", "echo"], ["clinical_notes", "ecg"],
      ["What is the HbA1c and ACR? (labs)", "What is the current regimen and what is recommended? (medication)", "What cardiac end-organ damage is on echo? (echo)"],
      "HbA1c10.2/ACR280 + concentric LVH on echo + missing SGLT2/GLP-1 for cardiorenal benefit."),
    M("M24", "P0008", "Does the poor glycemic control in the labs align with both the clinical complications in the notes and the cardiac changes on echo?",
      ["lab_results", "clinical_notes", "echo"], ["ecg", "heart_sounds"],
      ["What is the glycemic control? (labs)", "What complications are documented? (notes)", "What cardiac changes on echo? (echo)"],
      "HbA1c10.2 + neuropathy/ulcer + concentric LVH/diastolic dysfunction on echo."),
    M("M25", "P0009", "Does the exertional syncope, together with the murmur and echo valve data, indicate severe aortic stenosis, and is any medication a concern?",
      ["clinical_notes", "heart_sounds", "echo", "medication"], [],
      ["What is the syncope history? (notes)", "Describe the murmur. (heart_sounds)", "What is the valve area/gradient? (echo)", "Any medication concern? (medication)"],
      "Severe AS: syncope + 4/6 murmur to carotids + AVA0.7 + amlodipine caution."),
    M("M26", "P0009", "Do the ECG, echo, and auscultation together demonstrate the pressure overload expected from severe aortic stenosis?",
      ["ecg", "echo", "heart_sounds"], ["chest_xray"],
      ["What LVH signs on ECG? (ecg)", "What does the echo show about LV and valve? (echo)", "What does the murmur/S2 indicate? (heart_sounds)"],
      "ECG LVH strain + echo concentric LVH/severe AS + 4/6 murmur with diminished S2."),
    M("M27", "P0009", "Is the syncope workup supported by both the chest X-ray and lab findings for this valve disease?",
      ["chest_xray", "lab_results", "clinical_notes"], ["echo"],
      ["What does the CXR show? (cxr)", "What is the BNP? (labs)", "What is the syncope history? (notes)"],
      "CXR valve calcification/post-stenotic dilation + BNP480 + syncope."),
    M("M28", "P0010", "Do the ECG and echo together characterize the prior anterior infarct and the current degree of LV recovery?",
      ["ecg", "echo", "clinical_notes"], ["chest_xray"],
      ["What does the ECG show of prior MI? (ecg)", "What is the EF and wall motion? (echo)", "What is the recovery history? (notes)"],
      "Q waves V1-V3 + EF42 (improved from 35) anterior hypokinesis + rehab progress."),
    M("M29", "P0010", "Given the post-MI status and lipid results, is the secondary-prevention medication regimen optimized?",
      ["clinical_notes", "lab_results", "medication"], [],
      ["What is the post-MI status? (notes)", "Is the LDL at goal? (labs)", "What is the prevention regimen? (medication)"],
      "Post-STEMI + LDL58 at goal + DAPT/statin/BB/ARB."),
    M("M30", "P0010", "Is the reduced ejection fraction on echo consistent with the ECG infarct pattern and the absence of recurrent ischemia in the labs?",
      ["echo", "ecg", "lab_results"], ["clinical_notes"],
      ["What is the EF and wall motion? (echo)", "What is the ECG infarct pattern? (ecg)", "Is troponin negative? (labs)"],
      "EF42 anterior hypokinesis + Q waves V1-V3 + undetectable troponin."),
]

QUERIES = SIMPLE + PROBES + CROSS + MULTI


def apply_routing_principle(queries):
    """V2 Rule A (pre-registered): clinical_notes is optional-by-default on every
    query where it is not answer-bearing (in gold) and not a no_tool probe.
    Universal and results-independent — the chart is legitimately consultable for
    any clinical question, so reading it must not be penalized as a routing error."""
    n = 0
    for q in queries:
        if (q["probe_type"] != "no_tool"
                and "clinical_notes" not in q["gold_agents"]
                and "clinical_notes" not in q["optional_agents"]):
            q["optional_agents"] = q["optional_agents"] + ["clinical_notes"]
            n += 1
    return n


_CN_ADDED = apply_routing_principle(QUERIES)


# =========================================================================
# KB SETS: 10 clean + 30 seeded
# =========================================================================
def load_findings(pid):
    data = json.loads((STUBS / f"{pid}.json").read_text())
    return [{"agent": a, "summary": v["summary"]} for a, v in data.items()]


def seed(pid, target_agent, new_summary):
    f = load_findings(pid)
    for x in f:
        if x["agent"] == target_agent:
            x["summary"] = new_summary
    return f


CLEAN = [{"id": f"KBC{str(i+1).zfill(2)}", "patient_id": pid, "type": "clean",
          "findings": load_findings(pid), "gold_conflict": None,
          "seed_rationale": "Real internally-consistent findings; Bus must flag NO contradiction."}
         for i, pid in enumerate([f"P{str(n).zfill(4)}" for n in range(1, 11)])]

# 30 seeded: 3 per patient, varying modality-pair and subtlety (blatant/moderate/subtle)
SEED_SPECS = [
    # P0001 (base: lateral ischemia, EF45, trace MR)
    ("P0001", "echo", ["ecg", "echo"], "blatant",
     "Left ventricular ejection fraction 63% (normal). No wall motion abnormalities. No valvular disease. Normal diastolic function. Structurally normal heart."),
    ("P0001", "heart_sounds", ["echo", "heart_sounds"], "moderate",
     "Harsh grade IV/VI systolic murmur radiating to the carotids with a diminished S2, consistent with severe aortic valve disease. Delayed carotid upstroke."),
    ("P0001", "lab_results", ["ecg", "lab_results"], "moderate",
     "Troponin I 12.5 ng/mL (markedly elevated, consistent with acute myocardial infarction). CK-MB elevated. Findings diagnostic of acute ST-elevation MI."),
    # P0002 (base: pneumonia, normal heart)
    ("P0002", "chest_xray", ["clinical_notes", "chest_xray"], "blatant",
     "Clear lung fields bilaterally. No consolidation, infiltrate, effusion, or air bronchograms. Normal heart size. Entirely normal chest radiograph."),
    ("P0002", "lab_results", ["clinical_notes", "lab_results"], "moderate",
     "WBC 5.1 x10^3/uL (normal). CRP 2 mg/L (normal). Procalcitonin 0.05 ng/mL (normal, no evidence of bacterial infection). No inflammatory markers elevated."),
    ("P0002", "echo", ["chest_xray", "echo"], "subtle",
     "Severely reduced LVEF 30% with global hypokinesis. Moderate pulmonary edema pattern. Findings consistent with acute cardiogenic pulmonary congestion."),
    # P0003 (base: all normal)
    ("P0003", "ecg", ["ecg", "heart_sounds"], "blatant",
     "Atrial fibrillation with rapid ventricular response 148 bpm. Absent P waves, irregularly irregular. Acute lateral ST-segment depression."),
    ("P0003", "echo", ["echo", "clinical_notes"], "moderate",
     "Severely reduced LVEF 28% with global hypokinesis and left ventricular dilation. Findings consistent with dilated cardiomyopathy."),
    ("P0003", "lab_results", ["lab_results", "clinical_notes"], "subtle",
     "HbA1c 11.4% (markedly elevated, poorly controlled diabetes). Fasting glucose 292 mg/dL. LDL 208 mg/dL (severe hyperlipidemia)."),
    # P0004 (base: severe HFrEF, AFib, EF25)
    ("P0004", "echo", ["clinical_notes", "echo"], "blatant",
     "Normal LVEF 60%. No wall motion abnormalities. No valvular disease. Normal diastolic function. Normal left atrial size. Structurally normal heart."),
    ("P0004", "ecg", ["ecg", "heart_sounds"], "moderate",
     "Normal sinus rhythm at 72 bpm with regular RR intervals. Normal P waves present before every QRS. No atrial fibrillation."),
    ("P0004", "lab_results", ["clinical_notes", "lab_results"], "moderate",
     "BNP 45 pg/mL (normal). No biochemical evidence of heart failure or volume overload. Renal function normal, creatinine 0.9 mg/dL."),
    # P0005 (base: benign PACs, normal)
    ("P0005", "ecg", ["ecg", "echo"], "moderate",
     "Wolff-Parkinson-White pattern with short PR interval and delta waves. Pre-excitation present. High risk for reentrant tachyarrhythmia."),
    ("P0005", "echo", ["echo", "clinical_notes"], "moderate",
     "Hypertrophic cardiomyopathy with asymmetric septal hypertrophy (IVSd 19mm) and systolic anterior motion of the mitral valve. LVOT obstruction present."),
    ("P0005", "lab_results", ["lab_results", "clinical_notes"], "subtle",
     "TSH <0.01 mIU/L with free T4 markedly elevated, consistent with overt hyperthyroidism as a driver of the palpitations."),
    # P0006 (base: COPD, cor pulmonale, RV involvement)
    ("P0006", "echo", ["ecg", "echo"], "blatant",
     "Normal right ventricular size and function. Normal RVSP 22 mmHg. No pulmonary hypertension. Normal interventricular septum. Structurally normal heart."),
    ("P0006", "lab_results", ["clinical_notes", "lab_results"], "moderate",
     "ABG on room air: pH 7.42, pCO2 38 mmHg (normal), pO2 96 mmHg (normal oxygenation). No respiratory failure. Normal acid-base status."),
    ("P0006", "chest_xray", ["clinical_notes", "chest_xray"], "subtle",
     "Normal lung volumes without hyperinflation. Diaphragms normally positioned. No emphysematous changes. Normal AP diameter."),
    # P0007 (base: new AFib, LA dilation, thyroid normal)
    ("P0007", "ecg", ["ecg", "clinical_notes"], "blatant",
     "Normal sinus rhythm at 76 bpm with regular RR intervals and normal P waves. No atrial fibrillation or ectopy."),
    ("P0007", "lab_results", ["lab_results", "clinical_notes"], "moderate",
     "TSH <0.01 mIU/L, free T4 markedly elevated, consistent with thyrotoxicosis driving the atrial fibrillation."),
    ("P0007", "echo", ["echo", "chest_xray"], "subtle",
     "Normal left atrial size at 3.2 cm. No structural substrate for atrial fibrillation. Normal chamber dimensions throughout."),
    # P0008 (base: LVH, poorly controlled DM, S4)
    ("P0008", "lab_results", ["lab_results", "clinical_notes"], "blatant",
     "HbA1c 5.2% (normal, excellent glycemic control). Fasting glucose 88 mg/dL. Normal renal function, eGFR >90. No diabetic nephropathy."),
    ("P0008", "echo", ["ecg", "echo"], "moderate",
     "Normal left ventricular wall thickness with no hypertrophy. LVEF 65%. Normal diastolic function. No structural heart disease."),
    ("P0008", "heart_sounds", ["heart_sounds", "echo"], "subtle",
     "Normal S1 and S2 with no added sounds. No S4 gallop. Regular rate and rhythm. Entirely normal auscultation."),
    # P0009 (base: severe AS, 4/6 murmur, LVH)
    ("P0009", "echo", ["heart_sounds", "echo"], "blatant",
     "Normal aortic valve with trileaflet morphology and no stenosis. Aortic valve area 3.0 cm2, mean gradient 4 mmHg. Normal LVEF, no hypertrophy."),
    ("P0009", "heart_sounds", ["heart_sounds", "echo"], "moderate",
     "No murmurs, gallops, or rubs. Normal S1 and S2 with physiologic splitting. Normal carotid upstrokes. Entirely benign cardiac auscultation."),
    ("P0009", "ecg", ["ecg", "echo"], "subtle",
     "Normal ECG with no left ventricular hypertrophy by voltage criteria and no strain pattern. Normal ST segments and T waves."),
    # P0010 (base: post-anterior MI, Q waves, EF42)
    ("P0010", "ecg", ["ecg", "echo"], "blatant",
     "Entirely normal ECG. No Q waves in any leads. No evidence of prior infarction. Normal R-wave progression across the precordium."),
    ("P0010", "echo", ["ecg", "echo"], "moderate",
     "Normal LVEF 62% with no regional wall motion abnormality. No evidence of prior infarct or scar. Normal anterior and apical segments."),
    ("P0010", "lab_results", ["ecg", "lab_results"], "subtle",
     "Troponin I 9.8 ng/mL (markedly elevated) with dynamic rise, consistent with acute recurrent myocardial infarction."),
]

SEEDED = []
for i, (pid, tgt, pair, subtlety, newsum) in enumerate(SEED_SPECS, 1):
    SEEDED.append({
        "id": f"KBS{str(i).zfill(2)}", "patient_id": pid, "type": "seeded",
        "findings": seed(pid, tgt, newsum),
        "gold_conflict": pair, "subtlety": subtlety,
        "seed_rationale": f"Swapped {tgt} to contradict; gold pair {pair} ({subtlety}).",
    })

KB_SETS = CLEAN + SEEDED


# =========================================================================
def write_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def coverage_report():
    lines = ["# Coverage Report (frozen full set)\n\n"]
    tiers = Counter(q["tier"] for q in QUERIES)
    probes = Counter(q["probe_type"] for q in QUERIES if q["probe_type"])
    lines.append(f"- Total queries: {len(QUERIES)}  (tiers: {dict(tiers)})\n")
    lines.append(f"- Probes: {dict(probes)}\n")
    per_patient = Counter(q["patient_id"] for q in QUERIES)
    lines.append(f"- Queries per patient: {dict(sorted(per_patient.items()))}\n")
    # gold-agent modality coverage (required only)
    modc = Counter()
    for q in QUERIES:
        for a in q["gold_agents"]:
            modc[a] += 1
    lines.append(f"- Gold-agent (required) modality coverage: {dict(modc)}\n")
    lines.append(f"\n- KB sets: {len(KB_SETS)}  (clean {len(CLEAN)}, seeded {len(SEEDED)})\n")
    sub = Counter(s.get("subtlety") for s in SEEDED)
    lines.append(f"- Seeded subtlety distribution: {dict(sub)}\n")
    pairc = Counter(tuple(sorted(s["gold_conflict"])) for s in SEEDED)
    lines.append(f"- Seeded conflict-pair distribution: {len(pairc)} distinct pairs\n")
    for pair, n in sorted(pairc.items()):
        lines.append(f"    - {list(pair)}: {n}\n")
    (HERE / "coverage_report.md").write_text("".join(lines))


def review_md():
    lines = ["# Full Set Review (Checkpoint 2 — FREEZE on approval)\n\n",
             "Row-by-row gold-label approval. On sign-off these files are frozen and run once.\n\n"]
    for tier in ["simple", "cross_modal", "multi_hop"]:
        qs = [q for q in QUERIES if q["tier"] == tier]
        lines.append(f"## {tier} ({len(qs)})\n\n")
        for q in qs:
            probe = f" [{q['probe_type']}]" if q["probe_type"] else ""
            strip = f" (strip {q['modality_override']})" if q["modality_override"] else ""
            lines.append(f"**{q['id']}**{probe} `{q['patient_id']}`{strip}: {q['query']}\n")
            lines.append(f"  - gold={q['gold_agents']}" + (f" opt={q['optional_agents']}" if q['optional_agents'] else "") + f" — {q['rationale']}\n")
            if q["composed_from"]:
                lines.append(f"  - composed_from: {q['composed_from']}\n")
            lines.append("\n")
    lines.append("## KB seeded sets (30)\n\n")
    for s in SEEDED:
        swapped = [f["summary"][:80] for f in s["findings"]]  # not shown fully; see jsonl
        lines.append(f"**{s['id']}** `{s['patient_id']}` gold={s['gold_conflict']} ({s['subtlety']}): {s['seed_rationale']}\n\n")
    (HERE / "REVIEW.md").write_text("".join(lines))


def main():
    # integrity checks
    ids = [q["id"] for q in QUERIES]
    assert len(ids) == len(set(ids)), "duplicate query ids"
    assert len(QUERIES) == 100, f"expected 100 queries, got {len(QUERIES)}"
    assert len(KB_SETS) == 40, f"expected 40 kb sets, got {len(KB_SETS)}"
    write_jsonl(HERE / "queries.jsonl", QUERIES)
    write_jsonl(HERE / "kb_sets.jsonl", KB_SETS)
    coverage_report()
    review_md()
    print(f"Wrote queries.jsonl ({len(QUERIES)}), kb_sets.jsonl ({len(KB_SETS)})")
    print(f"V2 Rule A: added clinical_notes to optional on {_CN_ADDED} queries")
    print("Wrote coverage_report.md, REVIEW.md")


if __name__ == "__main__":
    main()
