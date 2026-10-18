"""Exercise the macOS bootstrap with command stubs and an isolated home."""

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "scripts/bootstrap.sh"


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cheapskate bootstrap ")
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.pending = self.root / "pending"
        self.home = self.root / "home"
        self.scripts = self.root / "project with spaces/scripts"
        for path in (self.bin, self.pending, self.home, self.scripts):
            path.mkdir(parents=True)
        self.log = self.root / "commands.log"
        script = SOURCE.read_text()
        script = script.replace("/opt/homebrew/bin/brew", str(self.bin / "brew"))
        script = script.replace("/usr/local/bin/brew", str(self.bin / "brew"))
        self.bootstrap = self.scripts / "bootstrap.sh"
        self.bootstrap.write_text(script)
        self.stub("uname", 'if [ "$1" = -s ]; then echo Darwin; else echo arm64; fi')
        for name, target in (("dirname", "/usr/bin/dirname"), ("grep", "/usr/bin/grep"),
                             ("mkdir", "/bin/mkdir"), ("rm", "/bin/rm"),
                             ("mktemp", "/usr/bin/mktemp")):
            (self.bin / name).symlink_to(target)
        self.stub("python3", 'exit 1')
        self.stub("python3.11", '''
if [ "$1" = -c ]; then exit 0; fi
echo "python $*" >> "$BOOTSTRAP_LOG"
exit 0''', pending=True)
        for name in ("node", "npm", "pipx"):
            self.stub(name, 'exit 0', pending=True)
        self.stub("codex", '''
if [ "$1" = login ] && [ "$2" = status ]; then
  [ -f "$BOOTSTRAP_HOME/codex-logged-in" ]; exit $?
fi
if [ "$1" = login ]; then
  echo "codex login" >> "$BOOTSTRAP_LOG"
  : > "$BOOTSTRAP_HOME/codex-logged-in"
fi''', pending=True)
        self.stub("claude", '''
if [ "$1" = auth ] && [ "$2" = status ]; then
  [ -f "$BOOTSTRAP_HOME/claude-logged-in" ]; exit $?
fi
if [ "$1" = auth ] && [ "$2" = login ]; then
  echo "claude login" >> "$BOOTSTRAP_LOG"
  : > "$BOOTSTRAP_HOME/claude-logged-in"
fi''', pending=True)
        self.stub("brew", '''
echo "brew $*" >> "$BOOTSTRAP_LOG"
case "$*" in
  'install python@3.11') /bin/cp "$BOOTSTRAP_PENDING/python3.11" "$BOOTSTRAP_BIN/" ;;
  'install node') /bin/cp "$BOOTSTRAP_PENDING/node" "$BOOTSTRAP_PENDING/npm" "$BOOTSTRAP_BIN/" ;;
  'install pipx') /bin/cp "$BOOTSTRAP_PENDING/pipx" "$BOOTSTRAP_BIN/" ;;
  'install --cask codex') /bin/cp "$BOOTSTRAP_PENDING/codex" "$BOOTSTRAP_BIN/" ;;
  'install --cask claude-code') /bin/cp "$BOOTSTRAP_PENDING/claude" "$BOOTSTRAP_BIN/" ;;
esac''', pending=True)
        self.stub("curl", '''
echo "curl $*" >> "$BOOTSTRAP_LOG"
while [ "$1" != -o ]; do shift; done
/bin/cp "$BOOTSTRAP_PENDING/homebrew-install" "$2"''')
        self.stub("homebrew-install", '/bin/cp "$BOOTSTRAP_PENDING/brew" "$BOOTSTRAP_BIN/brew"', pending=True)

    def tearDown(self):
        self.temp.cleanup()

    def stub(self, name, body, pending=False):
        path = (self.pending if pending else self.bin) / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def run_bootstrap(self, *args, input_text=None, arch="arm64"):
        env = os.environ.copy()
        env.update(PATH=str(self.bin), HOME=str(self.home), SHELL="/opt/homebrew/bin/fish",
                   TMPDIR=str(self.root), BOOTSTRAP_BIN=str(self.bin),
                   BOOTSTRAP_PENDING=str(self.pending), BOOTSTRAP_HOME=str(self.home),
                   BOOTSTRAP_LOG=str(self.log))
        if arch == "x86_64":
            self.stub("uname", 'if [ "$1" = -s ]; then echo Darwin; else echo x86_64; fi')
        return subprocess.run(["/bin/bash", str(self.bootstrap), *args], input=input_text,
                              capture_output=True, text=True, env=env)

    def test_dry_run_and_refusal_do_not_write(self):
        preview = self.run_bootstrap("--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("Instalar Homebrew", preview.stdout)
        self.assertIn("brew install python@3.11", preview.stdout)
        self.assertFalse(self.log.exists())
        refused = self.run_bootstrap(input_text="n\n")
        self.assertEqual(refused.returncode, 0, refused.stderr)
        self.assertFalse(self.log.exists())
        self.assertEqual(list(self.home.iterdir()), [])

    def test_full_flow_and_repeat_preserve_existing_state(self):
        first = self.run_bootstrap(input_text="s\ns\ns\n")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("Preparação concluída", first.stdout)
        log = self.log.read_text()
        for command in ("curl ", "brew install python@3.11", "brew install node",
                        "brew install pipx", "brew install --cask codex",
                        "brew install --cask claude-code", "codex login", "claude login",
                        "install --dry-run", "install", "check"):
            self.assertIn(command, log)
        profile = self.home / ".config/fish/config.fish"
        self.assertIn("fish_add_path", profile.read_text())
        second = self.run_bootstrap(input_text="s\n")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.log.read_text().count("brew install"), 5)
        self.assertEqual(self.log.read_text().count("codex login"), 1)
        self.assertEqual(self.log.read_text().count("claude login"), 1)
        self.assertEqual(profile.read_text().count("# Cheapskate bootstrap PATH"), 1)

    def test_package_failure_stops_before_login_and_is_recoverable(self):
        self.stub("brew", 'echo "brew $*" >> "$BOOTSTRAP_LOG"; exit 1', pending=True)
        failed = self.run_bootstrap(input_text="s\n", arch="x86_64")
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("Instalação do Python falhou", failed.stderr)
        self.assertNotIn("codex login", self.log.read_text())
        self.assertFalse((self.home / ".config/fish/config.fish").exists())

    def test_old_python_is_replaced_by_explicit_311_path(self):
        shutil.copy2(self.pending / "brew", self.bin / "brew")
        result = self.run_bootstrap("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("brew install python@3.11", result.stdout)
        self.assertNotIn("Instalar Homebrew", result.stdout)

    def test_homebrew_outside_path_is_reused(self):
        outside = self.root / "outside/bin/brew"
        outside.parent.mkdir(parents=True)
        shutil.copy2(self.pending / "brew", outside)
        script = self.bootstrap.read_text().replace(str(self.bin / "brew"), str(outside))
        self.bootstrap.write_text(script)
        result = self.run_bootstrap("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Instalar Homebrew", result.stdout)

    def test_skipped_logins_continue_to_installer(self):
        result = self.run_bootstrap(input_text="s\nn\nn\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        log = self.log.read_text()
        self.assertNotIn("codex login", log)
        self.assertNotIn("claude login", log)
        self.assertIn("install --dry-run", log)
        self.assertIn("check", log)
        self.assertIn("codex login", result.stdout)
        self.assertIn("claude auth login", result.stdout)

    def test_failed_logins_continue_to_installer(self):
        for name in ("codex", "claude"):
            self.stub(name, f'echo "{name} $*" >> "$BOOTSTRAP_LOG"; exit 1', pending=True)
        result = self.run_bootstrap(input_text="s\ns\ns\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Login do Codex não foi concluído", result.stdout)
        self.assertIn("Login do Claude Code não foi concluído", result.stdout)
        log = self.log.read_text()
        self.assertIn("codex login\n", log)
        self.assertIn("claude auth login\n", log)
        self.assertIn("check", log)

    def test_unconfirmed_logins_continue_to_installer(self):
        for name in ("codex", "claude"):
            self.stub(name, 'if [ "$2" = status ]; then exit 1; fi; exit 0', pending=True)
        result = self.run_bootstrap(input_text="s\ns\ns\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Login do Codex não foi confirmado", result.stdout)
        self.assertIn("Login do Claude Code não foi confirmado", result.stdout)
        self.assertIn("check", self.log.read_text())

    def test_login_prompt_eof_skips_authentication(self):
        result = self.run_bootstrap(input_text="s\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("codex login", self.log.read_text())
        self.assertNotIn("claude login", self.log.read_text())
        self.assertIn("check", self.log.read_text())

    def test_integrity_failure_still_stops_after_skipping_logins(self):
        self.stub("python3.11", '''
if [ "$1" = -c ]; then exit 0; fi
echo "python $*" >> "$BOOTSTRAP_LOG"
if [ "$2" = check ]; then exit 1; fi
exit 0''', pending=True)
        result = self.run_bootstrap(input_text="s\nn\nn\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Verificação do Cheapskate falhou", result.stderr)
        self.assertNotIn("Preparação concluída", result.stdout)

    def test_native_clients_outside_initial_path_are_reused(self):
        local_bin = self.home / ".local/bin"
        local_bin.mkdir(parents=True)
        for name in ("codex", "claude"):
            shutil.copy2(self.pending / name, local_bin / name)
        result = self.run_bootstrap("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Codex CLI: presente", result.stdout)
        self.assertIn("Claude Code: presente", result.stdout)
        self.assertNotIn("brew install --cask", result.stdout)


if __name__ == "__main__":
    unittest.main()
