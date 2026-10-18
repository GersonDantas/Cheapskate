"""Exercise installation and recovery entirely in temporary directories."""

import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("installer", ROOT / "scripts/cheapskate.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
HOOK_SPEC = importlib.util.spec_from_file_location("rtk_hook", ROOT / "hooks/rtk.py")
H = importlib.util.module_from_spec(HOOK_SPEC)
HOOK_SPEC.loader.exec_module(H)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cheapskate test ")
        self.home = Path(self.temp.name).resolve() / "user space"
        self.environment = patch.dict(os.environ, {}, clear=False)
        self.environment.start()
        os.environ.pop("CODEX_HOME", None)
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        self.installer = M.Installer(self.home)

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts/cheapskate.py"),
                               *args, "--home", str(self.home)], capture_output=True, text=True)

    def test_dry_run_no_files(self):
        result = self.cli("install", "--instructions-only", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.home.exists())

    def test_install_update_restore_user_content(self):
        original = self.home / ".codex/AGENTS.md"
        original.parent.mkdir(parents=True)
        original.write_text("User instructions\n")
        original.chmod(0o640)
        unrelated = self.home / ".config/ai-instructions/private-notes.md"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text("keep")
        installer = M.Installer(self.home)
        desired = installer.desired()
        installer.apply(desired, False)
        self.assertIn("User instructions", original.read_text())
        self.assertEqual(installer.apply(installer.desired(), False), 0)
        self.assertEqual(self.cli("check").returncode, 0)
        self.assertEqual(self.cli("audit").returncode, 0)
        installer.uninstall()
        self.assertEqual(original.read_text(), "User instructions\n")
        self.assertEqual(original.stat().st_mode & 0o777, 0o640)
        self.assertEqual(unrelated.read_text(), "keep")

    def test_edit_blocks_all_mutations(self):
        installer = self.installer
        installer.apply(installer.desired(), False)
        (installer.codex / "AGENTS.md").write_text("later edit")
        for command in ("update", "uninstall", "rollback"):
            result = self.cli(command, "--yes")
            self.assertNotEqual(result.returncode, 0)
        self.assertEqual((installer.codex / "AGENTS.md").read_text(), "later edit")

    def test_symlink_and_broken_symlink(self):
        installer = self.installer
        path = installer.codex / "AGENTS.md"
        path.parent.mkdir(parents=True)
        path.symlink_to(installer.active / "codex/AGENTS.md")
        installer.apply(installer.desired(), False)
        installer.uninstall()
        self.assertTrue(path.is_symlink())
        self.assertFalse(path.exists())
        path.unlink()
        path.symlink_to(self.home / "external.md")
        with self.assertRaises(M.Conflict):
            installer.desired()

    def test_symlink_parent_refused(self):
        self.home.mkdir(parents=True)
        (self.home / ".config").symlink_to(Path(self.temp.name))
        with self.assertRaises(M.Conflict):
            self.installer.desired()

    def test_invalid_json_toml_fail_before_apply(self):
        self.installer.codex.mkdir(parents=True)
        self.installer.codex.joinpath("config.toml").write_text("[broken")
        tools = {name: "/bin/true" for name in ("rtk", "codegraph", "graphify")}
        with self.assertRaises(ValueError):
            self.installer.desired(True, tools)
        self.assertFalse(self.installer.registry_path.exists())

    def test_failed_write_rolls_back(self):
        installer = self.installer
        desired = installer.desired()
        restore = M.restore
        count = 0

        def fail_once(path, state):
            nonlocal count
            count += 1
            if count == 3:
                raise OSError("simulated denied write")
            return restore(path, state)

        with patch.object(M, "restore", side_effect=fail_once):
            with self.assertRaises(OSError):
                installer.apply(desired, False)
        self.assertFalse((installer.codex / "AGENTS.md").exists())
        self.assertEqual(json.loads(installer.transaction_path.read_text())["status"], "rolled_back")

    def test_interrupted_transaction_recovery(self):
        installer = self.installer
        changes = installer.changes(installer.desired())
        transaction = {"status": "applying", "changes": changes,
                       "previous": installer.registry, "next": {}}
        M.atomic_write(installer.transaction_path, M.json_bytes(transaction))
        M.restore(Path(changes[0]["path"]), changes[0]["after"])
        result = self.cli("install", "--instructions-only", "--yes")
        self.assertNotEqual(result.returncode, 0)
        result = self.cli("rollback", "--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(Path(changes[0]["path"]).exists())

    def test_lock_rejects_concurrent_operation(self):
        self.installer.state.mkdir(parents=True)
        with (self.installer.state / "lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.cli("install", "--instructions-only", "--yes")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.installer.codex / "AGENTS.md").exists())

    def test_custom_host_directories(self):
        os.environ["CODEX_HOME"] = str(self.home / "custom codex")
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.home / "custom claude")
        installer = M.Installer(self.home)
        installer.apply(installer.desired(), False)
        self.assertTrue((installer.codex / "AGENTS.md").exists())
        self.assertFalse((self.home / ".codex").exists())

    def test_full_merge_and_idempotence(self):
        installer = self.installer
        installer.claude.mkdir(parents=True)
        settings = installer.claude / "settings.json"
        settings.write_text(json.dumps({"userKey": True, "hooks": {"SessionStart": []}}))
        config = installer.codex / "config.toml"
        config.parent.mkdir(parents=True)
        config.write_text('model = "user-choice"\n')
        tools = {name: "/bin/true" for name in ("rtk", "codegraph", "graphify")}
        skills = {name: b"synthetic skill" for name in installer.manifest["skills"]}
        skills.update({f"{name}/{relative}": b"synthetic reference"
                       for name, relative, spec in M.skill_resources(installer.manifest)
                       if relative != "SKILL.md"})
        desired = installer.desired(True, tools, skills)
        installer.apply(desired, True, tools)
        self.assertTrue(json.loads(settings.read_text())["userKey"])
        self.assertIn('model = "user-choice"', config.read_text())
        self.assertEqual(installer.apply(installer.desired(True, tools, skills), True, tools), 0)
        installer.uninstall()
        self.assertEqual(config.read_text(), 'model = "user-choice"\n')
        self.assertTrue(json.loads(settings.read_text())["userKey"])

    def test_download_integrity_refusal(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b"wrong data"

        with patch.object(M.urllib.request, "urlopen", return_value=Response()):
            with self.assertRaises(M.Conflict):
                M.download({"url": "https://example.org/data", "sha256": "0" * 64})

    def test_unknown_hook_refused_and_native_migrated(self):
        installer = self.installer
        settings = installer.claude / "settings.json"
        settings.parent.mkdir(parents=True)
        tools = {name: "/bin/true" for name in ("rtk", "codegraph", "graphify")}
        for matcher, command in (("Write", "rtk hook claude"), ("Bash", "echo rtk")):
            settings.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": matcher,
                                   "hooks": [{"type": "command", "command": command}]}]}}))
            with self.assertRaises(M.Conflict):
                installer.desired(True, tools)
        settings.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash",
                               "hooks": [{"type": "command", "command": "rtk hook claude"}]}]}}))
        desired = installer.desired(True, tools)
        after = json.loads(M.base64.b64decode(desired[str(settings)]["data"]))
        self.assertEqual(len(after["hooks"]["PreToolUse"]), 1)
        self.assertIn("ai-instructions/hooks/rtk.py", str(after))

    def test_skill_pin_change_and_rollback(self):
        installer = self.installer
        original = b"old skill"
        updated = b"new skill"
        spec = installer.manifest["skills"]["caveman"]
        spec["sha256"] = hashlib.sha256(original).hexdigest()
        path = installer.codex / "skills/caveman/SKILL.md"
        installer.apply({str(path): M.file_state(original)}, False)
        spec["sha256"] = hashlib.sha256(updated).hexdigest()
        with patch.object(M, "download", return_value=updated):
            self.assertEqual(installer.prepare_skills()["caveman"], updated)
        installer.apply({str(path): M.file_state(updated)}, False)
        self.assertEqual(path.read_bytes(), updated)
        installer.recover(M.read_json(installer.transaction_path, {}))
        self.assertEqual(path.read_bytes(), original)

    def test_local_binary_is_not_wrapped_recursively(self):
        installer = self.installer
        local = self.home / ".local/bin/graphify"
        local.parent.mkdir(parents=True)
        local.write_text("existing binary")
        tools = {"rtk": "/bin/true", "codegraph": "/bin/true", "graphify": str(local)}
        self.assertNotIn(str(local), installer.desired(True, tools))

    def test_existing_team_skips_all_install_commands(self):
        installer = self.installer
        result = subprocess.CompletedProcess([], 0, json.dumps({"installed": [{
            "pluginId": "personal-agent-team-codex@agent-team-configurator", "version": "0.5.0"}]}), "")
        with patch.object(M.subprocess, "run", return_value=result) as run:
            installer.install_team()
            self.assertTrue(installer.codex.is_dir())
            self.assertEqual(run.call_count, 1)
            self.assertIn("list", run.call_args.args[0])
            self.assertEqual(run.call_args.kwargs["env"]["CODEX_HOME"], str(installer.codex))

    def test_incomplete_team_snapshot_refused(self):
        installer = self.installer
        directory = installer.state / "team" / installer.manifest["team"]["revision"]
        directory.mkdir(parents=True)
        result = subprocess.CompletedProcess([], 0, '{"installed":[]}', "")
        with patch.object(M.subprocess, "run", return_value=result) as run:
            with self.assertRaises(M.Conflict):
                installer.install_team()
            self.assertEqual(run.call_count, 1)

    def test_plugin_failure_records_remaining_effects(self):
        installer = self.installer
        directory = installer.state / "team" / installer.manifest["team"]["revision"]
        plugin = directory / "plugins/personal-agent-team-codex/.codex-plugin/plugin.json"
        plugin.parent.mkdir(parents=True)
        plugin.write_text('{"version":"0.5.0"}')
        M.atomic_write(directory / ".cheapskate-complete.json",
                       M.json_bytes({str(plugin.relative_to(directory)): hashlib.sha256(plugin.read_bytes()).hexdigest()}))

        def run(command, **kwargs):
            if "marketplace" in command and "list" in command:
                return subprocess.CompletedProcess(command, 0, '{"marketplaces":[]}', "")
            if "list" in command:
                return subprocess.CompletedProcess(command, 0, '{"installed":[]}', "")
            if "marketplace" in command:
                return subprocess.CompletedProcess(command, 0)
            raise subprocess.CalledProcessError(1, command)

        with patch.object(M.subprocess, "run", side_effect=run):
            with self.assertRaises(M.Conflict):
                installer.install_team()
        effects = M.read_json(installer.state / "external-effects.json", {})
        self.assertEqual(len(effects["completed"]), 1)
        self.assertIn("marketplace", effects["completed"][0])
        self.assertIsNotNone(effects["pending"])

    def test_managed_config_blocks_external_plugin_mutation(self):
        installer = self.installer
        path = installer.codex / "config.toml"
        installer.apply({str(path): M.file_state(b'model = "user-model"\n')}, False)
        with patch.object(M.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, '{"installed":[]}', "")) as run:
            with self.assertRaises(M.Conflict):
                installer.install_team()
            self.assertEqual(run.call_count, 1)
        self.assertIn("user-model", path.read_text())

    def test_rewrite_preserves_args_and_skips_composition(self):
        event = {"tool_name": "Bash", "tool_input": {"command": "git status", "timeout": 5, "cwd": "/tmp"}}
        result = subprocess.CompletedProcess([], 0, "rtk git status\n", "")
        with patch.object(H.subprocess, "run", return_value=result):
            output = H.rewrite(event, "rtk")
            self.assertEqual(output["hookSpecificOutput"]["updatedInput"]["timeout"], 5)
            self.assertNotIn("permissionDecision", output["hookSpecificOutput"])
            codex = H.rewrite(event, "rtk", "codex")
            self.assertNotIn("permissionDecision", codex["hookSpecificOutput"])
            self.assertNotIn("updatedInput", codex["hookSpecificOutput"])
            for command in ("git commit", "git status && ls", "rtk git status", "git status > out"):
                event["tool_input"]["command"] = command
                self.assertIsNone(H.rewrite(event, "rtk"))


if __name__ == "__main__":
    unittest.main()
