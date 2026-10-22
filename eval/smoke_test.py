"""
Smoke test: run 2 pilot queries through run_pipeline headless, inspect the raw
output shape. De-risks the whole harness before we build parsers/scorers on
assumptions. Confirms: (a) the model id works, (b) run_pipeline is callable
offline, (c) what the response envelope actually looks like.
"""
import json
import time
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))

from src.core.orchestrator import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
PINFO = ROOT / "multimodal-data" / "patient-info"


def patient_info(pid):
    return json.loads((PINFO / f"{pid}.json").read_text())


def run_one(label, pid, query):
    print("\n" + "=" * 70)
    print(f"{label}: {pid} :: {query}")
    print("=" * 70)
    t0 = time.time()
    out = run_pipeline(query, patient_id=pid, patient_info=patient_info(pid))
    dt = time.time() - t0
    print(f"[latency {dt:.1f}s] return type: {type(out).__name__}")
    # Is it the JSON citation envelope, or plain text?
    try:
        obj = json.loads(out)
        print("PARSED AS JSON. keys:", list(obj.keys()))
        print("response text:\n", obj.get("response", "")[:800])
        cites = obj.get("citations", [])
        print(f"\n#citations: {len(cites)}  agents: {[c.get('agent') for c in cites]}")
        if cites:
            print("first citation object keys:", list(cites[0].keys()))
            print("first citation:", json.dumps(cites[0], ensure_ascii=False)[:400])
    except (json.JSONDecodeError, TypeError):
        print("PLAIN TEXT (no tools called):\n", str(out)[:800])


if __name__ == "__main__":
    # Q01 simple (expect echo only), Q05 cross-modal (expect ecg+echo+notes, multi-citation)
    run_one("Q01 simple", "P0009", "What is this patient's aortic valve area and mean gradient?")
    run_one("Q05 cross-modal", "P0001", "Is there any evidence of myocardial ischemia in this patient?")
    print("\nSmoke test done.")
