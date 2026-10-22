"""
Stage 3: Knowledge Bus conflict-detection runner + scorer. Calls
build_knowledge_bus() directly (pure function, no UI) on each set, k repetitions
(the Bus is a single stochastic Gemini call, so we report consistency too).

Ground truth:
  clean sets  -> no contradictions. Any contradicted_by link is a false positive.
  seeded sets -> exactly one gold_conflict [A,B] that MUST appear (A lists B or B lists A).

Metrics:
  recall   = seeded sets whose gold pair was flagged (majority of reps) / seeded sets
  FP rate  = clean sets with >=1 contradiction (majority of reps) / clean sets
             -- this is the precision signal: a seeded swap can legitimately contradict
             several findings, so "extra" links on seeded sets are not false positives;
             the clean sets are where any flagged conflict is unambiguously wrong.
  consistency = fraction of reps that agree with the majority verdict per set

Usage: PYTHONPATH=. python eval/score_kb.py [pilot|full] [--reps K]
"""
import sys
import json
from collections import defaultdict

from eval.common import DATA, run_dir, read_jsonl, write_jsonl
from src.agents.base_agent import Finding
from src.agents.knowledge_bus import build_knowledge_bus


def to_findings(raw):
    """kb-set 'findings' [{agent,summary}] -> [Finding] (file/web_path unused by the Bus)."""
    return [Finding(agent=f["agent"], file="", web_path="", summary=f["summary"]) for f in raw]


def contradiction_pairs(bus):
    """Set of unordered agent pairs the Bus flagged as contradicting."""
    pairs = set()
    for agent, entry in bus.items():
        for ref in entry.get("contradicted_by", []):
            other = ref.get("agent")
            if other:
                pairs.add(frozenset((agent, other)))
    return pairs


def run_set(kbset, reps):
    findings = to_findings(kbset["findings"])
    pid, info = kbset["patient_id"], {"name": kbset["patient_id"], "conditions": []}
    rep_pairs = []
    for _ in range(reps):
        bus = build_knowledge_bus(findings, pid, info)
        rep_pairs.append(contradiction_pairs(bus))
    return rep_pairs


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    tag = args[0] if args else "pilot"
    reps = int(sys.argv[sys.argv.index("--reps") + 1]) if "--reps" in sys.argv else 3

    sets = read_jsonl(DATA / (f"kb_sets_{tag}.jsonl" if tag == "pilot" else "kb_sets.jsonl"))
    out = run_dir(tag) / "kb_verdicts.jsonl"
    done = {r["id"] for r in read_jsonl(out)} if out.exists() else set()
    todo = [s for s in sets if s["id"] not in done]
    print(f"{len(sets)} KB sets x {reps} reps; {len(done)} done, running {len(todo)} ...\n")

    # incremental append (resume-safe): one line per set as it completes
    with open(out, "a") as f:
        for ks in todo:
            gold = frozenset(ks["gold_conflict"]) if ks["gold_conflict"] else None
            rep_pairs = run_set(ks, reps)
            rec = {"id": ks["id"], "type": ks["type"],
                   "gold": sorted(gold) if gold else None,
                   "rep_pairs": [sorted(sorted(x) for x in p) for p in rep_pairs]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if ks["type"] == "seeded":
                hit = sum(1 for p in rep_pairs if gold in p)
                print(f"  {ks['id']} seeded gold={sorted(gold)} {hit}/{reps} hit "
                      f"{'HIT' if hit > reps/2 else 'MISS'}", flush=True)
            else:
                anyc = sum(1 for p in rep_pairs if p)
                print(f"  {ks['id']} clean  {anyc}/{reps} flagged "
                      f"{'clean-OK' if anyc <= reps/2 else 'FALSE-POSITIVE'}", flush=True)

    # recompute headline metrics from the full file (correct across resumes)
    detail = read_jsonl(out)
    seeded = [r for r in detail if r["type"] == "seeded"]
    clean = [r for r in detail if r["type"] == "clean"]
    hits = sum(1 for r in seeded
               if sum(1 for p in r["rep_pairs"] if r["gold"] and sorted(r["gold"]) in [sorted(x) for x in p]) > len(r["rep_pairs"]) / 2)
    fps = sum(1 for r in clean if sum(1 for p in r["rep_pairs"] if p) > len(r["rep_pairs"]) / 2)
    print(f"\nKNOWLEDGE BUS RESULTS ({tag}, reps={reps}), {len(detail)}/{len(sets)} sets")
    if seeded:
        print(f"  seeded recall (majority): {hits}/{len(seeded)} = {hits/len(seeded)*100:.0f}%")
    if clean:
        print(f"  clean false-positive rate (precision signal): {fps}/{len(clean)} = {fps/len(clean)*100:.0f}%")


if __name__ == "__main__":
    main()
