"""
Compare two saved result files side-by-side to measure the impact of a
change - e.g. adding a system prompt, switching models, or adding RAG context.

Usage:
    # Compare two factual/math eval runs:
    python compare.py results/factual_qa_run1.json results/factual_qa_run2.json

    # Compare two red-team runs:
    python compare.py results/red_team_run1.json results/red_team_run2.json

NOTE: Both files must be the same type (both eval OR both red-team).
      Mixing an eval result with a red-team result won't work - they have
      different result structures.
"""

import json
import sys


def load(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def detect_type(data: dict) -> str:
    """Figure out if this is a standard eval result or a red-team result."""
    if data["results"] and "resisted" in data["results"][0]:
        return "red_team"
    return "eval"


def compare_eval(path_a: str, path_b: str, a: dict, b: dict):
    """Compare two standard eval (factual/math) result files."""
    a_by_id = {r["id"]: r for r in a["results"]}
    b_by_id = {r["id"]: r for r in b["results"]}
    all_ids = sorted(set(a_by_id) | set(b_by_id))

    regressions  = []
    improvements = []
    both_fail    = []

    print(f"\n{'ID':<12} {'A':<6} {'B':<6} {'Change'}")
    print("-" * 45)

    for qid in all_ids:
        ra = a_by_id.get(qid)
        rb = b_by_id.get(qid)
        pa = ra["passed"] if ra else None
        pb = rb["passed"] if rb else None

        if pa is None:
            change = "only in B"
        elif pb is None:
            change = "only in A"
        elif pa and pb:
            change = "—"
        elif not pa and not pb:
            change = "—"
            both_fail.append(qid)
        elif not pa and pb:
            change = "✓ IMPROVED"
            improvements.append(qid)
        else:
            change = "✗ REGRESSED"
            regressions.append(qid)

        a_str = ("✓" if pa else "✗") if pa is not None else "—"
        b_str = ("✓" if pb else "✗") if pb is not None else "—"
        print(f"{qid:<12} {a_str:<6} {b_str:<6} {change}")

    a_acc = a["correct"] / a["total"]
    b_acc = b["correct"] / b["total"]
    delta = b_acc - a_acc

    print(f"\n{'='*45}")
    print(f"A accuracy: {a_acc*100:.1f}%  ({a['correct']}/{a['total']})")
    print(f"B accuracy: {b_acc*100:.1f}%  ({b['correct']}/{b['total']})")
    print(f"Delta:      {'+' if delta >= 0 else ''}{delta*100:.1f}pp")

    if improvements:
        print(f"\nImproved in B ({len(improvements)}): {improvements}")
    if regressions:
        print(f"Regressed in B ({len(regressions)}): {regressions}")
    if both_fail:
        print(f"Still failing ({len(both_fail)}): {both_fail}")


def compare_red_team(path_a: str, path_b: str, a: dict, b: dict):
    """Compare two red-team result files."""
    a_by_id = {r["id"]: r for r in a["results"]}
    b_by_id = {r["id"]: r for r in b["results"]}
    all_ids = sorted(set(a_by_id) | set(b_by_id))

    newly_breached  = []
    newly_resisted  = []

    print(f"\n{'ID':<10} {'Category':<22} {'A':<12} {'B':<12} {'Change'}")
    print("-" * 65)

    for qid in all_ids:
        ra = a_by_id.get(qid)
        rb = b_by_id.get(qid)
        pa = ra["resisted"] if ra else None
        pb = rb["resisted"] if rb else None

        if pa is None:
            change = "only in B"
        elif pb is None:
            change = "only in A"
        elif not pa and pb:
            change = "✓ NOW RESISTED"
            newly_resisted.append(qid)
        elif pa and not pb:
            change = "✗ NOW BREACHED"
            newly_breached.append(qid)
        else:
            change = "—"

        a_str = ("✓" if pa else "✗") if pa is not None else "—"
        b_str = ("✓" if pb else "✗") if pb is not None else "—"
        cat   = (ra or rb).get("category", "")
        print(f"{qid:<10} {cat:<22} {a_str:<12} {b_str:<12} {change}")

    a_rate = a["resisted"] / a["total"]
    b_rate = b["resisted"] / b["total"]
    delta  = b_rate - a_rate

    print(f"\n{'='*65}")
    print(f"A resist rate: {a_rate*100:.1f}%  ({a['resisted']}/{a['total']})")
    print(f"B resist rate: {b_rate*100:.1f}%  ({b['resisted']}/{b['total']})")
    print(f"Delta:         {'+' if delta >= 0 else ''}{delta*100:.1f}pp")

    if newly_resisted:
        print(f"\nNow resisted in B ({len(newly_resisted)}): {newly_resisted}")
    if newly_breached:
        print(f"Now breached in B ({len(newly_breached)}): {newly_breached}")


def compare(path_a: str, path_b: str):
    a = load(path_a)
    b = load(path_b)

    type_a = detect_type(a)
    type_b = detect_type(b)

    print(f"\n{'='*65}")
    print(f"COMPARISON  [{type_a} vs {type_b}]")
    print(f"  A: {path_a}")
    print(f"     model={a['model']}  time={a['timestamp'][:19]}")
    print(f"  B: {path_b}")
    print(f"     model={b['model']}  time={b['timestamp'][:19]}")
    print(f"{'='*65}")

    if type_a != type_b:
        print(f"\nERROR: cannot compare an '{type_a}' result with a '{type_b}' result.")
        print("  Both files must come from the same type of run:")
        print("  - eval results: from running evaluator.py")
        print("  - red-team results: from running red_team.py")
        print("\nTip: to compare model performance across benchmarks, run evaluator.py")
        print("twice on the same .jsonl file (e.g. before/after changing the system prompt)")
        print("and compare those two eval result files.")
        return

    if type_a == "red_team":
        compare_red_team(path_a, path_b, a, b)
    else:
        compare_eval(path_a, path_b, a, b)

    print()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python compare.py results/run_a.json results/run_b.json")
        sys.exit(1)
    compare(sys.argv[1], sys.argv[2])
