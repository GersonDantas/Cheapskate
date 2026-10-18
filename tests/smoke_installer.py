#!/usr/bin/env python3
"""Opt-in smoke test with real installed tools and verified skill downloads."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Allows real skill downloads; no model calls")
    parser.add_argument("--with-team", action="store_true", help="Also tests optional plugin registration in the temporary Codex home")
    args = parser.parse_args()
    if not args.run:
        print("Preview: temporary home; real installed tools; skill downloads; install/check/audit/reinstall/rollback/uninstall.")
        return
    with tempfile.TemporaryDirectory(prefix="cheapskate-smoke-") as temporary:
        home = Path(temporary).resolve() / "home space"
        env = {**os.environ, "CODEX_HOME": str(home / ".codex"),
               "CLAUDE_CONFIG_DIR": str(home / ".claude")}

        def run(command):
            extra = ["--with-team"] if command == "install" and args.with_team else []
            result = subprocess.run([sys.executable, str(ROOT / "scripts/cheapskate.py"),
                                     command, "--home", str(home), "--yes", *extra],
                                    env=env, capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(f"{command} failed: {result.stderr}")

        run("install")
        run("check")
        run("audit")
        registry = home / ".local/state/cheapskate/installed.json"
        installed = registry.read_bytes()
        run("install")
        assert installed == registry.read_bytes(), "Second install changed managed state"
        for name in ("rtk", "codegraph", "graphify"):
            subprocess.run([str(home / f".local/bin/{name}"), "--version"], env=env, check=True)
        run("uninstall")
        assert not (home / ".codex/AGENTS.md").exists()
        run("rollback")
        run("check")
        assert json.loads(registry.read_text())["profile"] == "full"
        run("uninstall")
        print("Real tool/skill smoke test passed. Temporary home removed; no model calls.")


if __name__ == "__main__":
    main()
