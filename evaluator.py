"""
Runs a benchmark JSONL file against the model and scores every answer.

Scoring is intentionally simple:
  - Exact match (case-insensitive, stripped)
  - Contains match - expected string appears anywhere in the response

This is the right starting point because the most common eval failure in
real systems is overcomplicated scoring that hides simple regressions.
You can always add an LLM-as-judge scorer on top once the basics work.

Run:
    python evaluator.py evals/factual_qa.jsonl
    python evaluator.py evals/math_reasoning.jsonl
"""

import json
import os
import sys
import datetime
import argparse
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "agent_config",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_config.py")
)
_cfg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cfg)

import ollama_client


SYSTEM_PROMPT = (
    "You are a precise question-answering assistant. "
    "Answer the question as concisely as possible. "
    "If the answer is a number, give only the number. "
    "If the answer is a name or short phrase, give only that."
)


def score_answer(model_answer: str, expected: str) -> tuple:
    """Returns (passed: bool, method: str)"""
    model_clean    = model_answer.strip().lower()
    expected_clean = expected.strip().lower()

    if model_clean == expected_clean:
        return True, "exact_match"
    if expected_clean in model_clean:
        return True, "contains_match"
    return False, "no_match"


def run_eval(jsonl_path: str) -> dict:
    with open(jsonl_path) as f:
        cases = [json.loads(line) for line in f if line.strip()]

    results = []
    categories = {}

    print(f"\nRunning {len(cases)} cases from {jsonl_path}\n")
    print(f"{'ID':<12} {'Expected':<20} {'Passed':<8} {'Method':<16} {'Model Answer'}")
    print("-" * 85)

    for case in cases:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": case["question"]},
        ]
        model_answer = ollama_client.chat(messages)
        passed, method = score_answer(model_answer, case["expected"])

        cat = case.get("category", "uncategorized")
        categories.setdefault(cat, {"passed": 0, "total": 0})
        categories[cat]["total"] += 1
        if passed:
            categories[cat]["passed"] += 1

        answer_preview = model_answer.replace("\n", " ")[:40]
        status = "✓" if passed else "✗"
        print(f"{case['id']:<12} {case['expected']:<20} {status + ' ' + str(passed):<8} {method:<16} {answer_preview}")

        results.append({
            "id":           case["id"],
            "question":     case["question"],
            "expected":     case["expected"],
            "model_answer": model_answer,
            "passed":       passed,
            "method":       method,
            "category":     cat,
        })

    total   = len(results)
    correct = sum(r["passed"] for r in results)

    print(f"\n{'='*85}")
    print(f"OVERALL: {correct}/{total} ({100*correct/total:.1f}%)")
    print(f"\nBy category:")
    for cat, stats in sorted(categories.items()):
        pct = 100 * stats["passed"] / stats["total"]
        print(f"  {cat:<20} {stats['passed']}/{stats['total']} ({pct:.0f}%)")

    return {
        "eval_file":  jsonl_path,
        "model":      ollama_client.GENERATION_MODEL,
        "timestamp":  datetime.datetime.now().isoformat(),
        "total":      total,
        "correct":    correct,
        "accuracy":   correct / total,
        "by_category": categories,
        "results":    results,
    }


def save_results(summary: dict, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(summary["eval_file"]))[0]
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"{base}_{ts}.json")
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nResults saved to {path}")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("eval_file", help="Path to a .jsonl benchmark file")
    args = parser.parse_args()

    if not ollama_client.check_connection():
        print("Cannot reach Ollama - check agent_config.py")
        sys.exit(1)

    summary = run_eval(args.eval_file)
    save_results(summary, _cfg.RESULTS_DIR)


if __name__ == "__main__":
    main()
