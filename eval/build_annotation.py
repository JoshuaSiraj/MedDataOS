"""
Build a blind human-validation sheet for the citation judge (validates a run's
verdicts against a human annotator). Stratified so every consequential verdict
(overstated / fabricated / ungrounded) is human-checked, plus a random sample of
faithful/grounded to catch false negatives.

Outputs (under results/<tag>/validation/):
  annotation_sheet.csv   blind — claim + evidence + empty LABEL/NOTES columns
  annotation_key.jsonl   hidden — the judge verdict per claim (for scoring later)
  INSTRUCTIONS.md        the rubric the annotator applies

Run: PYTHONPATH=. python eval/build_annotation.py full_v2
"""
import sys
import csv
import json
import random

from eval.common import run_dir, read_jsonl, load_patient_info

random.seed(7)  # reproducible sample

SAMPLE = {"faithful": 80, "grounded": 15}  # flagged classes fully included


def evidence_for(claim, citation_by_id, all_findings, demo):
    if claim["kind"] == "cited":
        cites = [citation_by_id.get(cid) for cid in claim["cited_ids"]]
        return " | ".join(f"[{c['id']}·{c['agent']}] {c['summary']}" for c in cites if c)
    # uncited: grounded if in ANY finding or the demographics
    return f"DEMOGRAPHICS: {demo}  ||  ALL FINDINGS: " + \
           " | ".join(f"[{f['agent']}] {f['summary']}" for f in all_findings)


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "full_v2"
    d = run_dir(tag)
    verdicts = read_jsonl(d / "citation_verdicts.jsonl")
    raw = {r["id"]: r for r in read_jsonl(d / "raw_queries.jsonl")}

    # gather all claims with their evidence + hidden judge verdict
    records = []
    for vr in verdicts:
        qid = vr["id"]
        rr = raw[qid]
        cit_by_id = {c["id"]: c for c in rr["citations"]}
        demo = ", ".join(load_patient_info(rr["patient_id"]).get("conditions", [])) or "none"
        for j, c in enumerate(vr["claims"]):
            records.append({
                "cid": f"{qid}#{j}", "query_id": qid, "patient": rr["patient_id"],
                "kind": c["kind"], "claim_text": c["claim_text"],
                "evidence": evidence_for(c, cit_by_id, rr["citations"], demo),
                "judge_verdict": c["verdict"],
            })

    by_v = {}
    for r in records:
        by_v.setdefault(r["judge_verdict"], []).append(r)

    # select: all flagged + sampled faithful/grounded + all not_a_claim
    selected = []
    for v in ("overstated", "fabricated", "ungrounded"):
        selected += by_v.get(v, [])
    for v, n in SAMPLE.items():
        pool = by_v.get(v, [])
        selected += random.sample(pool, min(n, len(pool)))
    selected += by_v.get("not_a_claim", [])

    random.shuffle(selected)  # order must not leak verdict

    vdir = d / "validation"
    vdir.mkdir(exist_ok=True)
    # blind sheet
    with open(vdir / "annotation_sheet.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["idx", "claim_id", "query_id", "patient", "kind", "claim_text",
                    "evidence", "LABEL", "NOTES"])
        for i, r in enumerate(selected, 1):
            w.writerow([i, r["cid"], r["query_id"], r["patient"], r["kind"],
                        r["claim_text"], r["evidence"], "", ""])
    # hidden key
    with open(vdir / "annotation_key.jsonl", "w") as f:
        for r in selected:
            f.write(json.dumps({"claim_id": r["cid"], "kind": r["kind"],
                                "judge_verdict": r["judge_verdict"]}) + "\n")

    counts = {v: len(by_v.get(v, [])) for v in by_v}
    sel_counts = {}
    for r in selected:
        sel_counts[r["judge_verdict"]] = sel_counts.get(r["judge_verdict"], 0) + 1
    (vdir / "INSTRUCTIONS.md").write_text(INSTRUCTIONS)
    print(f"Wrote {vdir}/annotation_sheet.csv ({len(selected)} claims)")
    print(f"  full population by judge verdict: {counts}")
    print(f"  sampled by (hidden) judge verdict: {sel_counts}")
    print(f"Key + INSTRUCTIONS written. Annotator fills LABEL blind; then run score_agreement.py")


INSTRUCTIONS = """# Citation-judge validation — annotator instructions

For each row, read `claim_text` and `evidence`, then put ONE label in the LABEL
column. Do not look at any judge output — this is a blind check.

If `kind` = **cited** (the claim cited specific findings, shown in `evidence`):
- `faithful`   — the claim's factual content is supported by the cited finding(s),
                 including reasonable clinical interpretation/synthesis of them.
- `overstated` — asserts severity/certainty/magnitude BEYOND what the finding states.
- `fabricated` — asserts a fact absent from, or contradicting, the cited finding(s).

If `kind` = **uncited** (no citation; `evidence` shows demographics + all findings):
- `grounded`     — the fact appears in, or is directly entailed by, any finding or demographics.
- `ungrounded`   — a specific clinical assertion not backed by any finding or demographics.
- `not_a_claim`  — connective/framing text with no checkable clinical fact.

Use NOTES for anything ambiguous. Aim for consistency with the definitions above.
"""


if __name__ == "__main__":
    main()
