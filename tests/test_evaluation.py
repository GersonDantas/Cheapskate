"""Tests for usage parsing, eligibility and process timeout without providers."""

import importlib.util
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PAIR = load("pair", "eval-pair.py")
REPORT = load("report", "evaluation_report.py")


class EvaluationTests(unittest.TestCase):
    def test_turn_usage_ignores_snapshots_and_replays(self):
        events = [{"type": "usage.snapshot", "usage": {"input_tokens": 999}},
                  {"type": "turn.completed", "id": "one", "usage": {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 10}},
                  {"type": "turn.completed", "id": "two", "usage": {"input_tokens": 50, "cached_input_tokens": 10, "output_tokens": 5}}]
        events.append(events[1])
        parsed = PAIR.parse_usage("codex", "\n".join(json.dumps(item) for item in events))
        self.assertEqual(parsed["usage"]["input_total"], 150)
        self.assertEqual(parsed["usage"]["input_uncached"], 100)
        self.assertEqual(parsed["usage"]["total"], 165)
        self.assertIsNone(parsed["usage"]["reasoning"])

    def test_missing_usage_is_unknown(self):
        parsed = PAIR.parse_usage("codex", '{"type":"turn.completed"}')
        self.assertIsNone(parsed["usage"]["total"])
        self.assertEqual(parsed["observed_models"], [])

    def test_partial_failure_retains_usage(self):
        events = [{"type": "turn.completed", "usage": {"input_tokens": 5, "cached_input_tokens": 0, "output_tokens": 2}},
                  {"type": "turn.failed"}]
        parsed = PAIR.parse_usage("codex", "\n".join(json.dumps(item) for item in events))
        self.assertTrue(parsed["client_reported_failure"])
        self.assertEqual(parsed["usage"]["total"], 7)

    def test_claude_cache_is_not_double_counted_with_modelusage(self):
        result = {"usage": {"input_tokens": 10, "cache_read_input_tokens": 50,
                            "cache_creation_input_tokens": 20, "output_tokens": 5},
                  "modelUsage": {"exact-model": {"inputTokens": 999}}}
        parsed = PAIR.parse_usage("claude", json.dumps(result))
        self.assertEqual(parsed["usage"]["total"], 85)
        self.assertEqual(parsed["observed_models"], ["exact-model"])

    def test_invalid_shape_and_cache(self):
        with self.assertRaises(ValueError):
            PAIR.parse_usage("claude", "[]")
        with self.assertRaises(ValueError):
            PAIR.parse_usage("codex", '{"type":"turn.completed","usage":{"input_tokens":1,"cached_input_tokens":2}}')

    def test_pending_quality_prevents_percentage(self):
        before = {"host": "codex", "scope": "text-instructions", "client_version": "1",
                  "model_requested": "exact-model", "effort_requested": "medium", "prompt_sha256": "prompt",
                  "observed_models": ["exact-model"], "status": "completed", "usage": {"total": 100},
                  "text_scope_confirmed": True,
                  "answer_sha256": "answer-before"}
        after = {**before, "usage": {"total": 80}, "answer_sha256": "answer-after"}
        pending = REPORT.comparison(before, after)
        self.assertFalse(pending["eligible"])
        self.assertIsNone(pending["token_reduction_percent"])
        review = {"status": "passed", "before_answer_sha256": "answer-before", "after_answer_sha256": "answer-after"}
        self.assertEqual(REPORT.comparison(before, after, review)["token_reduction_percent"], 20)
        after["observed_models"] = []
        self.assertFalse(REPORT.comparison(before, after, review)["eligible"])

    def test_web_search_and_unknown_item_block_text_comparison(self):
        base = {"host": "codex", "scope": "text-instructions", "client_version": "1",
                "model_requested": "exact", "effort_requested": "medium", "prompt_sha256": "prompt",
                "status": "completed", "answer_sha256": "answer"}
        review = {"status": "passed", "before_answer_sha256": "answer", "after_answer_sha256": "answer"}
        for kind, eligible in (("web_search", False), ("new_unknown_item", False), ("agent_message", True), ("reasoning", True)):
            events = [{"type": "thread.started", "model": "exact"},
                      {"type": "item.completed", "item": {"type": kind}},
                      {"type": "turn.completed", "usage": {"input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 2}}]
            metrics = {**base, **PAIR.parse_usage("codex", "\n".join(json.dumps(item) for item in events))}
            self.assertEqual(REPORT.comparison(metrics, metrics, review)["eligible"], eligible)

    def test_timeout_terminates_descendants(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pid = root / "child.pid"
            code = ("import subprocess,sys,time; "
                    "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                    f"open({str(pid)!r},'w').write(str(p.pid)); time.sleep(60)")
            status, timed_out = PAIR.run_process([sys.executable, "-c", code], os.environ.copy(), root,
                                                root / "out", root / "err", 0.3)
            self.assertTrue(timed_out)
            self.assertNotEqual(status, 0)
            child = int(pid.read_text())
            state = subprocess.run(["ps", "-o", "stat=", "-p", str(child)], capture_output=True, text=True)
            self.assertTrue(not state.stdout.strip() or state.stdout.strip().startswith("Z"))

    def test_cap_before_any_inference(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "runs"
            result = subprocess.run([sys.executable, str(ROOT / "scripts/eval-suite.py"),
                                     "--run", "--max-calls", "1", "--output-dir", str(output)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exceeds cap", result.stderr)
            self.assertFalse(output.exists())

    def test_failed_client_does_not_stop_other_host(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            scripts.mkdir()
            for name in ("eval-suite.py", "eval-pair.py", "evaluation_report.py", "eval-instructions.sh", "eval-claude-instructions.sh"):
                shutil.copyfile(ROOT / "scripts" / name, scripts / name)
            (root / "evals").mkdir()
            (root / "evals/synthetic.jsonl").write_text('{"id":"sample","prompt":"synthetic"}\n')
            before = root / "evals/baseline/codex/AGENTS.md"
            before.parent.mkdir(parents=True)
            before.write_text("baseline")
            after = root / "codex/AGENTS.md"
            after.parent.mkdir()
            after.write_text("candidate")
            for directory in (root / "shared", root / "evals/baseline/shared"):
                directory.mkdir(parents=True)
                for name in ("conversation", "code"):
                    (directory / f"{name}-guidelines.md").write_text("fixture")
            fake = root / "bin"
            fake.mkdir()
            codex = fake / "codex"
            codex.write_text(f'#!{sys.executable}\n' +
                'import sys,json,pathlib\n'
                'if "--version" in sys.argv: print("fake 1.0.0")\n'
                'else:\n'
                ' pathlib.Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text("answer")\n'
                ' print(json.dumps({"type":"turn.completed","usage":{"input_tokens":10,"cached_input_tokens":0,"output_tokens":2}}))\n')
            claude = fake / "claude"
            claude.write_text(f'#!{sys.executable}\n' +
                'import sys,json\n'
                'if "--version" in sys.argv: print("fake 1.0.0")\n'
                'elif "status" in sys.argv: print(json.dumps({"loggedIn":True}))\n'
                'else: print(json.dumps({"is_error":True,"result":"synthetic failure"})); sys.exit(1)\n')
            codex.chmod(0o700)
            claude.chmod(0o700)
            auth = root / "auth"
            auth.mkdir()
            (auth / "auth.json").write_text("{}")
            env = {**os.environ, "PATH": str(fake) + os.pathsep + os.environ["PATH"], "CODEX_HOME": str(auth)}
            output = root / "runs"
            result = subprocess.run([sys.executable, str(scripts / "eval-suite.py"),
                                     "--hosts", "claude,codex", "--run", "--max-calls", "4",
                                     "--output-dir", str(output)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            report = json.loads(next(output.glob("*/report.json")).read_text())
            statuses = {pair["host"]: pair["status"] for pair in report["pairs"]}
            self.assertEqual(statuses, {"claude": "failed", "codex": "completed"})
            self.assertEqual(report["client_executions_attempted"], 4)


if __name__ == "__main__":
    unittest.main()
