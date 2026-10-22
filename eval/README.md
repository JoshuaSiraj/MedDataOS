# MedDataOS Technical Evaluation

Offline benchmark validating the three architecture-level properties the system
rests on: **routing** (right agents invoked), **citation faithfulness + coverage**
(claims trace to their data), and **cross-modal conflict detection** (the Knowledge
Bus flags real contradictions and leaves consistent patients alone). It does **not**
measure per-modality accuracy — that is not the system's claim.

All ground truth is derived from the 10 synthetic patients (`stubs/`,
`multimodal-data/`). System under test: Gemini (orchestrator + Knowledge Bus).
Judge: an OpenAI model from a different family, to avoid same-model bias.

## Layout

```
data/                     frozen benchmark inputs
  fact_inventory.json     atomic clinical facts per patient x modality (query source)
  queries.jsonl           100 queries: 30 simple + 10 probes + 30 cross-modal + 30 multi-hop
  kb_sets.jsonl           40 Knowledge Bus sets: 10 clean + 30 seeded contradictions
  REVIEW.md               human-readable gold-label review sheet
  build_*.py              generators for the above (rerun to regenerate)
results/<run>/            one self-contained folder per run
  raw_queries.jsonl       every query's response + citations + invoked agents + latency
  citation_verdicts.jsonl per-claim judge verdicts with rationales
  kb_verdicts.jsonl       per-set contradiction pairs across reps
  manifest.json           models, seed, date, counts, headline metrics (reproducibility)
  REPORT.md               human-readable summary + failure cases
```

## Running

```bash
# from repo root, with GEMINI_API_KEY and OPENAI_API_KEY in .env
PYTHONPATH=. python eval/run_queries.py full     # run queries (resumable)
PYTHONPATH=. python eval/score_routing.py full    # routing metrics (no API)
PYTHONPATH=. python eval/judge_citations.py full  # citation judge (resumable)
PYTHONPATH=. python eval/score_kb.py full --reps 3 # Knowledge Bus (resumable)
PYTHONPATH=. python eval/report.py full --date YYYY-MM-DD  # manifest + REPORT
```

Runners are resumable: each result is appended as it completes, so re-invoking
skips finished items. Scoring reads the saved files and never re-hits the APIs.

## Run 1 (frozen) headline

Routing F1 0.92 (recall 0.96) · citation faithfulness 92% · Knowledge Bus seeded
recall 93%, clean false-positive rate 0%. See `results/full/REPORT.md` for detail
and failure analysis. Judge–human validation of a claim subset is pending.
