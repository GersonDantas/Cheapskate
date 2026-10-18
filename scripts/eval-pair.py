#!/usr/bin/env python3
"""Evaluate two instruction bundles, retaining measured usage and partial failures."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
SHARED = ("conversation", "code", "rtk", "codegraph", "graphify", "caveman")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def number(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def sum_field(items, name):
    values = [number(item.get(name)) for item in items]
    return sum(values) if values and all(value is not None for value in values) else None


def parse_usage(host, data):
    if host == "codex":
        events = [json.loads(line) for line in data.splitlines() if line.strip()]
        if any(not isinstance(event, dict) for event in events):
            raise ValueError("Invalid event shape")
        turns, seen = [], set()
        for event in events:
            if event.get("type") != "turn.completed":
                continue
            identity = event.get("turn_id") or event.get("id")
            if identity and identity in seen:
                continue
            if identity:
                seen.add(identity)
            usage = event.get("usage") or {}
            if not isinstance(usage, dict):
                raise ValueError("Invalid usage shape")
            turns.append(usage)
        raw = turns
        input_tokens = sum_field(turns, "input_tokens")
        cached = sum_field(turns, "cached_input_tokens")
        output = sum_field(turns, "output_tokens")
        if input_tokens is not None and cached is not None and cached > input_tokens:
            raise ValueError("Cached input exceeds input tokens")
        uncached = input_tokens - cached if input_tokens is not None and cached is not None else None
        models = sorted({event["model"] for event in events
                         if event.get("type") in ("thread.started", "turn.started", "session.configured")
                         and isinstance(event.get("model"), str)})
        tool_count = 0
        text_scope = True
        tool_items = {"command_execution", "mcp_tool_call", "web_search", "file_change", "tool_call", "function_call", "todo_list"}
        text_items = {"agent_message", "reasoning"}
        known_events = {"thread.started", "turn.started", "turn.completed", "turn.failed", "error",
                        "session.configured", "item.started", "item.updated", "item.completed"}
        seen_tools = set()
        for event in events:
            if event.get("type") not in known_events:
                text_scope = False
            if event.get("type") not in ("item.started", "item.updated", "item.completed"):
                continue
            item = event.get("item")
            if not isinstance(item, dict):
                text_scope = False
                continue
            kind = item.get("type")
            if kind in tool_items:
                identity = item.get("id")
                if not identity or identity not in seen_tools:
                    tool_count += 1
                if identity:
                    seen_tools.add(identity)
            elif kind not in text_items:
                text_scope = False
        failed = any(event.get("type") in ("error", "turn.failed") for event in events)
        cache_write = None
        total_input = input_tokens
        model_usage = None
    else:
        event = json.loads(data)
        if not isinstance(event, dict):
            raise ValueError("Invalid result shape")
        raw = event.get("usage") or {}
        if not isinstance(raw, dict):
            raise ValueError("Invalid usage shape")
        model_usage = event.get("modelUsage") or {}
        input_tokens = number(raw.get("input_tokens"))
        cached = number(raw.get("cache_read_input_tokens"))
        cache_write = number(raw.get("cache_creation_input_tokens"))
        output = number(raw.get("output_tokens"))
        uncached = input_tokens
        components = (input_tokens, cached, cache_write)
        total_input = sum(components) if all(value is not None for value in components) else None
        models = sorted(model_usage) if isinstance(model_usage, dict) else []
        tool_count = None  # Safe-mode evaluation disables built-in tools explicitly.
        text_scope = True
        failed = event.get("is_error") is True
    total = total_input + output if total_input is not None and output is not None else None
    return {"native_usage": raw, "native_model_usage": model_usage,
            "observed_models": models, "tool_calls_observed": tool_count,
            "text_scope_confirmed": text_scope,
            "client_reported_failure": failed,
            "usage": {"input_reported": input_tokens, "input_uncached": uncached,
                      "cache_read": cached, "cache_write": cache_write,
                      "input_total": total_input, "output": output, "total": total,
                      "reasoning": None}}


def build_shared(directory):
    required = (directory / "conversation-guidelines.md", directory / "code-guidelines.md")
    if not all(path.is_file() for path in required):
        raise ValueError("Missing required shared instruction sources")
    return b"\n\n".join((directory / f"{name}-guidelines.md").read_bytes()
                        for name in SHARED if (directory / f"{name}-guidelines.md").is_file())


def client_version(host):
    try:
        result = subprocess.run([host, "--version"], capture_output=True, text=True,
                                timeout=15, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def run_process(command, env, cwd, stdout, stderr, timeout):
    with stdout.open("w") as out, stderr.open("w") as err:
        process = subprocess.Popen(command, env=env, cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=out, stderr=err, start_new_session=True)
        try:
            return process.wait(timeout=timeout), False
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=2)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                pass
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            return process.returncode, True


def evaluate(host, label, instructions, prompt, output_dir, temporary, model, effort, timeout, version, auth_unavailable=False):
    output_dir.mkdir(parents=True, exist_ok=True)
    raw = output_dir / f"{host}-{label}.{'jsonl' if host == 'codex' else 'json'}"
    stderr = output_dir / f"{host}-{label}.stderr.txt"
    answer = output_dir / f"{host}-{label}.md"
    project = temporary / label / "project"
    project.mkdir(parents=True)
    env = os.environ.copy()
    metrics = {"schema": 1, "host": host, "arm": label, "scope": "text-instructions",
               "client_version": version, "model_requested": model, "effort_requested": effort,
               "instruction_sha256": digest(instructions), "instruction_bytes": len(instructions),
               "prompt_sha256": digest(prompt.encode()), "quality_review": "pending",
               "status": "not_started", "observed_models": [], "usage": None,
               "client_inference_attempted": False}
    started = time.monotonic()
    try:
        if auth_unavailable:
            raise ValueError("Client authentication unavailable")
        if host == "codex":
            home = temporary / label / "codex-home"
            home.mkdir()
            auth = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
            if not auth.is_file():
                raise ValueError("Codex authentication file unavailable")
            (home / "auth.json").write_bytes(auth.read_bytes())
            (home / "AGENTS.md").write_bytes(instructions)
            env["CODEX_HOME"] = str(home)
            command = ["codex", "exec", "--ephemeral", "--ignore-user-config",
                       "--skip-git-repo-check", "--sandbox", "read-only", "--model", model,
                       "--config", f'model_reasoning_effort="{effort}"', "--cd", str(project),
                       "--json", "--output-last-message", str(answer), prompt]
        else:
            command = ["claude", "-p", "--safe-mode", "--tools", "", "--model", model,
                       "--effort", effort, "--no-session-persistence", "--output-format", "json",
                       "--system-prompt", instructions.decode(), prompt]
        metrics["client_inference_attempted"] = True
        returncode, timed_out = run_process(command, env, project, raw, stderr, timeout)
        metrics["exit_code"] = returncode
        metrics["status"] = "timeout" if timed_out else "failed" if returncode else "completed"
        try:
            parsed = parse_usage(host, raw.read_text())
            metrics.update(parsed)
            if metrics["status"] == "completed" and parsed["client_reported_failure"]:
                metrics["status"] = "failed"
            if host == "claude":
                result = json.loads(raw.read_text())
                if isinstance(result.get("result"), str):
                    answer.write_text(result["result"])
                metrics["cli_cost_usd"] = result.get("total_cost_usd")
        except (ValueError, TypeError):
            if metrics["status"] == "completed":
                metrics["status"] = "invalid_output"
        if answer.exists():
            metrics["answer_bytes"] = answer.stat().st_size
            metrics["answer_sha256"] = digest(answer.read_bytes())
        else:
            if metrics["status"] == "completed":
                metrics["status"] = "missing_answer"
        failure_text = (stderr.read_text() if stderr.exists() else "") + (raw.read_text() if raw.exists() else "")
        if metrics["status"] != "completed" and any(word in failure_text.lower() for word in ("oauth", "not logged in", "authentication", "unauthorized")):
            metrics["failure_category"] = "authentication"
    except (OSError, ValueError) as error:
        metrics["status"] = "unavailable"
        metrics["failure_category"] = "authentication" if "authentication" in str(error) else "client_setup"
    finally:
        metrics["duration_seconds"] = round(time.monotonic() - started, 3)
        (output_dir / f"{host}-{label}-metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    return metrics


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", choices=("codex", "claude"))
    parser.add_argument("prompt")
    args = parser.parse_args()
    timeout = float(os.environ.get("EVAL_TIMEOUT_SECONDS", "120"))
    if timeout <= 0:
        raise ValueError("Timeout must be positive")
    order = os.environ.get("EVAL_ORDER", "before-first")
    if order not in ("before-first", "after-first"):
        raise ValueError("Invalid EVAL_ORDER")
    if args.host == "codex":
        bundles = {"before": Path(os.environ.get("BASELINE_AGENTS", str(ROOT / "evals/baseline/codex/AGENTS.md"))).read_bytes(),
                   "after": Path(os.environ.get("CANDIDATE_AGENTS", str(ROOT / "codex/AGENTS.md"))).read_bytes()}
        model = os.environ.get("CODEX_EVAL_MODEL", "gpt-6-sol")
        effort = os.environ.get("CODEX_EVAL_EFFORT", "medium")
    else:
        bundles = {"before": build_shared(Path(os.environ.get("BASELINE_SHARED", str(ROOT / "evals/baseline/shared")))),
                   "after": build_shared(Path(os.environ.get("CANDIDATE_SHARED", str(ROOT / "shared"))))}
        model = os.environ.get("CLAUDE_EVAL_MODEL", "sonnet")
        effort = os.environ.get("CLAUDE_EVAL_EFFORT", "medium")
    version = client_version(args.host)
    auth_unavailable = False
    if args.host == "claude":
        try:
            status = subprocess.run(["claude", "auth", "status", "--json"], capture_output=True,
                                    text=True, timeout=15, check=False)
            auth_unavailable = json.loads(status.stdout).get("loggedIn") is False
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    with tempfile.TemporaryDirectory(prefix="cheapskate-eval-") as temporary:
        root = Path(temporary).resolve()
        output = Path(os.environ["EVAL_OUTPUT_DIR"]).absolute() if os.environ.get("EVAL_OUTPUT_DIR") else root / "artifacts"
        sequence = ("before", "after") if order == "before-first" else ("after", "before")
        results = []
        for label in sequence:
            result = evaluate(args.host, label, bundles[label], args.prompt, output, root,
                              model, effort, timeout, version, auth_unavailable)
            results.append(result)
            if result.get("failure_category") == "authentication":
                auth_unavailable = True
        for result in results:
            print(json.dumps({key: result.get(key) for key in
                              ("arm", "status", "observed_models", "usage", "duration_seconds")}))
        if not os.environ.get("EVAL_OUTPUT_DIR"):
            answers = {}
            for label in ("before", "after"):
                path = output / f"{args.host}-{label}.md"
                answers[label] = path.read_text() if path.is_file() else ""
                print(f"\n--- {label} answer ---\n{answers[label]}")
            print("\n--- answer diff ---")
            print("".join(difflib.unified_diff(
                answers["before"].splitlines(keepends=True),
                answers["after"].splitlines(keepends=True),
                fromfile="before", tofile="after")))
        return 0 if all(result["status"] == "completed" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
