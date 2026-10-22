"""
Score judge-human agreement once the annotation sheet's LABEL column is filled.
Reads results/<tag>/validation/{annotation_sheet.csv, annotation_key.jsonl}.

Reports:
  - exact-label agreement (all filled rows)
  - binary agreement + Cohen's kappa on failure vs non-failure
    (failure = overstated/fabricated/ungrounded; ok = faithful/grounded/not_a_claim)
  - judge false-positive rate (judge flagged, human says ok) and
    false-negative rate (human flags, judge said ok)
  - corrected faithfulness estimate for the run

Run: PYTHONPATH=. python eval/score_agreement.py full_v2
"""
import sys
import csv

from eval.common import run_dir, read_jsonl

FAILURE = {"overstated", "fabricated", "ungrounded"}


def kappa(pairs):
    """Cohen's kappa on binary (is_failure) labels."""
    n = len(pairs)
    if not n:
        return 0.0
    po = sum(1 for a, b in pairs if a == b) / n
    ja = sum(1 for a, _ in pairs if a) / n   # judge failure rate
    ha = sum(1 for _, b in pairs if b) / n   # human failure rate
    pe = ja * ha + (1 - ja) * (1 - ha)
    return (po - pe) / (1 - pe) if pe != 1 else 1.0


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "full_v2"
    vdir = run_dir(tag) / "validation"
    key = {r["claim_id"]: r["judge_verdict"] for r in read_jsonl(vdir / "annotation_key.jsonl")}

    rows = list(csv.DictReader(open(vdir / "annotation_sheet.csv")))
    filled = [r for r in rows if r["LABEL"].strip()]
    if not filled:
        print("No LABEL values filled yet. Annotator must complete the sheet first.")
        return

    exact = 0
    bin_pairs = []
    judge_fp = judge_fn = 0
    for r in filled:
        human = r["LABEL"].strip().lower()
        judge = key[r["claim_id"]]
        exact += int(human == judge)
        jf, hf = judge in FAILURE, human in FAILURE
        bin_pairs.append((jf, hf))
        if jf and not hf:
            judge_fp += 1
        if hf and not jf:
            judge_fn += 1

    n = len(filled)
    po = sum(1 for a, b in bin_pairs if a == b) / n
    print(f"Judge validation ({tag}) — {n}/{len(rows)} rows labeled\n")
    print(f"  exact-label agreement:        {exact/n*100:.0f}%")
    print(f"  binary (failure) agreement:   {po*100:.0f}%")
    print(f"  Cohen's kappa (failure):      {kappa(bin_pairs):.2f}")
    n_judge_fail = sum(1 for a, _ in bin_pairs if a)
    n_human_fail = sum(1 for _, b in bin_pairs if b)
    print(f"  judge false positives (flagged, human ok): {judge_fp}/{n_judge_fail} of judge-flagged")
    print(f"  judge false negatives (human flags, judge ok): {judge_fn}/{n_human_fail} of human-flagged")

    # corrected faithfulness: judge cited-faithfulness was reported on the full run;
    # here we report the human-confirmed failure precision to adjust it.
    if n_judge_fail:
        print(f"\n  -> of claims the judge called failures, humans confirm "
              f"{(n_judge_fail-judge_fp)/n_judge_fail*100:.0f}% as genuine.")
        print("     Use this to state faithfulness as a human-validated floor in the paper.")


if __name__ == "__main__":
    main()
