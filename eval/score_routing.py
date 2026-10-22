"""
Stage 1b: Routing scorer (pure code, no API). Reads results/raw_queries_<tag>.jsonl.

Scoring model (optional_agents are NEUTRAL -- neither rewarded nor penalized):
  required = set(gold_agents); optional = set(optional_agents); invoked = set fired
  TP = invoked & required        (required agents correctly called)
  FN = required - invoked        (required agents missed)
  FP = invoked - required - optional   (agents called that were neither required nor allowed)
  micro precision/recall/F1 aggregate TP/FP/FN across queries.

Exact-set accuracy (tolerant): PASS iff required is a subset of invoked AND invoked
is a subset of (required or optional) -- all required present, no disallowed extras.
Also reports strict exact (invoked == required) for reference.

Usage: PYTHONPATH=. python eval/score_routing.py [pilot|full]
"""
import sys
from collections import defaultdict
from eval.common import run_dir, read_jsonl


def score(rows):
    per_tier = defaultdict(lambda: {"n": 0, "tp": 0, "fp": 0, "fn": 0, "tol": 0, "strict": 0})
    fails = []
    for r in rows:
        req, opt, inv = set(r["gold_agents"]), set(r["optional_agents"]), set(r["invoked_set"])
        tp = len(inv & req); fn = len(req - inv); fp = len(inv - req - opt)
        tol = req.issubset(inv) and inv.issubset(req | opt)
        strict = inv == req
        for key in (r["tier"], "ALL"):
            t = per_tier[key]
            t["n"] += 1; t["tp"] += tp; t["fp"] += fp; t["fn"] += fn
            t["tol"] += int(tol); t["strict"] += int(strict)
        if not tol:
            fails.append((r["id"], r["tier"], sorted(req), sorted(inv),
                          sorted(req - inv), sorted(inv - req - opt)))
    return per_tier, fails


def prf(t):
    p = t["tp"] / (t["tp"] + t["fp"]) if (t["tp"] + t["fp"]) else 1.0
    r = t["tp"] / (t["tp"] + t["fn"]) if (t["tp"] + t["fn"]) else 1.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "pilot"
    rows = read_jsonl(run_dir(tag) / "raw_queries.jsonl")
    per_tier, fails = score(rows)

    order = ["simple", "cross_modal", "multi_hop", "ALL"]
    print(f"\nROUTING RESULTS ({tag}, n={per_tier['ALL']['n']})\n")
    print(f"{'tier':12s} {'n':>3} {'exact(tol)':>11} {'exact(strict)':>13} {'prec':>6} {'rec':>6} {'F1':>6}")
    for k in order:
        if k not in per_tier:
            continue
        t = per_tier[k]
        p, r, f = prf(t)
        print(f"{k:12s} {t['n']:>3} {t['tol']/t['n']*100:>9.0f}% {t['strict']/t['n']*100:>12.0f}% "
              f"{p:>6.2f} {r:>6.2f} {f:>6.2f}")

    if fails:
        print("\nFailures (exact-tolerant misses):")
        for fid, tier, req, inv, missed, extra in fails:
            detail = []
            if missed: detail.append(f"MISSED required {missed}")
            if extra: detail.append(f"EXTRA disallowed {extra}")
            print(f"  {fid} ({tier}): {'; '.join(detail)}")
            print(f"      required={req}  invoked={inv}")


if __name__ == "__main__":
    main()
