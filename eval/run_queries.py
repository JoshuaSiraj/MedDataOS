"""
Stage 1a: Query runner. Runs each query through run_pipeline, captures the raw
output (response text, citations, invoked-agent set, latency), saves to
results/raw_queries_<tag>.jsonl. Re-runnable; judging/scoring read the saved
file so we never re-hit Gemini to re-score.

Usage: PYTHONPATH=. python eval/run_queries.py [pilot|full]
"""
import sys
import json
import time

from eval.common import DATA, run_dir, read_jsonl, write_jsonl, load_patient_info
from src.core.orchestrator import run_pipeline


def run_query(q):
    """Execute one query; return the raw record used by all downstream scorers."""
    info = load_patient_info(q["patient_id"], strip_modalities=q.get("modality_override"))
    t0 = time.time()
    # run_knowledge_bus fires async inside run_pipeline; harmless here (we score KB separately)
    out = run_pipeline(q["query"], patient_id=q["patient_id"], patient_info=info)
    latency = round(time.time() - t0, 2)

    try:
        obj = json.loads(out)
        response = obj.get("response", "")
        citations = obj.get("citations", [])
        no_tool = False
    except (json.JSONDecodeError, TypeError):
        response = str(out)
        citations = []
        no_tool = True

    # invoked agents in tool-call order (dedup preserving order for the set metric)
    invoked = [c.get("agent") for c in citations]
    invoked_set = sorted(set(invoked))

    return {
        "id": q["id"], "tier": q["tier"], "patient_id": q["patient_id"],
        "probe_type": q.get("probe_type"),
        "query": q["query"],
        "gold_agents": q["gold_agents"], "optional_agents": q.get("optional_agents", []),
        "invoked_agents": invoked, "invoked_set": invoked_set,
        "no_tool": no_tool, "latency_s": latency,
        "response": response,
        # keep only what the judge needs from citations: id, agent, summary
        "citations": [{"id": c.get("id"), "agent": c.get("agent"), "summary": c.get("summary", "")} for c in citations],
    }


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "pilot"
    src = DATA / (f"queries_{tag}.jsonl" if tag == "pilot" else "queries.jsonl")
    queries = read_jsonl(src)
    out = run_dir(tag) / "raw_queries.jsonl"

    # resume: skip ids already written (incremental append survives kills)
    done = {r["id"] for r in read_jsonl(out)} if out.exists() else set()
    todo = [q for q in queries if q["id"] not in done]
    print(f"{len(queries)} total, {len(done)} done, running {len(todo)} ...")

    with open(out, "a") as f:
        for i, q in enumerate(todo, 1):
            rec = run_query(q)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            flag = "OK" if set(rec["gold_agents"]).issubset(set(rec["invoked_set"])) else "CHECK"
            print(f"  [{i}/{len(todo)}] {rec['id']} {rec['tier']:11s} "
                  f"gold={rec['gold_agents']} invoked={rec['invoked_set']} "
                  f"[{rec['latency_s']}s] {flag}", flush=True)
    total = len(read_jsonl(out))
    print(f"\n{out} now has {total}/{len(queries)} records")


if __name__ == "__main__":
    main()
