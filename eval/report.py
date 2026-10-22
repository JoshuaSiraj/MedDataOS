"""
Aggregate a run's three stages into a self-contained, browsable summary:
  results/<tag>/manifest.json  -- models, seed, date, counts (reproducibility)
  results/<tag>/REPORT.md      -- headline numbers + failure cases, human-readable

Reads the raw stage outputs already written by run_queries / judge_citations /
score_kb (and recomputes the same metrics so REPORT never disagrees with them).

Usage: PYTHONPATH=. python eval/report.py <tag> [--date YYYY-MM-DD]
"""
import sys
import json
from collections import Counter, defaultdict

from eval.common import run_dir, read_jsonl
from src.core.orchestrator import GEMINI_MODEL
from eval.judge_citations import JUDGE_MODEL, JUDGE_SEED
from eval.score_routing import score as score_routing, prf


def routing_block(rows):
    per_tier, fails = score_routing(rows)
    lines = ["## Routing\n\n", "| tier | n | exact (tolerant) | precision | recall | F1 |\n",
             "|---|---|---|---|---|---|\n"]
    for k in ["simple", "cross_modal", "multi_hop", "ALL"]:
        if k not in per_tier:
            continue
        t = per_tier[k]; p, r, f = prf(t)
        lines.append(f"| {k} | {t['n']} | {t['tol']/t['n']*100:.0f}% | {p:.2f} | {r:.2f} | {f:.2f} |\n")
    if fails:
        lines.append("\n**Routing failures (exact-tolerant misses):**\n\n")
        for fid, tier, req, inv, missed, extra in fails:
            d = []
            if missed: d.append(f"missed {missed}")
            if extra: d.append(f"extra {extra}")
            lines.append(f"- `{fid}` ({tier}): {'; '.join(d)} — required={req}, invoked={inv}\n")
    return lines, per_tier


def citation_block(verdict_rows):
    claims = [c for r in verdict_rows for c in r["claims"]]
    cited = Counter(c["verdict"] for c in claims if c["kind"] == "cited")
    uncited = Counter(c["verdict"] for c in claims if c["kind"] == "uncited")
    n = sum(cited.values())
    factual = uncited["grounded"] + uncited["ungrounded"]
    faith = cited["faithful"] / n * 100 if n else 0
    halluc = uncited["ungrounded"] / factual * 100 if factual else 0
    lines = ["\n## Citations\n\n",
             f"- cited claims: **{n}** — faithful {cited['faithful']}, overstated {cited['overstated']}, fabricated {cited['fabricated']}\n",
             f"- **faithfulness: {faith:.0f}%**  (overstatement {cited['overstated']/n*100 if n else 0:.0f}%, fabrication {cited['fabricated']/n*100 if n else 0:.0f}%)\n",
             f"- uncited factual claims: {factual} — grounded {uncited['grounded']}, ungrounded {uncited['ungrounded']}\n",
             f"- **hallucination rate: {halluc:.0f}%**  (ungrounded / uncited factual)\n"]
    # a few example failures
    ex = [c for c in claims if c["verdict"] in ("overstated", "fabricated", "ungrounded")][:6]
    if ex:
        lines.append("\n**Example flagged claims:**\n\n")
        for c in ex:
            lines.append(f"- [{c['verdict']}] {c['claim_text'][:110]}\n")
    return lines, {"faithfulness_pct": round(faith), "hallucination_pct": round(halluc), "n_cited": n}


def kb_block(kb_rows, reps_guess=3):
    n_seeded = n_clean = hits = fps = 0
    consist = []
    for r in kb_rows:
        gold = frozenset(r["gold"]) if r["gold"] else None
        reps = [set(frozenset(p) for p in rep) for rep in r["rep_pairs"]]
        k = len(reps)
        if r["type"] == "seeded":
            n_seeded += 1
            hit = sum(1 for p in reps if gold in p)
            hits += int(hit > k / 2)
            consist.append(max(hit, k - hit) / k)
        else:
            n_clean += 1
            anyc = sum(1 for p in reps if p)
            fps += int(anyc > k / 2)
            consist.append(max(anyc, k - anyc) / k)
    lines = ["\n## Knowledge Bus\n\n",
             f"- seeded recall (majority): {hits}/{n_seeded} = {hits/n_seeded*100 if n_seeded else 0:.0f}%\n",
             f"- clean false-positive rate: {fps}/{n_clean} = {fps/n_clean*100 if n_clean else 0:.0f}%\n",
             f"- mean consistency across reps: {sum(consist)/len(consist)*100 if consist else 0:.0f}%\n"]
    return lines, {"seeded_recall_pct": round(hits/n_seeded*100) if n_seeded else None,
                   "clean_fp_pct": round(fps/n_clean*100) if n_clean else None}


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "full"
    date = sys.argv[sys.argv.index("--date") + 1] if "--date" in sys.argv else "unknown"
    d = run_dir(tag)

    raw = read_jsonl(d / "raw_queries.jsonl")
    verdicts = read_jsonl(d / "citation_verdicts.jsonl") if (d / "citation_verdicts.jsonl").exists() else []
    kb = read_jsonl(d / "kb_verdicts.jsonl") if (d / "kb_verdicts.jsonl").exists() else []

    rb, per_tier = routing_block(raw)
    cb, cite_summary = citation_block(verdicts) if verdicts else ([], {})
    kbb, kb_summary = kb_block(kb) if kb else ([], {})

    latencies = [r["latency_s"] for r in raw]
    med_lat = sorted(latencies)[len(latencies) // 2] if latencies else None

    manifest = {
        "run": tag, "date": date,
        "system_model": GEMINI_MODEL, "judge_model": JUDGE_MODEL, "judge_seed": JUDGE_SEED,
        "n_queries": len(raw), "n_judged": len(verdicts), "n_kb_sets": len(kb),
        "median_latency_s": med_lat,
        "routing_exact_tolerant_pct": round(per_tier["ALL"]["tol"] / per_tier["ALL"]["n"] * 100),
        **cite_summary, **kb_summary,
    }
    (d / "manifest.json").write_text(json.dumps(manifest, indent=2))

    header = [f"# MedDataOS Technical Evaluation — `{tag}` run\n\n",
              f"- System under test: `{GEMINI_MODEL}`\n",
              f"- Judge: `{JUDGE_MODEL}` (seed {JUDGE_SEED})\n",
              f"- Date: {date}\n",
              f"- Queries: {len(raw)} | judged for citations: {len(verdicts)} | KB sets: {len(kb)}\n",
              f"- Median end-to-end latency: {med_lat}s\n\n"]
    (d / "REPORT.md").write_text("".join(header + rb + cb + kbb))
    print(f"Wrote {d/'manifest.json'} and {d/'REPORT.md'}")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
