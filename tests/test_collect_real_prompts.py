#!/usr/bin/env python3
"""Offline tests for real-prompt sanitization."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "collect_real_prompts", ROOT / "scripts/collect-real-prompts.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def main() -> int:
    source = (
        "Email owner@example.com token=super-secret-token-value "
        "path /Users/example/private and id 123456789012."
    )
    sanitized, flags = MODULE.sanitize(source)
    assert "owner@example.com" not in sanitized
    assert "super-secret-token-value" not in sanitized
    assert "/Users/example" not in sanitized
    assert "123456789012" not in sanitized
    assert "review_repository_and_company_names" in flags
    for secret in ('{"token": "super-secret-token-value"}',
                   '{"token": "first\\\" remaining secret"}',
                   'password = "two word secret"'):
        cleaned, _ = MODULE.sanitize(secret)
        assert "super-secret-token-value" not in cleaned
        assert "two word secret" not in cleaned
        assert "remaining secret" not in cleaned

    assert MODULE.authored_text("<environment_context>hidden</environment_context>") == ""
    assert MODULE.authored_text("A real user request") == "A real user request"

    long_text, long_flags = MODULE.sanitize("x" * 5000)
    assert len(long_text) < 4100
    assert "truncated" in long_flags
    print("Prompt sanitization passed offline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
