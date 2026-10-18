#!/usr/bin/env python3
"""macOS configuration installer. Python 3.11+, no third-party libraries."""

from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
SHARED = ("conversation", "code", "rtk", "codegraph", "graphify", "caveman")


class Conflict(RuntimeError):
    pass


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def file_state(content, mode=0o600):
    return {"type": "file", "data": base64.b64encode(content).decode(), "mode": mode}


def snapshot(path):
    if path.is_symlink():
        return {"type": "link", "target": os.readlink(path)}
    if not path.exists():
        return {"type": "absent"}
    if not path.is_file():
        raise Conflict(f"Destino não é arquivo: {path}")
    return file_state(path.read_bytes(), stat.S_IMODE(path.stat().st_mode))


def parent_guard(path):
    for parent in path.parents:
        if parent.is_symlink():
            raise Conflict(f"Diretório pai é um symlink: {parent}")
        if parent.exists() and not parent.is_dir():
            raise Conflict(f"Diretório pai inválido: {parent}")


def atomic_write(path, content, mode=0o600):
    parent_guard(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".cheapskate-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def restore(path, state):
    parent_guard(path)
    if state["type"] == "file":
        atomic_write(path, base64.b64decode(state["data"]), state["mode"])
    elif state["type"] == "link":
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".cheapskate-link-", dir=path.parent)
        os.close(descriptor)
        os.unlink(name)
        try:
            os.symlink(state["target"], name)
            os.replace(name, path)
        finally:
            if os.path.islink(name):
                os.unlink(name)
    elif path.exists() or path.is_symlink():
        path.unlink()


def read_json(path, default):
    if path.is_symlink():
        raise Conflict(f"Arquivo de configuração é symlink: {path}")
    result = json.loads(path.read_text()) if path.exists() else default
    if not isinstance(result, dict):
        raise Conflict(f"JSON precisa ser objeto: {path}")
    return result


def hook_entries(config):
    hooks = config.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise Conflict("Campo hooks precisa ser um objeto")
    entries = hooks.setdefault("PreToolUse", [])
    if not isinstance(entries, list):
        raise Conflict("PreToolUse precisa ser uma lista")
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
            raise Conflict("Entrada PreToolUse inválida")
        for handler in entry["hooks"]:
            if not isinstance(handler, dict) or not isinstance(handler.get("command", ""), str):
                raise Conflict("Handler PreToolUse inválido")
    return entries


def download(spec):
    if not spec["url"].startswith("https://"):
        raise Conflict("Download precisa usar HTTPS")
    with urllib.request.urlopen(spec["url"], timeout=60) as response:
        data = response.read()
    algorithm = "sha512" if "sha512" in spec else "sha256"
    if hashlib.new(algorithm, data).hexdigest() != spec[algorithm]:
        raise Conflict(f"Integridade inválida: {spec['url']}")
    return data


def version(path):
    result = subprocess.run([str(path), "--version"], capture_output=True,
                            text=True, timeout=15, check=False)
    match = re.search(r"\b\d+\.\d+\.\d+\b", result.stdout)
    return match.group() if result.returncode == 0 and match else "desconhecida"


def skill_resources(manifest):
    for name, spec in manifest["skills"].items():
        yield name, "SKILL.md", spec
        for filename, digest in spec.get("references", {}).items():
            yield name, f"references/{filename}", {"url": spec["reference_base"] + filename, "sha256": digest}


class Installer:
    def __init__(self, home, source=ROOT):
        self.home = Path(home).absolute()
        self.source = Path(source)
        if self.home == Path("/") or self.home == self.source.absolute():
            raise Conflict("Diretório pessoal alvo inválido")
        self.active = self.home / ".config/ai-instructions"
        self.state = self.home / ".local/state/cheapskate"
        self.codex = Path(os.environ.get("CODEX_HOME", str(self.home / ".codex"))).absolute()
        self.claude = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(self.home / ".claude"))).absolute()
        self.registry_path = self.state / "installed.json"
        self.transaction_path = self.state / "transaction.json"
        parent_guard(self.registry_path)
        self.manifest = json.loads((self.source / "dependencies.json").read_text())
        self.registry = read_json(self.registry_path, {"files": {}, "profile": "instructions"})
        self.validate_paths(self.registry["files"])

    def validate_paths(self, names):
        allowed = {str(self.active / f"shared/{name}-guidelines.md") for name in SHARED}
        allowed.update(str(self.active / name) for name in (
            "codex/AGENTS.md", "claude/CLAUDE.md", "generic/INSTRUCTIONS.md",
            "scripts/cheapskate.py", "hooks/rtk.py", "dependencies.json",
            "codex/rtk-guidelines.md", "claude/host-guidelines.md"))
        allowed.update(str(self.home / f".local/bin/{name}") for name in ("cheapskate", "rtk", "codegraph", "graphify"))
        allowed.update(str(path) for path in (self.codex / "AGENTS.md", self.claude / "CLAUDE.md",
            self.codex / "hooks.json", self.claude / "settings.json", self.codex / "config.toml",
            self.claude / ".claude.json", self.home / ".claude.json"))
        allowed.update(str(directory / f"skills/{name}/SKILL.md")
                       for directory in (self.codex, self.claude) for name in self.manifest["skills"])
        allowed.update(str(directory / f"skills/{name}/{relative}")
                       for directory in (self.codex, self.claude)
                       for name, relative, spec in skill_resources(self.manifest))
        if set(names) - allowed:
            raise Conflict("Journal contém destinos fora da lista de arquivos gerenciados")

    def verify_owned(self):
        for name, entry in self.registry["files"].items():
            path = Path(name)
            parent_guard(path)
            if snapshot(path) != entry["installed"]:
                raise Conflict(f"Alteração posterior preservada: {path}. Reconcilie antes de continuar.")

    def pending(self):
        tx = read_json(self.transaction_path, {})
        return tx if tx.get("status") == "applying" else None

    def tools(self):
        tools = {}
        for name in ("rtk", "codegraph", "graphify"):
            managed = self.state / "runtime" / name / self.manifest[name]["version"] / "bin" / name
            found = self.registry.get("tools", {}).get(name)
            found = found or (str(managed) if managed.is_file() else shutil.which(name))
            if found and not Path(found).is_file():
                found = None
            tools[name] = found
            if found and version(found) != self.manifest[name]["version"]:
                if Path(found).is_relative_to(self.state / "runtime" / name):
                    found = str(managed) if managed.is_file() else None
                else:
                    raise Conflict(f"{name}: versão {version(found)}, esperada {self.manifest[name]['version']}. "
                                   "A versão existente foi preservada; compatibilidade não validada.")
            if found and version(found) != self.manifest[name]["version"]:
                raise Conflict(f"Runtime privado de {name} tem versão inesperada")
            tools[name] = found
        return tools

    def desired(self, full=False, tools=None, skill_data=None):
        files = {}

        def add(path, content, mode=0o600):
            parent_guard(path)
            files[str(path)] = file_state(content, mode)

        parts = [(self.source / f"shared/{name}-guidelines.md").read_bytes() for name in SHARED]
        for name, content in zip(SHARED, parts):
            add(self.active / f"shared/{name}-guidelines.md", content)
        shared = b"\n\n".join(parts)
        notes = b"\n\n" + (self.source / "codex/rtk-guidelines.md").read_bytes() if full else b""
        bundle = shared + notes
        add(self.active / "codex/AGENTS.md", bundle)
        # Embedded Claude adapter avoids relative-import behavior through a global symlink.
        claude_notes = b"\n\n" + (self.source / "claude/host-guidelines.md").read_bytes() if full else b""
        add(self.active / "claude/CLAUDE.md", shared + claude_notes)
        add(self.active / "generic/INSTRUCTIONS.md", shared)

        for directory, leaf, content in ((self.codex, "AGENTS.md", bundle),
                                          (self.claude, "CLAUDE.md", shared + claude_notes)):
            path = directory / leaf
            entry = self.registry["files"].get(str(path))
            prior = entry["original"] if entry else snapshot(path)
            if prior["type"] == "link":
                target = Path(prior["target"])
                if not target.is_absolute():
                    target = path.parent / target
                if target.absolute() != self.active / ("codex/AGENTS.md" if leaf == "AGENTS.md" else "claude/CLAUDE.md"):
                    raise Conflict(f"Entrada global aponta para arquivo externo: {path}")
                original = b""
            elif prior["type"] == "file":
                original = base64.b64decode(prior["data"]) + b"\n\n"
            else:
                original = b""
            add(path, original + b"<!-- Cheapskate managed instructions -->\n\n" + content)

        for relative in ("scripts/cheapskate.py", "hooks/rtk.py", "dependencies.json"):
            add(self.active / relative, (self.source / relative).read_bytes(), 0o700 if relative.endswith(".py") else 0o600)
        for filename in ("codex/rtk-guidelines.md", "claude/host-guidelines.md"):
            add(self.active / filename, (self.source / filename).read_bytes())
        add(self.home / ".local/bin/cheapskate",
            (f"#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(self.active / 'scripts/cheapskate.py'))} \"$@\"\n").encode(), 0o700)
        if full:
            tools = {name: path or str(self.state / f"runtime/{name}/{self.manifest[name]['version']}/bin/{name}") for name, path in tools.items()}
            for name in ("rtk", "codegraph", "graphify"):
                if tools.get(name):
                    launcher = self.home / f".local/bin/{name}"
                    if Path(tools[name]).absolute() == launcher:
                        continue
                    add(launcher,
                        (f"#!/bin/sh\nexec {shlex.quote(tools[name])} \"$@\"\n").encode(), 0o700)
            for host in (self.codex, self.claude):
                for name, relative, spec in skill_resources(self.manifest):
                    path = host / f"skills/{name}/{relative}"
                    current = snapshot(path)
                    skill = host / f"skills/{name}/SKILL.md"
                    if skill.exists() and str(skill) not in self.registry["files"]:
                        if current["type"] != "file":
                            if relative == "SKILL.md":
                                raise Conflict(f"Skill existente é symlink: {path}")
                        # Existing skill remains owned by its original installer.
                        continue
                    key = name if relative == "SKILL.md" else f"{name}/{relative}"
                    if skill_data and key in skill_data:
                        add(path, skill_data[key])
                    elif current["type"] == "file":
                        if hashlib.sha256(base64.b64decode(current["data"])).hexdigest() != spec["sha256"]:
                            add(path, f"Atualização verificada prevista: {spec['url']}\n".encode())
                        else:
                            files[str(path)] = current
                    else:
                        add(path, f"Download verificado previsto: {spec['url']}\n".encode())

            for host, path in (("codex", self.codex / "hooks.json"), ("claude", self.claude / "settings.json")):
                command = " ".join(shlex.quote(arg) for arg in
                                   (sys.executable, str(self.active / "hooks/rtk.py"), tools["rtk"], host))
                hook = {"matcher": "^Bash$", "hooks": [{"type": "command", "command": command, "timeout": 10}]}
                config = read_json(path, {})
                existing = hook_entries(config)
                # Migrate recognized RTK hooks; unknown handlers require manual reconciliation.
                compressors = [item for item in existing if any("rtk" in h.get("command", "").lower()
                                for h in item.get("hooks", []))]
                for item in compressors:
                    if item.get("matcher", "") not in ("", "Bash", "^Bash$", ".*") or len(item["hooks"]) != 1:
                        raise Conflict(f"Hook RTK incompatível ou combinado: {path}")
                    tokens = shlex.split(item["hooks"][0]["command"])
                    own = len(tokens) == 4 and tokens[1] == str(self.active / "hooks/rtk.py")
                    native = host == "claude" and tokens == ["rtk", "hook", "claude"]
                    legacy = host == "codex" and len(tokens) == 2 and tokens[1] == str(self.codex / "hooks/rtk-pretooluse.py")
                    if not (own or native or legacy):
                        raise Conflict(f"Hook contendo RTK não reconhecido: {path}")
                existing[:] = [item for item in existing if item not in compressors]
                existing.append(hook)
                add(path, json_bytes(config))

            toml_path = self.codex / "config.toml"
            if toml_path.is_symlink():
                raise Conflict(f"TOML é symlink: {toml_path}")
            text = toml_path.read_text() if toml_path.exists() else ""
            config = tomllib.loads(text)
            if config.get("hooks", {}).get("PreToolUse"):
                raise Conflict("Hooks inline do Codex encontrados. Reconcilie RTK antes de registrar hooks.json.")
            expected = {"command": tools["codegraph"] or "codegraph", "args": ["serve", "--mcp"]}
            server = config.get("mcp_servers", {}).get("codegraph")
            if server is None:
                text += "\n[mcp_servers.codegraph]\ncommand = " + json.dumps(expected["command"]) + '\nargs = ["serve", "--mcp"]\n'
                tomllib.loads(text)
                add(toml_path, text.encode())
            elif server.get("args") != expected["args"] or server.get("command") not in (expected["command"], "codegraph") or server.get("enabled") is False:
                raise Conflict("Servidor CodeGraph existente no Codex difere do contrato validado.")

            path = self.claude / ".claude.json" if "CLAUDE_CONFIG_DIR" in os.environ else self.home / ".claude.json"
            config = read_json(path, {})
            servers = config.setdefault("mcpServers", {})
            if not isinstance(servers, dict):
                raise Conflict("mcpServers precisa ser um objeto")
            server = servers.get("codegraph")
            if server is None:
                servers["codegraph"] = {"type": "stdio", **expected}
                add(path, json_bytes(config))
            elif server.get("args") != expected["args"] or server.get("command") not in (expected["command"], "codegraph"):
                raise Conflict("Servidor CodeGraph existente no Claude difere do contrato validado.")
        return files

    def changes(self, desired):
        self.verify_owned()
        return [{"path": name, "before": snapshot(Path(name)), "after": value}
                for name, value in desired.items() if snapshot(Path(name)) != value]

    def transaction(self, changes, next_registry):
        self.validate_paths(change["path"] for change in changes)
        tx = {"status": "applying", "changes": changes, "previous": self.registry, "next": next_registry}
        atomic_write(self.transaction_path, json_bytes(tx))
        try:
            for change in changes:
                path = Path(change["path"])
                if snapshot(path) != change["before"]:
                    raise Conflict(f"Destino mudou durante aplicação: {path}")
                restore(path, change["after"])
            atomic_write(self.registry_path, json_bytes(next_registry))
            tx["status"] = "committed"
            atomic_write(self.transaction_path, json_bytes(tx))
            self.registry = next_registry
        except BaseException:
            self.recover(tx)
            raise

    def recover(self, tx):
        self.validate_paths(change["path"] for change in tx["changes"])
        self.validate_paths(tx["previous"]["files"])
        for change in tx["changes"]:
            current = snapshot(Path(change["path"]))
            if current not in (change["before"], change["after"]):
                raise Conflict(f"Rollback bloqueado por alteração posterior: {change['path']}")
        for change in reversed(tx["changes"]):
            restore(Path(change["path"]), change["before"])
        atomic_write(self.registry_path, json_bytes(tx["previous"]))
        tx["status"] = "rolled_back"
        atomic_write(self.transaction_path, json_bytes(tx))
        self.registry = tx["previous"]

    def apply(self, desired, full, tools=None):
        changes = self.changes(desired)
        registry = json.loads(json.dumps(self.registry))
        for name, after in desired.items():
            registry["files"][name] = {"original": registry["files"].get(name, {}).get("original", snapshot(Path(name))), "installed": after}
        registry["profile"] = "full" if full else "instructions"
        registry["tools"] = tools or {}
        if changes or registry != self.registry:
            self.transaction(changes, registry)
        return len(changes)

    def uninstall(self):
        self.verify_owned()
        desired = {name: entry["original"] for name, entry in self.registry["files"].items()}
        changes = self.changes(desired)
        if self.registry["files"]:
            self.transaction(changes, {"files": {}, "profile": "instructions"})
        return len(changes)

    def install_dependencies(self, tools):
        runtime = self.state / "runtime"
        for name, path in tools.items():
            if path:
                continue
            spec = self.manifest[name]
            artifact = spec["artifacts"][platform.machine()] if name == "rtk" else spec
            data = download(artifact)
            prefix = runtime / name / spec["version"]
            parent_guard(prefix / "bin/placeholder")
            prefix.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="cheapskate-download-") as temporary:
                tmp = Path(temporary)
                if name == "rtk":
                    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                        members = [member for member in archive.getmembers() if Path(member.name).name == "rtk" and member.isfile()]
                        if len(members) != 1:
                            raise Conflict("Artefato RTK não contém um executável único")
                        binary = archive.extractfile(members[0]).read()
                    atomic_write(prefix / "bin/rtk", binary, 0o700)
                elif name == "codegraph":
                    archive = tmp / "codegraph.tgz"
                    archive.write_bytes(data)
                    subprocess.run(["npm", "install", "--prefix", str(prefix), str(archive)], check=True)
                    prefix.joinpath("bin").mkdir(exist_ok=True)
                    atomic_write(prefix / "bin/codegraph",
                                 (f"#!/bin/sh\nexec {shlex.quote(str(prefix / 'node_modules/.bin/codegraph'))} \"$@\"\n").encode(), 0o700)
                else:
                    wheel = tmp / "graphifyy-0.9.63-py3-none-any.whl"
                    wheel.write_bytes(data)
                    env = {**os.environ, "PIPX_HOME": str(prefix / "pipx"), "PIPX_BIN_DIR": str(prefix / "bin")}
                    subprocess.run(["pipx", "install", str(wheel)], env=env, check=True)
            tools[name] = str(prefix / f"bin/{name}")
            if version(tools[name]) != spec["version"]:
                raise Conflict(f"Versão instalada de {name} não corresponde ao manifesto")
            print(f"Dependência disponível: {name} {spec['version']}. Runtime preservado em {prefix}.")
        return tools

    def prepare_skills(self):
        contents = {}
        for name, relative, spec in skill_resources(self.manifest):
            key = name if relative == "SKILL.md" else f"{name}/{relative}"
            for directory in (self.codex, self.claude):
                skill = directory / f"skills/{name}/SKILL.md"
                if skill.exists() and str(skill) not in self.registry["files"]:
                    continue
                path = directory / f"skills/{name}/{relative}"
                content = path.read_bytes() if path.is_file() else None
                if content and hashlib.sha256(content).hexdigest() == spec["sha256"]:
                    contents[key] = content
                elif key not in contents:
                    contents[key] = download(spec)
        return contents

    def install_team(self):
        spec = self.manifest["team"]
        directory = self.state / "team" / spec["revision"]
        env = {**os.environ, "CODEX_HOME": str(self.codex)}
        parent_guard(self.codex / "config.toml")
        self.codex.mkdir(parents=True, exist_ok=True)

        def query(*args):
            result = subprocess.run(["codex", "plugin", *args, "--json"], env=env,
                                    capture_output=True, text=True, check=False)
            if result.returncode:
                raise Conflict(f"Consulta do plugin falhou: {result.stderr.strip()}")
            return json.loads(result.stdout)

        installed = query("list").get("installed", [])
        existing = [item for item in installed if item.get("pluginId") == "personal-agent-team-codex@agent-team-configurator"]
        if existing:
            if existing[0].get("version") != spec["version"]:
                raise Conflict("Personal Agent Team existente tem versão não validada; preservado.")
            print("Personal Agent Team já instalado; configuração e ativação preservadas.")
            return
        if str(self.codex / "config.toml") in self.registry["files"]:
            raise Conflict("Para adicionar o plugin após uma instalação completa, reconcilie primeiro config.toml. "
                           "A operação externa foi interrompida antes de modificar o arquivo gerenciado.")
        marker = directory / ".cheapskate-complete.json"
        if not directory.exists():
            data = download(spec)
            directory.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="team-staging-", dir=directory.parent) as temporary:
                staging = Path(temporary) / "source"
                hashes = {}
                with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                    for member in archive.getmembers():
                        relative = Path(*Path(member.name).parts[1:])
                        if relative.is_absolute() or ".." in relative.parts or member.issym() or member.islnk():
                            raise Conflict("Caminho inválido no artefato do plugin")
                        destination = staging / relative
                        if member.isfile():
                            content = archive.extractfile(member).read()
                            atomic_write(destination, content, member.mode & 0o700)
                            hashes[str(relative)] = hashlib.sha256(content).hexdigest()
                        elif member.isdir():
                            destination.mkdir(parents=True, exist_ok=True)
                atomic_write(staging / ".cheapskate-complete.json", json_bytes(hashes))
                os.replace(staging, directory)
        if not marker.is_file():
            raise Conflict(f"Snapshot incompleto preservado: {directory}. Use outro snapshot após reconciliar.")
        for name, digest in read_json(marker, {}).items():
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                raise Conflict("Caminho inválido no snapshot do plugin")
            if hashlib.sha256((directory / relative).read_bytes()).hexdigest() != digest:
                raise Conflict("Snapshot do plugin foi alterado")
        manifest = json.loads((directory / "plugins/personal-agent-team-codex/.codex-plugin/plugin.json").read_text())
        if manifest["version"] != spec["version"]:
            raise Conflict("Versão do plugin não corresponde ao manifesto")
        marketplaces = query("marketplace", "list").get("marketplaces", [])
        existing = [item for item in marketplaces if item.get("name") == "agent-team-configurator"]
        if existing and Path(existing[0]["root"]).resolve() != directory.resolve():
            raise Conflict("Marketplace existente usa outra origem; preservado. Reconcilie a origem antes de instalar.")
        effects_path = self.state / "external-effects.json"
        effects = read_json(effects_path, {"completed": []})
        commands = [] if existing else [["codex", "plugin", "marketplace", "add", str(directory)]]
        commands.append(["codex", "plugin", "add", "personal-agent-team-codex@agent-team-configurator"])
        for command in commands:
            effects["pending"] = command
            atomic_write(effects_path, json_bytes(effects))
            try:
                subprocess.run(command, env=env, check=True)
            except subprocess.SubprocessError:
                raise Conflict(f"Instalação externa falhou. Passos concluídos preservados: {effects['completed']}. "
                               f"Consulte {effects_path}; execute novamente para retomar.") from None
            effects["completed"].append(command)
            effects["pending"] = None
            atomic_write(effects_path, json_bytes(effects))
        plugins = query("list").get("installed", [])
        if not any(item.get("pluginId") == "personal-agent-team-codex@agent-team-configurator"
                   and item.get("version") == spec["version"] for item in plugins):
            raise Conflict("Registro externo não confirmou o plugin esperado; efeitos preservados.")
        print("Personal Agent Team instalado. Execute configurar-equipe e revise /hooks no Codex CLI.")


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("install", "update", "check", "audit", "uninstall", "rollback"))
    parser.add_argument("--home", type=Path, default=Path.home(), help="Diretório pessoal alvo, também usado em testes")
    parser.add_argument("--instructions-only", action="store_true", help="Instala somente instruções, sem ferramentas ou hooks")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--with-team", action="store_true", help="Instala o plugin opcional sem configurar agentes")
    args = parser.parse_args()
    if platform.system() != "Darwin":
        raise Conflict("Esta versão suporta macOS; outras plataformas não foram validadas.")
    installer = Installer(args.home)
    if args.with_team and args.command not in ("install", "update"):
        raise Conflict("--with-team só pode ser usado com install/update")
    pending = installer.pending()
    if pending and args.command != "rollback":
        raise Conflict("Transação incompleta detectada. Execute rollback antes de continuar.")
    full = not args.instructions_only
    if args.command == "update":
        full = installer.registry["profile"] == "full"
    elif installer.registry["profile"] == "full" and args.instructions_only and args.command == "install":
        raise Conflict("Perfil completo já instalado; remova antes de trocar para somente instruções")

    if args.command in ("check", "audit"):
        installer.verify_owned()
        print(f"Arquivos íntegros: {len(installer.registry['files'])}; perfil: {installer.registry['profile']}.")
        if not installer.registry["files"]:
            print("Cheapskate ainda não instalado.")
            if args.command == "audit":
                tools = installer.tools() if full else {}
                prospective = installer.changes(installer.desired(full, tools))
                print(f"Diferenças previstas para a fonte atual: {len(prospective)}")
                for change in prospective:
                    print(change["path"])
            return 1
        tools = installer.tools() if installer.registry["profile"] == "full" else {}
        if tools and not all(tools.values()):
            raise Conflict("Dependência da instalação completa está ausente")
        if args.command == "audit":
            desired = installer.desired(bool(tools), tools)
            changed = installer.changes(desired)
            print(f"Divergências da fonte: {len(changed)}")
            if changed:
                return 1
        if tools:
            configured = installer.desired(True, tools)
            if installer.changes(configured):
                raise Conflict("Integração instalada diverge da configuração esperada. Execute audit/update.")
            for directory in (installer.codex, installer.claude):
                for name, relative, spec in skill_resources(installer.manifest):
                    path = directory / f"skills/{name}/{relative}"
                    skill = directory / f"skills/{name}/SKILL.md"
                    if skill.is_file() and str(skill) not in installer.registry["files"] and relative != "SKILL.md":
                        continue
                    if not path.is_file():
                        raise Conflict(f"Skill ausente: {path}")
                    if hashlib.sha256(path.read_bytes()).hexdigest() != spec["sha256"]:
                        print(f"Skill existente preservada, revisão diferente do pin: {path}")
            print("Ferramentas e configuração verificadas. Confiança do hook: não verificada; revise /hooks no Codex CLI.")
        return 0

    tools = {}
    if args.command in ("install", "update"):
        installer.verify_owned()
        if full:
            tools = installer.tools()
            for name, command in (("codegraph", "npm"), ("graphify", "pipx")):
                if not tools[name] and not shutil.which(command):
                    raise Conflict(f"Instale {command} para provisionar {name}.")
        desired = installer.desired(full, tools)
        changes = installer.changes(desired)
    elif args.command == "uninstall":
        installer.verify_owned()
        changes = installer.changes({name: item["original"] for name, item in installer.registry["files"].items()})
    else:
        tx = read_json(installer.transaction_path, {})
        if tx.get("status") not in ("applying", "committed"):
            raise Conflict("Não há transação disponível para rollback")
        changes = tx["changes"]

    print(f"Operação: {args.command}; arquivos previstos: {len(changes)}")
    for change in changes:
        print(change["path"])
    if tools:
        print("Dependências ausentes: " + ", ".join(name for name, path in tools.items() if not path))
        for name, path in tools.items():
            if not path:
                print(f"Download verificado: {name} {installer.manifest[name]['version']}")
                if name == "codegraph":
                    print(f"npm install --prefix {installer.state / 'runtime/codegraph' / installer.manifest[name]['version']} <tarball verificado>")
                elif name == "graphify":
                    print(f"pipx install <wheel verificado>, runtime isolado em {installer.state / 'runtime/graphify' / installer.manifest[name]['version']}")
        print("Skills ausentes serão baixadas com hash fixado. Dependências de npm/pipx permanecem após rollback.")
    if args.with_team:
        if not shutil.which("codex"):
            raise Conflict("Codex CLI necessário para instalar o plugin opcional")
        print(f"Plugin opcional: Personal Agent Team {installer.manifest['team']['version']}, revisão {installer.manifest['team']['revision']}.")
        print("Comandos externos: codex plugin marketplace add <snapshot fixado>; codex plugin add personal-agent-team-codex@agent-team-configurator")
    if args.dry_run:
        return 0
    if not args.yes and input("Aplicar este plano? [s/N] ").lower() != "s":
        print("Operação cancelada.")
        return 0
    installer.state.mkdir(parents=True, exist_ok=True)
    lock_path = installer.state / "lock"
    if lock_path.is_symlink():
        raise Conflict("Lock é symlink")
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Conflict("Outra operação está em execução") from None
        if read_json(installer.registry_path, {"files": {}, "profile": "instructions"}) != installer.registry:
            raise Conflict("A instalação mudou após a prévia. Execute novamente.")
        if args.command != "rollback":
            for change in changes:
                if snapshot(Path(change["path"])) != change["before"]:
                    raise Conflict(f"Destino mudou após a prévia: {change['path']}")
        if args.command == "rollback":
            installer.recover(tx)
        elif args.command == "uninstall":
            installer.uninstall()
        else:
            skill_data = {}
            if full:
                tools = installer.install_dependencies(tools)
                skill_data = installer.prepare_skills()
                for change in changes:
                    if snapshot(Path(change["path"])) != change["before"]:
                        raise Conflict(f"Destino mudou durante provisionamento: {change['path']}")
                desired = installer.desired(True, tools, skill_data)
            if args.with_team:
                installer.install_team()
                # Plugin settings are external effects; take the managed-file snapshot afterwards.
                desired = installer.desired(full, tools, skill_data)
            installer.apply(desired, full, tools)
    print("Operação concluída. Abra novas sessões dos agentes.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Conflict, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Cheapskate: {error}", file=sys.stderr)
        raise SystemExit(1)
