#!/usr/bin/env python3
"""Run selected baseline/candidate cases with explicit real-prompt approval."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from evaluation_report import generate


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "synthetic": ROOT / "evals/synthetic.jsonl",
    "real": ROOT / "evals/local/real-prompt-preview.jsonl",
}
EVALUATORS = {
    "codex": ROOT / "scripts/eval-instructions.sh",
    "claude": ROOT / "scripts/eval-claude-instructions.sh",
}


def load_cases(source: bytes):
    cases = [json.loads(line) for line in source.decode("utf-8").splitlines() if line.strip()]
    ids = set()
    for case in cases:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", case.get("id", "")) or case["id"] in ids:
            raise SystemExit("Invalid or duplicate case ID")
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            raise SystemExit("Case prompt must be a nonempty string")
        ids.add(case["id"])
    return cases


def main() -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=SOURCES, default="synthetic")
    parser.add_argument("--hosts", default="codex,claude")
    parser.add_argument("--ids", help="comma-separated case IDs")
    parser.add_argument("--repeat", type=int, choices=(1, 3), default=1)
    parser.add_argument(
        "--order",
        choices=("alternate", "before-first", "after-first"),
        default="alternate",
    )
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--approve-sha")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "evals/local/runs")
    parser.add_argument("--max-calls", type=int, default=8, help="Maximum planned client inference executions; internal retries may exceed it")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout per client arm in seconds")
    args = parser.parse_args()

    source_path = SOURCES[args.source]
    if not source_path.exists():
        raise SystemExit(f"Missing case file: {source_path}")
    source = source_path.read_bytes()
    source_sha = hashlib.sha256(source).hexdigest()
    cases = load_cases(source)
    requested_ids = set(filter(None, (args.ids or "").split(",")))
    if requested_ids:
        cases = [case for case in cases if case["id"] in requested_ids]
        missing = requested_ids - {case["id"] for case in cases}
        if missing:
            raise SystemExit("Unknown case IDs: " + ", ".join(sorted(missing)))
    hosts = list(dict.fromkeys(filter(None, args.hosts.split(","))))
    unknown_hosts = set(hosts) - EVALUATORS.keys()
    if unknown_hosts:
        raise SystemExit("Unknown hosts: " + ", ".join(sorted(unknown_hosts)))
    if not cases or not hosts:
        raise SystemExit("Select at least one case and one host.")
    calls = len(cases) * len(hosts) * args.repeat * 2
    if args.max_calls <= 0 or args.timeout <= 0:
        raise SystemExit("Call cap and timeout must be positive")

    print(
        json.dumps(
            {
                "mode": "run" if args.run else "dry-run",
                "source": args.source,
                "source_sha256": source_sha,
                "cases": [
                    {"id": case["id"], "critical": case.get("critical")}
                    for case in cases
                ],
                "hosts": hosts,
                "repeat": args.repeat,
                "order": args.order,
                "planned_client_executions": calls,
                "provider_calls": "client-controlled" if args.run else 0,
                "max_client_executions": args.max_calls,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not args.run:
        return 0
    if calls > args.max_calls:
        raise SystemExit(f"Plan requires {calls} client executions, exceeds cap {args.max_calls}")
    if args.source == "real" and args.approve_sha != source_sha:
        raise SystemExit("Real prompts require --approve-sha matching the reviewed preview.")

    run_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_root = args.output_dir / run_name
    run_root.mkdir(parents=True, exist_ok=False)
    (run_root / "source-sha256.txt").write_text(source_sha + "\n", encoding="utf-8")
    source_hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in [ROOT / "scripts/eval-pair.py", ROOT / "scripts/evaluation_report.py",
                                  ROOT / "scripts/eval-suite.py", ROOT / "dependencies.json"] if path.exists()}
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=False)
    (run_root / "run.json").write_text(json.dumps({"schema": 1, "source_sha256": source_sha,
        "source_hashes": source_hashes, "client_executions_planned": calls,
        "source_revision": revision.stdout.strip() if revision.returncode == 0 else None,
        "source_dirty": bool(dirty.stdout) if dirty.returncode == 0 else None,
        "scope": "text-instructions", "runner_retries": 0}, indent=2) + "\n")
    host_pair_counts = {host: 0 for host in hosts}
    failures = 0
    for case in cases:
        for repetition in range(1, args.repeat + 1):
            for host in hosts:
                case_dir = run_root / case["id"] / f"run-{repetition}" / host
                case_dir.mkdir(parents=True)
                env = os.environ.copy()
                env["EVAL_OUTPUT_DIR"] = str(case_dir)
                order = args.order
                if order == "alternate":
                    order = "before-first" if host_pair_counts[host] % 2 == 0 else "after-first"
                host_pair_counts[host] += 1
                env["EVAL_ORDER"] = order
                env["EVAL_TIMEOUT_SECONDS"] = str(args.timeout)
                started_at = datetime.now(timezone.utc).isoformat()
                started = time.monotonic()
                status = "completed"
                try:
                    with (case_dir / "evaluator.log").open("w", encoding="utf-8") as log:
                        subprocess.run(
                            ["sh", str(EVALUATORS[host]), case["prompt"]],
                            env=env,
                            stdout=log,
                            stderr=subprocess.STDOUT,
                            check=True,
                        )
                except subprocess.CalledProcessError:
                    status = "failed"
                    failures += 1
                finally:
                    (case_dir / "pair-run.json").write_text(
                        json.dumps(
                            {
                                "case": case["id"],
                                "host": host,
                                "repetition": repetition,
                                "order": order,
                                "status": status,
                                "started_at": started_at,
                                "duration_seconds": round(time.monotonic() - started, 3),
                            },
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
    print(f"Artifacts: {run_root}")
    generate(run_root)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
