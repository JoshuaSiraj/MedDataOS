"""
Stage 2: Citation faithfulness + coverage judge (OpenAI gpt-5.1, different family
from the Gemini system-under-test). Reads results/raw_queries_<tag>.jsonl.

For each query the judge segments the response into atomic clinical claims and labels:
  CITED claims (carry [cite:N]):  faithful | overstated | fabricated
      -- vs the union of the summaries of the findings they cite.
  UNCITED factual claims:         grounded | ungrounded | not_a_claim
      -- grounded if the fact is in ANY finding summary or the demographics.

Metrics:
  faithfulness = faithful / (faithful+overstated+fabricated)   [cited claims]
  overstatement_rate = overstated / total cited
  fabrication_rate   = fabricated / total cited
  hallucination_rate = ungrounded / (grounded+ungrounded)      [uncited factual claims]

Usage: PYTHONPATH=. python eval/judge_citations.py [pilot|full] [--limit N]
"""
import sys
import json
from collections import Counter

from openai import OpenAI
from eval.common import run_dir, read_jsonl, write_jsonl, load_patient_info

JUDGE_MODEL = "gpt-5.5-2026-04-23"  # pinned dated snapshot for reproducibility
JUDGE_SEED = 7  # best-effort reproducibility for the frozen run

SCHEMA = {
    "name": "claim_verdicts",
    "strict": True,
    "schema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object", "additionalProperties": False,
                    "properties": {
                        "claim_text": {"type": "string"},
                        "kind": {"type": "string", "enum": ["cited", "uncited"]},
                        "cited_ids": {"type": "array", "items": {"type": "string"}},
                        "verdict": {"type": "string", "enum": [
                            "faithful", "overstated", "fabricated",
                            "grounded", "ungrounded", "not_a_claim"]},
                        "rationale": {"type": "string"},
                    },
                    "required": ["claim_text", "kind", "cited_ids", "verdict", "rationale"],
                },
            }
        },
        "required": ["claims"],
    },
}

SYSTEM = """You are a careful clinical-evidence auditor. You are given an AI system's \
narrative answer about one patient, the source findings it may cite (each with an id), \
and the patient's demographics. The narrative uses [cite:N] markers to attribute claims \
to finding N.

Segment the narrative into atomic clinical claims (one asserted fact each). For each claim:

- If it carries one or more [cite:N] markers -> kind="cited", cited_ids=[those N]. Judge the \
claim ONLY against the union of the cited findings' summaries:
    faithful   = the claim's factual content is supported by the cited finding(s). This INCLUDES \
reasonable clinical synthesis and interpretation grounded in the data: causal linkage between \
correlated findings (e.g. "the ECG changes are corroborated by the echo"), standard clinical \
characterizations of the reported values (e.g. calling HbA1c 10.2% "severely uncontrolled" when \
the finding says "markedly elevated"), and restating a value with its finding-provided qualifier. \
Connecting findings the way a clinician would is EXPECTED and is faithful, not an error.
    overstated = the claim asserts a severity, certainty, or magnitude BEYOND what the finding \
states -- a genuine distortion a clinician would flag (e.g. finding says "mildly reduced EF 45%" \
but claim says "severely reduced"; finding says "borderline troponin" but claim says "clear \
myocardial infarction").
    fabricated = the claim asserts a specific fact that is absent from, or contradicted by, the \
cited finding(s).

- If it has NO citation and states a checkable clinical fact -> kind="uncited":
    grounded   = the fact appears in, or is directly entailed by, ANY provided finding summary \
or the demographics.
    ungrounded = a specific clinical assertion not backed by any finding or the demographics.

- If it is connective/framing text with no checkable fact -> kind="uncited", verdict="not_a_claim".

Ignore the literal [cite:N] tokens when quoting claim_text. Reward faithful synthesis; reserve \
overstated/fabricated for genuine distortions or unsupported assertions."""


def build_user(rec, demographics):
    cites = "\n".join(f"[{c['id']}] ({c['agent']}) {c['summary']}" for c in rec["citations"])
    return (f"DEMOGRAPHICS: {demographics}\n\n"
            f"SOURCE FINDINGS (citable):\n{cites}\n\n"
            f"NARRATIVE ANSWER:\n{rec['response']}")


def demographics_str(pid):
    info = load_patient_info(pid)
    return (f"name: {info.get('name', pid)}; {info.get('age')}{info.get('sex')}, conditions: "
            f"{', '.join(info.get('conditions', [])) or 'none'}; "
            f"allergies: {', '.join(info.get('allergies', [])) or 'none'}")


def judge_query(client, rec, retries=4):
    """Judge one query. Resilient to occasional empty/invalid completions:
    retries with escalating token budget; returns None if all attempts fail
    (caller records the failure rather than crashing the batch)."""
    msg = build_user(rec, demographics_str(rec["patient_id"]))
    toks = 8000
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}],
                response_format={"type": "json_schema", "json_schema": SCHEMA},
                max_completion_tokens=toks,
                seed=JUDGE_SEED,
            )
            content = resp.choices[0].message.content
            if content and content.strip():
                return json.loads(content)["claims"]
        except (json.JSONDecodeError, KeyError, Exception) as e:
            last = str(e)[:80]
        toks = min(toks * 2, 24000)
    print(f"      ! judge failed for {rec['id']} after {retries} attempts")
    return None


def summarize(all_claims):
    cited = Counter(c["verdict"] for c in all_claims if c["kind"] == "cited")
    uncited = Counter(c["verdict"] for c in all_claims if c["kind"] == "uncited")
    n_cited = sum(cited.values())
    faithful = cited["faithful"] / n_cited if n_cited else 0.0
    factual_uncited = uncited["grounded"] + uncited["ungrounded"]
    halluc = uncited["ungrounded"] / factual_uncited if factual_uncited else 0.0
    return cited, uncited, n_cited, faithful, factual_uncited, halluc


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    tag = args[0] if args else "pilot"
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    rows = read_jsonl(run_dir(tag) / "raw_queries.jsonl")
    rows = [r for r in rows if not r["no_tool"]]  # nothing to judge if no citations
    if limit:
        rows = rows[:limit]

    out = run_dir(tag) / "citation_verdicts.jsonl"
    # resume: for the pilot re-runs we overwrite; for a long full run, skip done ids
    done = {r["id"] for r in read_jsonl(out)} if (out.exists() and not limit and tag != "pilot") else set()
    if not done and out.exists() and (limit or tag == "pilot"):
        out.unlink()  # fresh start for pilot/limited re-runs
    todo = [r for r in rows if r["id"] not in done]
    print(f"{len(rows)} judgeable, {len(done)} done, running {len(todo)} ...")

    client = OpenAI()
    failed = []
    with open(out, "a") as fh:
        for i, rec in enumerate(todo, 1):
            claims = judge_query(client, rec)
            if claims is None:
                failed.append(rec["id"])
                continue
            fh.write(json.dumps({"id": rec["id"], "tier": rec["tier"], "claims": claims}, ensure_ascii=False) + "\n")
            fh.flush()
            c = Counter(x["verdict"] for x in claims)
            print(f"  [{i}/{len(todo)}] {rec['id']} {rec['tier']:11s} "
                  f"cited(F/O/Fab)={c['faithful']}/{c['overstated']}/{c['fabricated']} "
                  f"uncited(G/U/NA)={c['grounded']}/{c['ungrounded']}/{c['not_a_claim']}", flush=True)

    all_claims = [c for r in read_jsonl(out) for c in r["claims"]]
    cited, uncited, n_cited, faithful, factual_uncited, halluc = summarize(all_claims)
    print(f"\nCITATION RESULTS ({tag})")
    print(f"  cited claims: {n_cited}  ->  faithful {cited['faithful']}, "
          f"overstated {cited['overstated']}, fabricated {cited['fabricated']}")
    print(f"  faithfulness (faithful/total cited): {faithful*100:.0f}%")
    print(f"  overstatement rate: {cited['overstated']/n_cited*100:.0f}%   "
          f"fabrication rate: {cited['fabricated']/n_cited*100:.0f}%")
    print(f"  uncited factual claims: {factual_uncited}  ->  grounded {uncited['grounded']}, "
          f"ungrounded {uncited['ungrounded']}  (not-a-claim {uncited['not_a_claim']})")
    print(f"  hallucination rate (ungrounded/factual uncited): {halluc*100:.0f}%")
    if failed:
        print(f"  WARNING: {len(failed)} queries failed judging and were excluded: {failed}")


if __name__ == "__main__":
    main()
