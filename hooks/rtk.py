#!/usr/bin/env python3
"""Rewrite simple read/test shell calls with RTK's own command mapping."""

import json
import re
import subprocess
import sys


def rewrite(event, rtk, host="claude"):
    if event.get("tool_name") != "Bash":
        return None
    inputs = event.get("tool_input")
    command = inputs.get("command") if isinstance(inputs, dict) else None
    if not isinstance(command, str) or re.search(r"[\n|;&><`$]", command):
        return None
    allowed = (
        r"(?:ls|tree|cat|head|tail|rg|grep|find|fd|wc|du)\b",
        r"git\s+(?:status|diff|log|show|rev-parse|ls-files)\b",
        r"(?:cargo\s+(?:test|check|clippy)|go\s+test|pytest)\b",
        r"(?:npm|pnpm|yarn)\s+(?:test|run\s+(?:test|lint|check))\b",
    )
    if not any(re.match(pattern, command.strip()) for pattern in allowed):
        return None
    try:
        result = subprocess.run([rtk, "rewrite", command], capture_output=True,
                                text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    changed = result.stdout.strip()
    if result.returncode not in (0, 3) or not changed or changed == command:
        return None
    if host == "codex":
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                "additionalContext": f"For this command, RTK provides: {changed}. Use RTK explicitly on subsequent calls."}}
    # Omit permissionDecision so normal Claude permission processing still applies.
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "updatedInput": {**inputs, "command": changed}}}


if __name__ == "__main__":
    try:
        output = rewrite(json.load(sys.stdin), sys.argv[1], sys.argv[2])
        if output:
            print(json.dumps(output))
    except (ValueError, IndexError, TypeError):
        pass
