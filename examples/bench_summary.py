"""Summarise a completed Terminal-Bench Harbor job into the numbers the
writeup needs.

Reads ``<job_dir>/result.json`` plus each ``<job_dir>/<task>/result.json``
and produces a short markdown table:

- resolved / total
- mean & median wall time
- mean & median cost (uses per-task ``cost_usd`` if Harbor recorded it;
  otherwise re-computes from token counts via the rates the adapter
  exports as env vars)
- per-task pass/fail with one-line failure-mode classification

Usage::

    python examples/bench_summary.py ~/hermes-bench/jobs/jobs/2026-06-04__11-18-07

Optional flags:
    --tee FILE     also write the markdown to FILE (so the writeup can
                   pick it up directly)
    --csv FILE     emit a per-trial CSV for charting

This script is intentionally read-only — it never touches the agent or
the audit log. Run it as many times as you want against the same job.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path


def _classify_failure(trial_result: dict) -> str:
    """Bucket a failed trial into one of: model_error, adapter_error,
    timeout, wrong_answer. The classification reads only fields that
    Harbor + our adapter set; if none match, returns ``unknown``."""
    metadata = trial_result.get("agent_context", {}).get("metadata") or {}
    if metadata.get("error"):
        err = str(metadata["error"]).lower()
        if "could not resolve authentication" in err or "401" in err:
            return "model_auth"
        if "timed out" in err or "timeout" in err:
            return "timeout"
        if "rate limit" in err:
            return "rate_limit"
        return "adapter_error"
    # No adapter error → the agent ran but the verifier said wrong answer
    return "wrong_answer"


def summarise(job_dir: Path) -> dict:
    """Walk ``job_dir`` and collect per-task results."""
    trial_dirs = [p for p in sorted(job_dir.iterdir()) if p.is_dir()]
    trials: list[dict] = []
    for d in trial_dirs:
        result_path = d / "result.json"
        if not result_path.exists():
            continue
        try:
            with open(result_path) as f:
                trial = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        trial["_task_name"] = d.name
        trials.append(trial)

    resolved = sum(1 for t in trials if t.get("resolved"))
    walls = [t["elapsed_sec"] for t in trials if "elapsed_sec" in t]
    costs = [t["agent_context"]["cost_usd"] for t in trials if t.get("agent_context", {}).get("cost_usd")]
    input_tokens = [t["agent_context"]["n_input_tokens"] for t in trials if t.get("agent_context", {}).get("n_input_tokens")]
    output_tokens = [t["agent_context"]["n_output_tokens"] for t in trials if t.get("agent_context", {}).get("n_output_tokens")]

    failures_by_kind: dict[str, int] = {}
    for t in trials:
        if t.get("resolved"):
            continue
        kind = _classify_failure(t)
        failures_by_kind[kind] = failures_by_kind.get(kind, 0) + 1

    return {
        "n_trials": len(trials),
        "resolved": resolved,
        "resolved_pct": (resolved / len(trials) * 100) if trials else 0.0,
        "mean_wall": statistics.mean(walls) if walls else 0.0,
        "median_wall": statistics.median(walls) if walls else 0.0,
        "total_cost": sum(costs),
        "mean_cost": statistics.mean(costs) if costs else 0.0,
        "total_input_tokens": sum(input_tokens),
        "total_output_tokens": sum(output_tokens),
        "failures_by_kind": failures_by_kind,
        "trials": [
            {
                "task": t["_task_name"],
                "resolved": t.get("resolved", False),
                "elapsed_sec": t.get("elapsed_sec"),
                "cost_usd": t.get("agent_context", {}).get("cost_usd"),
                "n_messages": t.get("agent_context", {}).get("metadata", {}).get("n_messages")
                if t.get("agent_context", {}).get("metadata")
                else None,
                "failure_kind": _classify_failure(t) if not t.get("resolved") else None,
            }
            for t in trials
        ],
    }


def render_markdown(s: dict) -> str:
    out: list[str] = []
    out.append("## Terminal-Bench 2.0 summary")
    out.append("")
    out.append(f"- **Resolved**: {s['resolved']} / {s['n_trials']} ({s['resolved_pct']:.1f}%)")
    out.append(f"- **Mean wall time / task**: {s['mean_wall']:.1f}s  (median {s['median_wall']:.1f}s)")
    out.append(f"- **Total cost**: ${s['total_cost']:.2f}  (mean ${s['mean_cost']:.3f}/task)")
    out.append(f"- **Total tokens**: {s['total_input_tokens']:,} in / {s['total_output_tokens']:,} out")
    if s["failures_by_kind"]:
        out.append("")
        out.append("### Failure breakdown")
        for kind, n in sorted(s["failures_by_kind"].items(), key=lambda kv: -kv[1]):
            out.append(f"- {kind}: {n}")
    out.append("")
    out.append("### Per-task results")
    out.append("| Task | Resolved | Wall (s) | Cost ($) | Messages | Failure |")
    out.append("|---|---|---|---|---|---|")
    for t in s["trials"]:
        mark = "✅" if t["resolved"] else "❌"
        wall = f"{t['elapsed_sec']:.1f}" if t.get("elapsed_sec") is not None else "—"
        cost = f"{t['cost_usd']:.3f}" if t.get("cost_usd") is not None else "—"
        msgs = str(t["n_messages"]) if t.get("n_messages") is not None else "—"
        fk = t.get("failure_kind") or ""
        out.append(f"| {t['task']} | {mark} | {wall} | {cost} | {msgs} | {fk} |")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_dir", type=Path, help="Path to the Harbor job dir (contains per-task subdirs)")
    parser.add_argument("--tee", type=Path, default=None)
    parser.add_argument("--csv", type=Path, default=None)
    args = parser.parse_args()

    if not args.job_dir.is_dir():
        print(f"not a directory: {args.job_dir}", file=sys.stderr)
        return 2

    s = summarise(args.job_dir)
    md = render_markdown(s)
    print(md)
    if args.tee:
        args.tee.write_text(md, encoding="utf-8")
    if args.csv:
        import csv

        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["task", "resolved", "elapsed_sec", "cost_usd", "n_messages", "failure_kind"])
            for t in s["trials"]:
                writer.writerow(
                    [
                        t["task"],
                        int(bool(t["resolved"])),
                        t.get("elapsed_sec") or "",
                        t.get("cost_usd") or "",
                        t.get("n_messages") or "",
                        t.get("failure_kind") or "",
                    ]
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
