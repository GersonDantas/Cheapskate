"""Real-prompt runs reject a digest that does not match the reviewed preview."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("suite", ROOT / "scripts/eval-suite.py")
SUITE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUITE)


class ApprovalTests(unittest.TestCase):
    def test_wrong_digest_never_calls_evaluator(self):
        with tempfile.TemporaryDirectory() as temporary:
            preview = Path(temporary) / "preview.jsonl"
            preview.write_text('{"id":"private-01","prompt":"private"}\n')
            calls = []

            def run(command, **kwargs):
                calls.append(command)
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            args = ["eval-suite.py", "--source", "real", "--hosts", "codex", "--run",
                    "--approve-sha", "invalid", "--output-dir", str(Path(temporary) / "runs")]
            with patch.dict(SUITE.SOURCES, {"real": preview}), \
                 patch.object(SUITE.subprocess, "run", run), patch.object(sys, "argv", args):
                with self.assertRaisesRegex(SystemExit, "matching the reviewed preview"):
                    SUITE.main()
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
