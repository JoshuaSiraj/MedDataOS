"""
Phase B: Pilot dataset (10 queries + 2 KB sets) + human review sheet.

The pilot is the DEV set: we may inspect its results and tune judge prompts /
schema before authoring the frozen full set. It spans all three query tiers and
both probe types, plus one clean and one seeded KB set, so Checkpoint 1 locks
question style, gold-set philosophy, and JSONL schema before mass production.

Run: python eval/data/build_pilot.py
Writes: queries_pilot.jsonl, kb_sets_pilot.jsonl, REVIEW_pilot.md
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STUBS = ROOT / "stubs"

# ---------------------------------------------------------------------------
# QUERY SCHEMA (one JSON object per line in queries_pilot.jsonl):
#   id              unique id
#   tier            "simple" | "cross_modal" | "multi_hop"
#   patient_id      active patient
#   query           the natural-language question sent to run_pipeline()
#   gold_agents     agents that MUST fire (scored)
#   optional_agents agents that may fire without penalty (neither FP nor FN)
#   composed_from   (multi_hop) source per-modality questions, for auditability
#   modality_override  (probe) modalities to STRIP from patient_info.data_dates
#   probe_type      null | "no_tool" | "unavailable_modality"
#   rationale       one line: why this gold set, anchored to fact_inventory
# ---------------------------------------------------------------------------

QUERIES = [
    # ---- SIMPLE (single-modality lookups anchored to one fact) ----
    {
        "id": "Q01", "tier": "simple", "patient_id": "P0009",
        "query": "What is this patient's aortic valve area and mean gradient?",
        "gold_agents": ["echo"], "optional_agents": [],
        "composed_from": None, "modality_override": None, "probe_type": None,
        "rationale": "AVA 0.7 cm2 / mean gradient 52 are echo-only quantitative facts (P0009 echo).",
    },
    {
        "id": "Q02", "tier": "simple", "patient_id": "P0001",
        "query": "What is this patient's most recent HbA1c?",
        "gold_agents": ["lab_results"], "optional_agents": [],
        "composed_from": None, "modality_override": None, "probe_type": None,
        "rationale": "HbA1c 7.2% is a lab value only (P0001 lab_results).",
    },
    # ---- PROBE: no-tool (general knowledge, no patient data needed) ----
    {
        "id": "Q03", "tier": "simple", "patient_id": "P0003",
        "query": "In general, what does left ventricular ejection fraction measure?",
        "gold_agents": [], "optional_agents": [],
        "composed_from": None, "modality_override": None, "probe_type": "no_tool",
        "rationale": "Definitional question answerable from general knowledge; no agent should fire.",
    },
    # ---- PROBE: unavailable-modality (echo stripped; must not call echo) ----
    {
        "id": "Q04", "tier": "simple", "patient_id": "P0003",
        "query": "What did this patient's echocardiogram show about LV function?",
        "gold_agents": [], "optional_agents": [],
        "composed_from": None, "modality_override": ["echo"], "probe_type": "unavailable_modality",
        "rationale": "Echo removed from data_dates; prompt says only call available modalities, so echo must NOT fire.",
    },

    # ---- CROSS-MODAL (question needs 2-3 correlated modalities) ----
    {
        "id": "Q05", "tier": "cross_modal", "patient_id": "P0001",
        "query": "Is there any evidence of myocardial ischemia in this patient?",
        "gold_agents": ["ecg", "echo", "clinical_notes"],
        "optional_agents": ["lab_results", "heart_sounds"],
        "composed_from": None, "modality_override": None, "probe_type": None,
        "rationale": "Ischemia signal spans ECG (ST-dep V4-V6), echo (lateral hypokinesis), notes (exertional angina); troponin/BNP optional supporting.",
    },
    {
        "id": "Q06", "tier": "cross_modal", "patient_id": "P0004",
        "query": "Assess this patient's volume status and heart failure severity.",
        "gold_agents": ["clinical_notes", "chest_xray", "echo", "lab_results"],
        "optional_agents": ["heart_sounds", "ecg"],
        "composed_from": None, "modality_override": None, "probe_type": None,
        "rationale": "HF severity: notes (orthopnea/edema), CXR (congestion/effusions), echo (EF 25%), labs (BNP 1840); S3/AFib optional.",
    },
    {
        "id": "Q07", "tier": "cross_modal", "patient_id": "P0006",
        "query": "Is there evidence of right heart strain or pulmonary hypertension?",
        "gold_agents": ["ecg", "echo"],
        "optional_agents": ["chest_xray", "heart_sounds"],
        "composed_from": None, "modality_override": None, "probe_type": None,
        "rationale": "RV strain: ECG (P pulmonale, RAD, RV strain) + echo (RV dilation, RVSP 42, D-sign); CXR hyperinflation and loud P2 optional.",
    },

    # ---- MULTI-HOP (composed from several per-modality questions) ----
    {
        "id": "Q08", "tier": "multi_hop", "patient_id": "P0009",
        "query": "This patient has had exertional syncope. What do the murmur and valve findings point to, and is any current medication a concern for that diagnosis?",
        "gold_agents": ["clinical_notes", "heart_sounds", "echo", "medication"],
        "optional_agents": [],
        "composed_from": [
            "What is the cause of this patient's exertional syncope? (notes)",
            "Describe the systolic murmur. (heart_sounds)",
            "What is the aortic valve area and gradient? (echo)",
            "Are any current medications a concern here? (medication)",
        ],
        "modality_override": None, "probe_type": None,
        "rationale": "Severe AS chain: syncope (notes) + 4/6 murmur to carotids (heart_sounds) + AVA 0.7 (echo) + amlodipine caution in severe AS (medication).",
    },
    {
        "id": "Q09", "tier": "multi_hop", "patient_id": "P0008",
        "query": "How well controlled is this patient's diabetes, is there evidence of cardiac end-organ damage, and does the medication regimen address the cardiorenal risk?",
        "gold_agents": ["lab_results", "ecg", "echo", "medication"],
        "optional_agents": ["clinical_notes", "heart_sounds"],
        "composed_from": [
            "What is the HbA1c and renal status? (lab_results)",
            "Is there LVH or strain on the ECG? (ecg)",
            "Does the echo show hypertensive cardiac changes? (echo)",
            "Does the medication list cover cardiorenal protection? (medication)",
        ],
        "modality_override": None, "probe_type": None,
        "rationale": "DM control (HbA1c 10.2, ACR 280) + LVH strain (ecg) + concentric LVH/diastolic dysfx (echo) + SGLT2/GLP-1 gap (medication).",
    },
    {
        "id": "Q10", "tier": "multi_hop", "patient_id": "P0010",
        "query": "What do the ECG and echocardiogram tell us about this patient's prior heart attack, and is the current antiplatelet regimen appropriate?",
        "gold_agents": ["ecg", "echo", "medication"],
        "optional_agents": ["clinical_notes"],
        "composed_from": [
            "What does the ECG show of the prior infarct? (ecg)",
            "What is the EF and wall motion? (echo)",
            "Is the antiplatelet regimen appropriate? (medication)",
        ],
        "modality_override": None, "probe_type": None,
        "rationale": "Post-anterior STEMI: Q waves V1-V3 (ecg) + EF 42% anterior hypokinesis (echo) + DAPT aspirin+clopidogrel 9mo remaining (medication).",
    },
]

# ---------------------------------------------------------------------------
# KB SET SCHEMA (one JSON object per line in kb_sets_pilot.jsonl):
#   id            unique id
#   patient_id    base patient
#   type          "clean" | "seeded"
#   findings      list of {agent, summary} handed to build_knowledge_bus()
#   gold_conflict (seeded) [agentA, agentB] pair that MUST be flagged; null if clean
#   seed_rationale why the swapped finding contradicts the rest
# ---------------------------------------------------------------------------

def load_findings(pid):
    """Load a patient's real findings as [{agent, summary}], in stub order."""
    data = json.loads((STUBS / f"{pid}.json").read_text())
    return [{"agent": agent, "summary": v["summary"]} for agent, v in data.items()]


def seeded_p0001():
    """P0001: replace the echo finding (LVEF 45%, lateral hypokinesis -> agrees
    with ECG lateral ischemia) with a NORMAL echo. Now echo contradicts the
    ECG (lateral ischemia), and is inconsistent with borderline troponin / BNP.
    Gold conflict: ecg <-> echo."""
    findings = load_findings("P0001")
    for f in findings:
        if f["agent"] == "echo":
            f["summary"] = (
                "Left ventricular ejection fraction estimated at 62% (normal). "
                "No regional wall motion abnormalities. Normal left atrial size. "
                "No valvular disease. Normal right ventricular size and function. "
                "No pericardial effusion. Normal diastolic function."
            )
    return findings


KB_SETS = [
    {
        "id": "KB01", "patient_id": "P0003", "type": "clean",
        "findings": load_findings("P0003"),
        "gold_conflict": None,
        "seed_rationale": "Healthy wellness exam; all modalities internally consistent (normal). Bus must flag NO contradictions.",
    },
    {
        "id": "KB02", "patient_id": "P0001", "type": "seeded",
        "findings": seeded_p0001(),
        "gold_conflict": ["ecg", "echo"],
        "seed_rationale": "Echo swapped to fully normal LV function, contradicting the ECG's lateral ischemia (ST-dep V4-V6) and lateral-territory story.",
    },
]


def write_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_review():
    lines = ["# Pilot Review Sheet\n",
             "Approve or correct each gold label. This locks question style, gold-set philosophy, and schema before the full set.\n",
             "\n## Queries (10)\n"]
    for q in QUERIES:
        lines.append(f"### {q['id']} — {q['tier']}" + (f" — probe: {q['probe_type']}" if q['probe_type'] else "") + "\n")
        lines.append(f"- **Patient:** {q['patient_id']}\n")
        lines.append(f"- **Query:** {q['query']}\n")
        lines.append(f"- **Gold agents:** {q['gold_agents'] or '(none — should call no tools)'}\n")
        if q["optional_agents"]:
            lines.append(f"- **Optional (no penalty):** {q['optional_agents']}\n")
        if q["modality_override"]:
            lines.append(f"- **Stripped modalities:** {q['modality_override']}\n")
        if q["composed_from"]:
            lines.append(f"- **Composed from:**\n")
            for s in q["composed_from"]:
                lines.append(f"    - {s}\n")
        lines.append(f"- **Rationale:** {q['rationale']}\n\n")

    lines.append("## Knowledge Bus sets (2)\n")
    for k in KB_SETS:
        lines.append(f"### {k['id']} — {k['type']} — base {k['patient_id']}\n")
        if k["gold_conflict"]:
            lines.append(f"- **Gold conflict pair:** {k['gold_conflict']}\n")
        else:
            lines.append(f"- **Gold:** no contradictions (clean)\n")
        lines.append(f"- **Rationale:** {k['seed_rationale']}\n")
        lines.append(f"- **Findings handed to the Bus:**\n")
        for f in k["findings"]:
            lines.append(f"    - `{f['agent']}`: {f['summary'][:110]}{'...' if len(f['summary'])>110 else ''}\n")
        lines.append("\n")
    (HERE / "REVIEW_pilot.md").write_text("".join(lines))


def main():
    write_jsonl(HERE / "queries_pilot.jsonl", QUERIES)
    write_jsonl(HERE / "kb_sets_pilot.jsonl", KB_SETS)
    write_review()
    tiers = {}
    for q in QUERIES:
        tiers[q["tier"]] = tiers.get(q["tier"], 0) + 1
    print("Wrote queries_pilot.jsonl:", len(QUERIES), "queries", tiers)
    print("Wrote kb_sets_pilot.jsonl:", len(KB_SETS), "sets")
    print("Wrote REVIEW_pilot.md")


if __name__ == "__main__":
    main()
