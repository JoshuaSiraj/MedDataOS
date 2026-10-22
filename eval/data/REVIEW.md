# Full Set Review (Checkpoint 2 — FREEZE on approval)

Row-by-row gold-label approval. On sign-off these files are frozen and run once.

## simple (40)

**S01** `P0001`: What is the QTc interval on this patient's ECG?
  - gold=['ecg'] opt=['clinical_notes'] — QTc 420ms — ecg only.

**S02** `P0001`: What is this patient's LDL cholesterol level?
  - gold=['lab_results'] opt=['clinical_notes'] — LDL 142 — labs only.

**S03** `P0001`: Which statin and dose is this patient currently taking?
  - gold=['medication'] opt=['clinical_notes'] — Atorvastatin 40mg — medication only.

**S04** `P0002`: What does the chest X-ray show in the right lower lobe?
  - gold=['chest_xray'] opt=['clinical_notes'] — RLL consolidation — CXR only.

**S05** `P0002`: What is this patient's white blood cell count?
  - gold=['lab_results'] opt=['clinical_notes'] — WBC 15.2 — labs only.

**S06** `P0002`: What is the patient's fever history on presentation?
  - gold=['clinical_notes'] — 5-day fever 39.2C — notes only.

**S07** `P0003`: What is this patient's left ventricular ejection fraction?
  - gold=['echo'] opt=['clinical_notes'] — LVEF 60% — echo only.

**S08** `P0003`: Are any murmurs heard on auscultation?
  - gold=['heart_sounds'] opt=['clinical_notes'] — No murmurs — heart_sounds only.

**S09** `P0003`: What medication is this patient taking for anxiety?
  - gold=['medication'] opt=['clinical_notes'] — Sertraline 50mg — medication only.

**S10** `P0004`: What is this patient's current ejection fraction?
  - gold=['echo'] opt=['clinical_notes'] — LVEF 25% — echo only.

**S11** `P0004`: What is the patient's BNP level?
  - gold=['lab_results'] opt=['clinical_notes'] — BNP 1840 — labs only.

**S12** `P0004`: What anticoagulant is this patient taking?
  - gold=['medication'] opt=['clinical_notes'] — Apixaban — medication only.

**S13** `P0005`: What does the ECG show regarding premature beats?
  - gold=['ecg'] opt=['clinical_notes'] — Isolated PACs — ecg only.

**S14** `P0005`: What is this patient's TSH level?
  - gold=['lab_results'] opt=['clinical_notes'] — TSH 1.6 — labs only.

**S15** `P0005`: What triggers this patient's palpitations?
  - gold=['clinical_notes'] — Caffeine/stress — notes only.

**S16** `P0006`: What do the arterial blood gas results show?
  - gold=['lab_results'] opt=['clinical_notes'] — ABG type 2 resp failure — labs only.

**S17** `P0006`: What does the chest X-ray show about lung volumes?
  - gold=['chest_xray'] opt=['clinical_notes'] — Hyperinflation — CXR only.

**S18** `P0006`: What is the estimated pulmonary artery pressure (RVSP) on echo?
  - gold=['echo'] opt=['clinical_notes'] — RVSP 42 — echo only.

**S19** `P0007`: What cardiac rhythm does the ECG show?
  - gold=['ecg'] opt=['clinical_notes'] — Atrial fibrillation — ecg only.

**S20** `P0007`: What is this patient's TSH level?
  - gold=['lab_results'] opt=['clinical_notes'] — TSH 2.1 normal — labs only.

**S21** `P0007`: What rate-control medication was started for the AFib?
  - gold=['medication'] opt=['clinical_notes'] — Metoprolol succinate — medication only.

**S22** `P0008`: What is this patient's HbA1c?
  - gold=['lab_results'] opt=['clinical_notes'] — HbA1c 10.2% — labs only.

**S23** `P0008`: Does the ECG meet voltage criteria for left ventricular hypertrophy?
  - gold=['ecg'] opt=['clinical_notes'] — LVH by Sokolow-Lyon — ecg only.

**S24** `P0008`: What extra heart sound is heard on auscultation?
  - gold=['heart_sounds'] opt=['clinical_notes'] — S4 gallop — heart_sounds only.

**S25** `P0009`: Describe the murmur heard on auscultation.
  - gold=['heart_sounds'] opt=['clinical_notes'] — 4/6 systolic to carotids — heart_sounds only.

**S26** `P0009`: What is the aortic valve area on the echocardiogram?
  - gold=['echo'] opt=['clinical_notes'] — AVA 0.7 cm2 — echo only.

**S27** `P0009`: What is this patient's BNP level?
  - gold=['lab_results'] opt=['clinical_notes'] — BNP 480 — labs only.

**S28** `P0010`: What do the Q waves on the ECG indicate?
  - gold=['ecg'] opt=['clinical_notes'] — Prior anterior MI — ecg only.

**S29** `P0010`: What is this patient's current ejection fraction?
  - gold=['echo'] opt=['clinical_notes'] — LVEF 42% — echo only.

**S30** `P0010`: What is this patient's dual antiplatelet regimen?
  - gold=['medication'] opt=['clinical_notes'] — Aspirin + clopidogrel — medication only.

**P01** [no_tool] `P0002`: In general, what is procalcitonin used to indicate?
  - gold=[] — Definitional; no patient data needed.

**P02** [no_tool] `P0004`: What does the term 'ejection fraction' mean in general?
  - gold=[] — Definitional; no tools.

**P03** [no_tool] `P0006`: In general terms, what is COPD?
  - gold=[] — Definitional; no tools.

**P04** [no_tool] `P0007`: Generally speaking, what is atrial fibrillation?
  - gold=[] — Definitional; no tools.

**P05** [no_tool] `P0009`: In general, what does 'aortic stenosis' refer to?
  - gold=[] — Definitional; no tools.

**P06** [unavailable_modality] `P0005` (strip ['echo']): What did this patient's echocardiogram show about LV function?
  - gold=[] opt=['clinical_notes'] — Echo stripped; must not call echo.

**P07** [unavailable_modality] `P0003` (strip ['ecg']): What does this patient's ECG show?
  - gold=[] opt=['clinical_notes'] — ECG stripped; must not call ecg.

**P08** [unavailable_modality] `P0002` (strip ['heart_sounds']): What murmurs were heard on this patient's auscultation?
  - gold=[] opt=['clinical_notes'] — Heart sounds stripped; must not call heart_sounds.

**P09** [unavailable_modality] `P0008` (strip ['chest_xray']): What did this patient's chest X-ray reveal?
  - gold=[] opt=['clinical_notes'] — CXR stripped; must not call chest_xray.

**P10** [unavailable_modality] `P0010` (strip ['lab_results']): What are this patient's latest laboratory values?
  - gold=[] opt=['clinical_notes'] — Labs stripped; must not call lab_results.

## cross_modal (30)

**C01** `P0001`: Is there any evidence of myocardial ischemia in this patient?
  - gold=['ecg', 'echo', 'clinical_notes'] opt=['lab_results', 'heart_sounds'] — ECG ST-dep, echo lateral hypokinesis, notes angina; troponin optional.

**C02** `P0001`: How well controlled are this patient's diabetes and lipids?
  - gold=['lab_results', 'medication'] opt=['clinical_notes'] — Labs (HbA1c/LDL) + medication regimen.

**C03** `P0001`: Does the imaging support hypertensive heart disease?
  - gold=['chest_xray', 'echo'] opt=['ecg', 'clinical_notes'] — CXR cardiomegaly + echo diastolic dysfunction.

**C04** `P0002`: Is there evidence of a pulmonary infection?
  - gold=['clinical_notes', 'chest_xray', 'lab_results'] opt=['ecg'] — Notes fever/cough, CXR consolidation, labs WBC/CRP.

**C05** `P0002`: Is the patient's tachycardia cardiac or secondary to another cause?
  - gold=['ecg', 'clinical_notes'] opt=['lab_results', 'heart_sounds'] — ECG sinus tach + notes fever context.

**C06** `P0002`: Is there any evidence of cardiac involvement from this illness?
  - gold=['echo', 'ecg', 'heart_sounds'] opt=['lab_results', 'clinical_notes'] — Echo normal, ECG no ischemia, auscultation normal — rule out cardiac.

**C07** `P0003`: Is there any evidence of cardiac disease in this patient?
  - gold=['ecg', 'echo', 'heart_sounds'] opt=['chest_xray', 'clinical_notes'] — Wellness exam: ECG/echo/auscultation all normal.

**C08** `P0003`: Do the labs and history suggest any metabolic abnormality?
  - gold=['lab_results', 'clinical_notes'] opt=['medication'] — Labs normal + history.

**C09** `P0003`: Is the cardiac auscultation consistent with the imaging?
  - gold=['heart_sounds', 'echo'] opt=['ecg', 'clinical_notes'] — Normal auscultation vs normal echo.

**C10** `P0004`: Assess this patient's volume status and heart failure severity.
  - gold=['clinical_notes', 'chest_xray', 'echo', 'lab_results'] opt=['heart_sounds', 'ecg'] — Notes edema, CXR congestion, echo EF25, BNP 1840.

**C11** `P0004`: What evidence supports atrial fibrillation in this patient?
  - gold=['ecg', 'heart_sounds'] opt=['clinical_notes'] — ECG AFib + irregularly irregular auscultation.

**C12** `P0004`: Is there evidence of mitral regurgitation?
  - gold=['echo', 'heart_sounds'] opt=['chest_xray', 'clinical_notes'] — Echo moderate MR + holosystolic murmur.

**C13** `P0005`: Are the palpitations caused by a dangerous arrhythmia?
  - gold=['ecg', 'echo'] opt=['clinical_notes', 'heart_sounds'] — ECG benign PACs + structurally normal echo.

**C14** `P0005`: Is there a structural or thyroid cause for the palpitations?
  - gold=['echo', 'lab_results'] opt=['clinical_notes'] — Echo normal + TSH normal.

**C15** `P0005`: Do the auscultation and ECG agree about the rhythm?
  - gold=['heart_sounds', 'ecg'] opt=['clinical_notes'] — Both show PACs/normal rhythm.

**C16** `P0006`: Is there evidence of right heart strain or pulmonary hypertension?
  - gold=['ecg', 'echo'] opt=['chest_xray', 'heart_sounds', 'clinical_notes'] — ECG RV strain/P pulmonale + echo RVSP42/D-sign.

**C17** `P0006`: What evidence supports a COPD exacerbation?
  - gold=['clinical_notes', 'chest_xray', 'lab_results'] opt=['medication'] — Notes dyspnea/sputum, CXR hyperinflation, ABG.

**C18** `P0006`: Do the ECG and echo agree about right-sided heart involvement?
  - gold=['ecg', 'echo'] opt=['heart_sounds', 'clinical_notes'] — ECG RAD/RV strain vs echo RV dilation.

**C19** `P0007`: What is the evidence for new-onset atrial fibrillation?
  - gold=['ecg', 'clinical_notes', 'heart_sounds'] opt=['chest_xray'] — ECG AFib, notes palpitations, irregular auscultation.

**C20** `P0007`: Has a thyroid or structural cause for the AFib been evaluated?
  - gold=['lab_results', 'echo'] opt=['clinical_notes'] — TSH normal + echo LA size.

**C21** `P0007`: Is there left atrial enlargement to support an AFib substrate?
  - gold=['echo', 'chest_xray'] opt=['ecg', 'clinical_notes'] — Echo LA 4.1cm + CXR LA enlargement.

**C22** `P0008`: Is there cardiac end-organ damage from hypertension and diabetes?
  - gold=['ecg', 'echo', 'heart_sounds'] opt=['chest_xray', 'clinical_notes'] — ECG LVH strain, echo concentric LVH, S4; CXR cardiomegaly optional (Q09 lesson).

**C23** `P0008`: How well controlled is the diabetes and is there renal involvement?
  - gold=['lab_results', 'clinical_notes'] opt=['medication'] — HbA1c 10.2, ACR 280 + history.

**C24** `P0008`: Do the ECG and echo agree about left ventricular hypertrophy?
  - gold=['ecg', 'echo'] opt=['heart_sounds', 'clinical_notes'] — ECG LVH voltage vs echo concentric LVH.

**C25** `P0009`: What is the severity of this patient's aortic stenosis?
  - gold=['echo', 'heart_sounds'] opt=['clinical_notes', 'chest_xray', 'ecg'] — Echo AVA/gradient + murmur; clinical/CXR/ECG supportive.

**C26** `P0009`: Is there evidence of pressure overload on the heart?
  - gold=['ecg', 'echo'] opt=['heart_sounds', 'chest_xray', 'clinical_notes'] — ECG LVH strain + echo concentric LVH.

**C27** `P0009`: Do the murmur and valve findings correlate?
  - gold=['heart_sounds', 'echo'] opt=['clinical_notes'] — 4/6 murmur vs severe AS on echo.

**C28** `P0010`: What does the evidence show about the prior myocardial infarction?
  - gold=['ecg', 'echo'] opt=['clinical_notes', 'chest_xray'] — ECG Q waves + echo anterior hypokinesis.

**C29** `P0010`: Has left ventricular function recovered after the infarct?
  - gold=['echo', 'clinical_notes'] opt=['lab_results'] — Echo EF42 improved + notes improving tolerance.

**C30** `P0010`: Is the secondary-prevention medication regimen appropriate post-MI?
  - gold=['medication', 'clinical_notes'] opt=['lab_results'] — DAPT/statin/BB/ARB + post-MI context.

## multi_hop (30)

**M01** `P0001`: Given this patient's exertional chest pain, do the ECG and echo localize the ischemia to the same territory, and are the cardiac enzymes concerning?
  - gold=['clinical_notes', 'ecg', 'echo', 'lab_results'] opt=['heart_sounds'] — Lateral ischemia chain: notes angina + ECG V4-V6 + echo lateral wall + borderline troponin.
  - composed_from: ['What is the chest pain history? (notes)', 'Where is the ischemia on ECG? (ecg)', 'Which wall is hypokinetic on echo? (echo)', 'Is troponin elevated? (labs)']

**M02** `P0001`: Is this patient's cardiovascular risk being adequately managed by the current medications, given the lipid and glucose results and the ischemic ECG findings?
  - gold=['lab_results', 'medication', 'ecg'] opt=['clinical_notes', 'echo'] — Risk management: LDL 142/HbA1c 7.2 vs atorvastatin 40 (subtherapeutic) + lateral ischemia on ECG.
  - composed_from: ['What are the LDL and HbA1c? (labs)', 'What lipid/glucose meds is the patient on? (medication)', 'What do the ECG ischemic findings show? (ecg)']

**M03** `P0001`: Do the structural imaging and auscultation agree about valvular status, and is it consistent with the reported symptoms?
  - gold=['echo', 'heart_sounds', 'clinical_notes'] — Trace MR on echo + grade II apical murmur, mild symptoms.
  - composed_from: ['What valvular disease on echo? (echo)', 'What murmur on auscultation? (heart_sounds)', 'What are the symptoms? (notes)']

**M04** `P0002`: Does the combination of imaging, labs, and symptoms confirm a bacterial pneumonia, and is the antibiotic choice appropriate?
  - gold=['chest_xray', 'lab_results', 'clinical_notes', 'medication'] — CAP: consolidation + WBC/procalcitonin + fever + ceftriaxone/azithromycin.
  - composed_from: ['What does the CXR show? (cxr)', 'What do inflammatory markers show? (labs)', 'What are the symptoms? (notes)', 'What antibiotics were started? (medication)']

**M05** `P0002`: Is the tachycardia explained by the infection rather than a primary cardiac problem, considering the ECG, echo, and clinical context?
  - gold=['ecg', 'echo', 'clinical_notes'] opt=['heart_sounds'] — Sinus tach secondary to fever; echo normal, no cardiac cause.
  - composed_from: ['What does the ECG rhythm show? (ecg)', 'Is the heart structurally normal? (echo)', 'What is the fever/infection context? (notes)']

**M06** `P0002`: Do the auscultation, echo, and ECG together exclude significant structural or ischemic heart disease in this acutely ill patient?
  - gold=['heart_sounds', 'echo', 'ecg'] opt=['clinical_notes'] — Normal auscultation + LVEF 62% + no ischemic ECG changes exclude cardiac disease.
  - composed_from: ['What does auscultation reveal? (heart_sounds)', 'What does the echo show? (echo)', 'Does the ECG show ischemia? (ecg)']

**M07** `P0003`: Across the ECG, echo, and auscultation, is there any objective evidence of cardiac disease to explain the exercise intolerance?
  - gold=['ecg', 'echo', 'heart_sounds', 'clinical_notes'] opt=['chest_xray'] — All normal; deconditioning, no cardiac disease.
  - composed_from: ['What does the ECG show? (ecg)', 'What is the EF? (echo)', 'Any murmurs? (heart_sounds)', 'What is the exercise complaint? (notes)']

**M08** `P0003`: Do the labs, medication review, and clinical history together indicate any cardiovascular risk requiring new treatment?
  - gold=['lab_results', 'medication', 'clinical_notes'] — Normal lipids + no cardiac meds + low-risk history — no new treatment.
  - composed_from: ['What is the lipid/metabolic panel? (labs)', 'What medications is the patient on? (medication)', 'What risk factors are in the history? (notes)']

**M09** `P0003`: Is the normal cardiac imaging consistent with both the physical exam and the resting vitals reported?
  - gold=['echo', 'heart_sounds', 'clinical_notes'] opt=['ecg'] — Normal echo + normal exam + normal vitals all agree.
  - composed_from: ['What does the echo show? (echo)', 'What are the auscultation findings? (heart_sounds)', 'What are the vitals/exam? (notes)']

**M10** `P0004`: How severe is this heart failure decompensation when the symptoms, chest X-ray, echo, and BNP are considered together?
  - gold=['clinical_notes', 'chest_xray', 'echo', 'lab_results'] opt=['heart_sounds', 'ecg'] — Severe ADHF: orthopnea/edema + congestion/effusions + EF25 + BNP1840.
  - composed_from: ['What are the HF symptoms? (notes)', 'What does the CXR show? (cxr)', 'What is the EF? (echo)', 'What is the BNP? (labs)']

**M11** `P0004`: Is the anticoagulation and heart-failure medication regimen appropriate given the atrial fibrillation and reduced renal function?
  - gold=['ecg', 'lab_results', 'medication'] opt=['clinical_notes'] — AFib + eGFR32 + apixaban/carvedilol/losartan/furosemide (ACE allergy).
  - composed_from: ['What rhythm is on ECG? (ecg)', 'What is the renal function? (labs)', 'What is the medication regimen? (medication)']

**M12** `P0004`: Do the echo and auscultation agree on the presence and severity of mitral regurgitation, and does it fit the heart-failure picture?
  - gold=['echo', 'heart_sounds', 'clinical_notes'] opt=['chest_xray'] — Moderate functional MR + holosystolic murmur in decompensated HFrEF.
  - composed_from: ['What MR grade on echo? (echo)', 'What murmur on auscultation? (heart_sounds)', 'What is the HF context? (notes)']

**M13** `P0005`: Taking the ECG, echo, and labs together, are these palpitations benign or is further workup warranted?
  - gold=['ecg', 'echo', 'lab_results'] opt=['clinical_notes', 'heart_sounds'] — Benign PACs + normal echo + normal TSH.
  - composed_from: ['What does the ECG show? (ecg)', 'Is the heart structurally normal? (echo)', 'Is thyroid function normal? (labs)']

**M14** `P0005`: Do the history and ECG together identify a modifiable trigger for the palpitations, and is medication indicated?
  - gold=['clinical_notes', 'ecg', 'medication'] opt=['heart_sounds'] — Caffeine trigger + benign PACs + no antiarrhythmic; counseling only.
  - composed_from: ['What triggers the palpitations? (notes)', 'What arrhythmia is on ECG? (ecg)', 'Is any medication indicated? (medication)']

**M15** `P0005`: Is the rhythm seen on the ECG confirmed by auscultation, and is it structurally benign on echo?
  - gold=['ecg', 'heart_sounds', 'echo'] opt=['clinical_notes'] — PACs on ECG + early beats on auscultation + normal echo.
  - composed_from: ['What does the ECG show? (ecg)', 'What does auscultation reveal? (heart_sounds)', 'Is the echo normal? (echo)']

**M16** `P0006`: Does the evidence across ECG, echo, and chest X-ray establish cor pulmonale from this patient's COPD?
  - gold=['ecg', 'echo', 'chest_xray'] opt=['heart_sounds', 'clinical_notes'] — Cor pulmonale: P pulmonale/RV strain + RV dilation/RVSP42 + hyperinflation.
  - composed_from: ['What right-heart signs on ECG? (ecg)', 'What does the echo show about the RV? (echo)', 'What does the CXR show? (cxr)']

**M17** `P0006`: Do the blood gas, symptoms, and medications together support the diagnosis and treatment of an acute COPD exacerbation?
  - gold=['lab_results', 'clinical_notes', 'medication'] opt=['chest_xray'] — Type 2 resp failure ABG + dyspnea/sputum + prednisolone/doxycycline.
  - composed_from: ['What does the ABG show? (labs)', 'What are the symptoms? (notes)', 'What treatment was started? (medication)']

**M18** `P0006`: Does the elevated pulmonary pressure on echo correlate with the auscultation and ECG findings of right heart involvement?
  - gold=['echo', 'heart_sounds', 'ecg'] opt=['clinical_notes'] — RVSP42 + loud P2 + RV strain/P pulmonale all correlate.
  - composed_from: ['What is the RVSP on echo? (echo)', 'What does auscultation reveal? (heart_sounds)', 'What ECG signs of RH strain? (ecg)']

**M19** `P0007`: Do the ECG, auscultation, and history together establish new-onset atrial fibrillation, and has a reversible cause been excluded?
  - gold=['ecg', 'heart_sounds', 'clinical_notes', 'lab_results'] — New AFib: ECG + irregular auscultation + palpitations, TSH normal.
  - composed_from: ['What rhythm on ECG? (ecg)', 'What does auscultation reveal? (heart_sounds)', 'What is the history? (notes)', 'Is thyroid excluded? (labs)']

**M20** `P0007`: Given the confirmed atrial fibrillation and stroke risk, is the anticoagulation and rate-control regimen appropriate?
  - gold=['ecg', 'medication', 'clinical_notes'] opt=['lab_results'] — AFib + apixaban (CHA2DS2-VASc 3) + metoprolol rate control.
  - composed_from: ['What rhythm on ECG? (ecg)', 'What AFib medications were started? (medication)', 'What are the stroke risk factors? (notes)']

**M21** `P0007`: Do the echo, chest X-ray, and ECG together support a left atrial substrate for the arrhythmia?
  - gold=['echo', 'chest_xray', 'ecg'] opt=['clinical_notes'] — Echo LA 4.1cm + CXR LA enlargement + AFib on ECG.
  - composed_from: ['What is the LA size on echo? (echo)', 'What does the CXR show about the LA? (cxr)', 'What rhythm/atrial activity is on the ECG? (ecg)']

**M22** `P0008`: Do the ECG, echo, and auscultation together demonstrate hypertensive cardiac end-organ damage in this diabetic patient?
  - gold=['ecg', 'echo', 'heart_sounds'] opt=['chest_xray', 'clinical_notes'] — LVH strain + concentric LVH/diastolic dysfx + S4 gallop.
  - composed_from: ['What LVH signs on ECG? (ecg)', 'What does the echo show? (echo)', 'What extra heart sound? (heart_sounds)']

**M23** `P0008`: Given the HbA1c, renal markers, current medications, and echo evidence of cardiac damage, is the regimen adequate for cardiorenal protection?
  - gold=['lab_results', 'medication', 'echo'] opt=['clinical_notes', 'ecg'] — HbA1c10.2/ACR280 + concentric LVH on echo + missing SGLT2/GLP-1 for cardiorenal benefit.
  - composed_from: ['What is the HbA1c and ACR? (labs)', 'What is the current regimen and what is recommended? (medication)', 'What cardiac end-organ damage is on echo? (echo)']

**M24** `P0008`: Does the poor glycemic control in the labs align with both the clinical complications in the notes and the cardiac changes on echo?
  - gold=['lab_results', 'clinical_notes', 'echo'] opt=['ecg', 'heart_sounds'] — HbA1c10.2 + neuropathy/ulcer + concentric LVH/diastolic dysfunction on echo.
  - composed_from: ['What is the glycemic control? (labs)', 'What complications are documented? (notes)', 'What cardiac changes on echo? (echo)']

**M25** `P0009`: Does the exertional syncope, together with the murmur and echo valve data, indicate severe aortic stenosis, and is any medication a concern?
  - gold=['clinical_notes', 'heart_sounds', 'echo', 'medication'] — Severe AS: syncope + 4/6 murmur to carotids + AVA0.7 + amlodipine caution.
  - composed_from: ['What is the syncope history? (notes)', 'Describe the murmur. (heart_sounds)', 'What is the valve area/gradient? (echo)', 'Any medication concern? (medication)']

**M26** `P0009`: Do the ECG, echo, and auscultation together demonstrate the pressure overload expected from severe aortic stenosis?
  - gold=['ecg', 'echo', 'heart_sounds'] opt=['chest_xray', 'clinical_notes'] — ECG LVH strain + echo concentric LVH/severe AS + 4/6 murmur with diminished S2.
  - composed_from: ['What LVH signs on ECG? (ecg)', 'What does the echo show about LV and valve? (echo)', 'What does the murmur/S2 indicate? (heart_sounds)']

**M27** `P0009`: Is the syncope workup supported by both the chest X-ray and lab findings for this valve disease?
  - gold=['chest_xray', 'lab_results', 'clinical_notes'] opt=['echo'] — CXR valve calcification/post-stenotic dilation + BNP480 + syncope.
  - composed_from: ['What does the CXR show? (cxr)', 'What is the BNP? (labs)', 'What is the syncope history? (notes)']

**M28** `P0010`: Do the ECG and echo together characterize the prior anterior infarct and the current degree of LV recovery?
  - gold=['ecg', 'echo', 'clinical_notes'] opt=['chest_xray'] — Q waves V1-V3 + EF42 (improved from 35) anterior hypokinesis + rehab progress.
  - composed_from: ['What does the ECG show of prior MI? (ecg)', 'What is the EF and wall motion? (echo)', 'What is the recovery history? (notes)']

**M29** `P0010`: Given the post-MI status and lipid results, is the secondary-prevention medication regimen optimized?
  - gold=['clinical_notes', 'lab_results', 'medication'] — Post-STEMI + LDL58 at goal + DAPT/statin/BB/ARB.
  - composed_from: ['What is the post-MI status? (notes)', 'Is the LDL at goal? (labs)', 'What is the prevention regimen? (medication)']

**M30** `P0010`: Is the reduced ejection fraction on echo consistent with the ECG infarct pattern and the absence of recurrent ischemia in the labs?
  - gold=['echo', 'ecg', 'lab_results'] opt=['clinical_notes'] — EF42 anterior hypokinesis + Q waves V1-V3 + undetectable troponin.
  - composed_from: ['What is the EF and wall motion? (echo)', 'What is the ECG infarct pattern? (ecg)', 'Is troponin negative? (labs)']

## KB seeded sets (30)

**KBS01** `P0001` gold=['ecg', 'echo'] (blatant): Swapped echo to contradict; gold pair ['ecg', 'echo'] (blatant).

**KBS02** `P0001` gold=['echo', 'heart_sounds'] (moderate): Swapped heart_sounds to contradict; gold pair ['echo', 'heart_sounds'] (moderate).

**KBS03** `P0001` gold=['ecg', 'lab_results'] (moderate): Swapped lab_results to contradict; gold pair ['ecg', 'lab_results'] (moderate).

**KBS04** `P0002` gold=['clinical_notes', 'chest_xray'] (blatant): Swapped chest_xray to contradict; gold pair ['clinical_notes', 'chest_xray'] (blatant).

**KBS05** `P0002` gold=['clinical_notes', 'lab_results'] (moderate): Swapped lab_results to contradict; gold pair ['clinical_notes', 'lab_results'] (moderate).

**KBS06** `P0002` gold=['chest_xray', 'echo'] (subtle): Swapped echo to contradict; gold pair ['chest_xray', 'echo'] (subtle).

**KBS07** `P0003` gold=['ecg', 'heart_sounds'] (blatant): Swapped ecg to contradict; gold pair ['ecg', 'heart_sounds'] (blatant).

**KBS08** `P0003` gold=['echo', 'clinical_notes'] (moderate): Swapped echo to contradict; gold pair ['echo', 'clinical_notes'] (moderate).

**KBS09** `P0003` gold=['lab_results', 'clinical_notes'] (subtle): Swapped lab_results to contradict; gold pair ['lab_results', 'clinical_notes'] (subtle).

**KBS10** `P0004` gold=['clinical_notes', 'echo'] (blatant): Swapped echo to contradict; gold pair ['clinical_notes', 'echo'] (blatant).

**KBS11** `P0004` gold=['ecg', 'heart_sounds'] (moderate): Swapped ecg to contradict; gold pair ['ecg', 'heart_sounds'] (moderate).

**KBS12** `P0004` gold=['clinical_notes', 'lab_results'] (moderate): Swapped lab_results to contradict; gold pair ['clinical_notes', 'lab_results'] (moderate).

**KBS13** `P0005` gold=['ecg', 'echo'] (moderate): Swapped ecg to contradict; gold pair ['ecg', 'echo'] (moderate).

**KBS14** `P0005` gold=['echo', 'clinical_notes'] (moderate): Swapped echo to contradict; gold pair ['echo', 'clinical_notes'] (moderate).

**KBS15** `P0005` gold=['lab_results', 'clinical_notes'] (subtle): Swapped lab_results to contradict; gold pair ['lab_results', 'clinical_notes'] (subtle).

**KBS16** `P0006` gold=['ecg', 'echo'] (blatant): Swapped echo to contradict; gold pair ['ecg', 'echo'] (blatant).

**KBS17** `P0006` gold=['clinical_notes', 'lab_results'] (moderate): Swapped lab_results to contradict; gold pair ['clinical_notes', 'lab_results'] (moderate).

**KBS18** `P0006` gold=['clinical_notes', 'chest_xray'] (subtle): Swapped chest_xray to contradict; gold pair ['clinical_notes', 'chest_xray'] (subtle).

**KBS19** `P0007` gold=['ecg', 'clinical_notes'] (blatant): Swapped ecg to contradict; gold pair ['ecg', 'clinical_notes'] (blatant).

**KBS20** `P0007` gold=['lab_results', 'clinical_notes'] (moderate): Swapped lab_results to contradict; gold pair ['lab_results', 'clinical_notes'] (moderate).

**KBS21** `P0007` gold=['echo', 'chest_xray'] (subtle): Swapped echo to contradict; gold pair ['echo', 'chest_xray'] (subtle).

**KBS22** `P0008` gold=['lab_results', 'clinical_notes'] (blatant): Swapped lab_results to contradict; gold pair ['lab_results', 'clinical_notes'] (blatant).

**KBS23** `P0008` gold=['ecg', 'echo'] (moderate): Swapped echo to contradict; gold pair ['ecg', 'echo'] (moderate).

**KBS24** `P0008` gold=['heart_sounds', 'echo'] (subtle): Swapped heart_sounds to contradict; gold pair ['heart_sounds', 'echo'] (subtle).

**KBS25** `P0009` gold=['heart_sounds', 'echo'] (blatant): Swapped echo to contradict; gold pair ['heart_sounds', 'echo'] (blatant).

**KBS26** `P0009` gold=['heart_sounds', 'echo'] (moderate): Swapped heart_sounds to contradict; gold pair ['heart_sounds', 'echo'] (moderate).

**KBS27** `P0009` gold=['ecg', 'echo'] (subtle): Swapped ecg to contradict; gold pair ['ecg', 'echo'] (subtle).

**KBS28** `P0010` gold=['ecg', 'echo'] (blatant): Swapped ecg to contradict; gold pair ['ecg', 'echo'] (blatant).

**KBS29** `P0010` gold=['ecg', 'echo'] (moderate): Swapped echo to contradict; gold pair ['ecg', 'echo'] (moderate).

**KBS30** `P0010` gold=['ecg', 'lab_results'] (subtle): Swapped lab_results to contradict; gold pair ['ecg', 'lab_results'] (subtle).

