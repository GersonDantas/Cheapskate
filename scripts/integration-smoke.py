#!/usr/bin/env python3
"""Validate real RTK mappings and CodeGraph MCP without model calls or indexes."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rtk_hook", ROOT / "hooks/rtk.py")
HOOK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOOK)


def mcp_smoke(project, env):
    process = subprocess.Popen(["codegraph", "serve", "--mcp", "--no-watch", "--path", str(project)],
                               cwd=project, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05", "capabilities": {},
        "clientInfo": {"name": "cheapskate-smoke", "version": "1"}}}
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    initialized = False
    deadline = time.monotonic() + 15
    pending = b""
    try:
        while time.monotonic() < deadline:
            if selector.select(timeout=min(0.5, max(0, deadline - time.monotonic()))):
                chunk = os.read(process.stdout.fileno(), 4096)
                if time.monotonic() >= deadline:
                    break
                if not chunk:
                    break
                pending += chunk
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    response = json.loads(line)
                    if response.get("id") == 1:
                        initialized = isinstance(response.get("result", {}).get("capabilities"), dict)
                        break
                if initialized:
                    break
    finally:
        selector.close()
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
            process.stdin.close()
            process.stdout.close()
    return {"initialized": initialized, "index_created": (project / ".codegraph").exists(),
            "scope": "protocol_handshake_not_code_navigation"}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "evals/local/integration")
    args = parser.parse_args()
    if not args.run:
        print("Preview: synthetic temporary Git fixture, isolated RTK database, hook JSON, MCP handshake. No model calls.")
        return 0
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cheapskate-integration-") as temporary:
        project = Path(temporary).resolve()
        env = {**os.environ, "RTK_DB_PATH": str(project / "rtk-history.db"),
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}

        def git(*command):
            result = subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull,
                "-c", "user.name=Cheapskate", "-c", "user.email=benchmark@example.invalid",
                "-c", "commit.gpgsign=false", *command], cwd=project, env=env,
                capture_output=True, text=True, check=True)
            return result.stdout

        git("init", "-q")
        for index in range(5):
            (project / "fixture.txt").write_text(f"fixture {index}\n")
            git("add", "fixture.txt")
            git("commit", "-q", "-m", f"sentinel-{index}")
        native = git("log", "-5")
        optimized = subprocess.run(["rtk", "git", "log", "-5"], cwd=project, env=env,
                                   capture_output=True, text=True, check=True).stdout
        sentinels = all(f"sentinel-{index}" in text for index in range(5) for text in (native, optimized))
        event = {"tool_name": "Bash", "tool_input": {"command": "git status", "timeout": 10}}
        codex = HOOK.rewrite(event, "rtk", "codex")
        claude = HOOK.rewrite(event, "rtk", "claude")
        hooks = {"codex_hint": bool(codex and codex["hookSpecificOutput"].get("additionalContext")),
                 "claude_rewrite": bool(claude and claude["hookSpecificOutput"].get("updatedInput")),
                 "no_permission_decisions": all("permissionDecision" not in (item or {}).get("hookSpecificOutput", {})
                                              for item in (codex, claude)),
                 "scope": "standalone_hook_not_client_session"}
        report = {"schema": 1, "rtk": {"native_bytes": len(native.encode()),
            "optimized_bytes": len(optimized.encode()), "native_lines": len(native.splitlines()),
            "optimized_lines": len(optimized.splitlines()), "sentinels_preserved": sentinels,
            "output_bytes_reduction_percent": round(100 * (1 - len(optimized.encode()) / len(native.encode())), 2),
            "scope": "output_bytes_not_provider_tokens_or_billing"}, "hooks": hooks,
            "codegraph": mcp_smoke(project, env)}
        (args.output_dir / "integration.json").write_text(json.dumps(report, indent=2) + "\n")
        (args.output_dir / "native-log.txt").write_text(native)
        (args.output_dir / "rtk-log.txt").write_text(optimized)
        print(json.dumps(report, indent=2))
        return 0 if (sentinels and all(hooks[name] for name in ("codex_hint", "claude_rewrite", "no_permission_decisions"))
                     and report["codegraph"]["initialized"] and not report["codegraph"]["index_created"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
