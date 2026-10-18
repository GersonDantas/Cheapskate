#!/usr/bin/env python3
"""Create a private, sanitized preview of recent user-authored prompts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


HOME = Path.home()
INJECTED_PREFIXES = (
    "# AGENTS.md instructions",
    "<apps_instructions>",
    "<collaboration_mode>",
    "<developer",
    "<environment_context>",
    "<permissions instructions>",
    "<plugins_instructions>",
    "<recommended_plugins>",
    "<skills_instructions>",
    "<skill>",
    "<system-reminder>",
)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"\b(?:sk|ghp|github_pat|xox[baprs])[-_A-Za-z0-9]{12,}\b", re.I),
    re.compile(r"(?i)\b(api[_-]?key|token|password|secret)\b[\"']?\s*[:=]\s*(?:\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'|[^\s,;}\]]+)"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
)
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f-]{27}[0-9a-f]\b", re.I)
ACCOUNT_ID = re.compile(r"(?<!\d)\d{10,18}(?!\d)")
HOME_PATH = re.compile(r"/(?:Users|home)/[^/\s]+")
VOLUME_PATH = re.compile(r"/Volumes/[^/\s]+")
TEMP_PATH = re.compile(r"/var/folders/[^\s]+")
NAMED_REFERENCE = re.compile(
    r"(?:github\.com/[^\s)]+|\b[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\b|\.git\b)", re.I
)


def records(path: Path):
    try:
        with path.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def authored_text(text: str) -> str:
    stripped = text.strip()
    marker = "## My request for Codex:"
    if stripped.startswith(("# Files mentioned by the user:", "# Response annotations:")):
        return stripped.split(marker, 1)[1].strip() if marker in stripped else ""
    if not stripped or stripped.startswith(INJECTED_PREFIXES):
        return ""
    return stripped


def sanitize(text: str) -> tuple[str, list[str]]:
    flags = ["review_repository_and_company_names"]
    text = text.replace("\u2028", "\n").replace("\u2029", "\n").replace("\x85", "\n")
    if NAMED_REFERENCE.search(text):
        flags.append("named_reference_detected")
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED_SECRET]", text)
    text = EMAIL.sub("[REDACTED_EMAIL]", text)
    text = UUID.sub("[REDACTED_ID]", text)
    text = ACCOUNT_ID.sub("[REDACTED_ACCOUNT_ID]", text)
    text = HOME_PATH.sub("~", text)
    text = VOLUME_PATH.sub("[REDACTED_VOLUME]", text)
    text = TEMP_PATH.sub("[REDACTED_TEMP_PATH]", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > 4000:
        text = text[:4000].rstrip() + "\n\n[TRUNCATED]"
        flags.append("truncated")
    return text, flags


def codex_session(path: Path):
    messages: list[tuple[str, str]] = []
    latest_completion = ""
    for item in records(path):
        payload = item.get("payload") or {}
        if item.get("type") == "event_msg" and payload.get("type") == "task_complete":
            latest_completion = max(latest_completion, item.get("timestamp", ""))
        if item.get("type") != "response_item" or payload.get("type") != "message":
            continue
        if payload.get("role") != "user":
            continue
        parts = [
            authored_text(content.get("text", ""))
            for content in payload.get("content") or []
            if content.get("type") == "input_text"
        ]
        text = "\n\n".join(filter(None, parts))
        if text:
            messages.append((item.get("timestamp", ""), text))
    if not messages or latest_completion < messages[-1][0]:
        return None
    return max(messages, key=lambda item: len(item[1]))


def claude_session(path: Path):
    messages: list[tuple[str, str]] = []
    latest_user = latest_assistant = ""
    for item in records(path):
        timestamp = item.get("timestamp", "")
        if item.get("type") == "assistant":
            latest_assistant = max(latest_assistant, timestamp)
        if item.get("type") != "user" or item.get("isSidechain") is True:
            continue
        content = (item.get("message") or {}).get("content")
        if not isinstance(content, str):
            continue
        content = authored_text(content)
        if content:
            latest_user = max(latest_user, timestamp)
            messages.append((timestamp, content))
    if not messages or latest_assistant < latest_user:
        return None
    return max(messages, key=lambda item: len(item[1]))


def recent_sessions(root: Path, parser, limit: int):
    found = []
    if not root.exists():
        return found
    for path in sorted(root.rglob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True):
        parsed = parser(path)
        if parsed:
            found.append((path, *parsed))
        if len(found) >= limit:
            break
    return found


def main() -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20, choices=range(1, 21))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "evals/local",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    candidates = []
    sources = (
        ("codex", HOME / ".codex/sessions", codex_session),
        ("claude", HOME / ".claude/projects", claude_session),
    )
    for host, root, session_parser in sources:
        for index, (path, timestamp, raw) in enumerate(
            recent_sessions(root, session_parser, args.limit), 1
        ):
            prompt, flags = sanitize(raw)
            if prompt:
                candidates.append(
                    {
                        "id": f"{host}-{index:02d}",
                        "host": host,
                        "timestamp": timestamp,
                        "source_hash": hashlib.sha256(str(path).encode()).hexdigest()[:12],
                        "review_flags": flags,
                        "prompt": prompt,
                    }
                )

    jsonl_path = args.output_dir / "real-prompt-preview.jsonl"
    markdown_path = args.output_dir / "real-prompt-preview.md"
    with jsonl_path.open("w", encoding="utf-8") as stream:
        for item in candidates:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    generated = datetime.now(timezone.utc).isoformat()
    with markdown_path.open("w", encoding="utf-8") as stream:
        stream.write("# Private real-prompt preview\n\n")
        stream.write(f"Generated locally: `{generated}`\n\n")
        stream.write("Nothing in this file has been sent to a model. Review every item before use.\n\n")
        for item in candidates:
            stream.write(f"## {item['id']}\n\n")
            stream.write(f"Review: `{', '.join(item['review_flags'])}`\n\n")
            stream.write("```text\n" + item["prompt"].replace("```", "` ` `") + "\n```\n\n")
    jsonl_path.chmod(0o600)
    markdown_path.chmod(0o600)
    digest = hashlib.sha256(jsonl_path.read_bytes()).hexdigest()
    print(json.dumps({"count": len(candidates), "sha256": digest}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
