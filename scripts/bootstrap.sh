#!/bin/bash
# Prepare a macOS terminal before running the Python installer.
set -euo pipefail
umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
dry_run=0
if [[ ${1:-} == --dry-run && $# == 1 ]]; then
  dry_run=1
elif [[ $# != 0 ]]; then
  echo "Uso: bash scripts/bootstrap.sh [--dry-run]" >&2
  exit 2
fi

fail() {
  echo "Cheapskate: $1" >&2
  echo "Corrija a etapa e execute novamente: bash scripts/bootstrap.sh" >&2
  exit 1
}

[[ $(uname -s) == Darwin ]] || fail "Este assistente suporta macOS."
case ${SHELL##*/} in
  zsh) profile="$HOME/.zprofile" ;;
  bash) profile="$HOME/.bash_profile" ;;
  fish) profile="$HOME/.config/fish/config.fish" ;;
  *) fail "Shell não suportado para configurar o PATH: ${SHELL:-desconhecido}." ;;
esac
[[ ! -L $profile ]] || fail "Perfil de shell é symlink: $profile"
[[ ! -L ${profile%/*} ]] || fail "Diretório do perfil de shell é symlink: ${profile%/*}"
PATH="$HOME/.local/bin:$PATH"
export PATH

arch=$(uname -m)
case $arch in
  arm64) default_brew="/opt/homebrew/bin/brew" ;;
  x86_64) default_brew="/usr/local/bin/brew" ;;
  *) fail "Arquitetura macOS não suportada: $arch" ;;
esac

brew=$(command -v brew || true)
if [[ -z $brew && -x $default_brew ]]; then
  brew=$default_brew
fi
if [[ -n $brew ]]; then
  PATH="${brew%/bin/brew}/bin:$PATH"
  export PATH
fi

find_python() {
  local name path
  for name in python3 python3.15 python3.14 python3.13 python3.12 python3.11; do
    path=$(command -v "$name" || true)
    if [[ -n $path ]] && "$path" -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
      printf '%s' "$path"
      return 0
    fi
  done
  return 1
}

python=$(find_python || true)
need_python=0; need_node=0; need_pipx=0; need_codex=0; need_claude=0
[[ -n $python ]] || need_python=1
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then need_node=1; fi
command -v pipx >/dev/null 2>&1 || need_pipx=1
command -v codex >/dev/null 2>&1 || need_codex=1
command -v claude >/dev/null 2>&1 || need_claude=1
need_brew=0
if [[ -z $brew && $((need_python + need_node + need_pipx + need_codex + need_claude)) -gt 0 ]]; then
  need_brew=1
fi

echo "Plano de preparação do Cheapskate:"
if (( need_brew )); then
  echo "  Instalar Homebrew pelo instalador oficial: https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"
else
  echo "  Homebrew: $([[ -n $brew ]] && echo presente || echo desnecessário)"
fi
(( need_python )) && echo "  brew install python@3.11" || echo "  Python 3.11+: presente ($python)"
(( need_node )) && echo "  brew install node (Node.js e npm)" || echo "  Node.js e npm: presentes"
(( need_pipx )) && echo "  brew install pipx" || echo "  pipx: presente"
(( need_codex )) && echo "  brew install --cask codex" || echo "  Codex CLI: presente"
(( need_claude )) && echo "  brew install --cask claude-code" || echo "  Claude Code: presente"
echo "  Configurar PATH em $profile se necessário."
echo "  Verificar login de Codex e Claude; oferecer login opcional, sem bloquear a instalação."
echo "  Mostrar prévia do instalador Cheapskate, pedir confirmação e executar check."
echo "Homebrew, pacotes, perfil de shell e login persistem após rollback/uninstall do Cheapskate."
if (( dry_run )); then exit 0; fi

read -r -p "Aplicar a preparação? [s/N] " answer || fail "Confirmação não recebida."
if [[ $answer != s ]]; then
  echo "Preparação cancelada."
  exit 0
fi

if (( need_brew )); then
  command -v curl >/dev/null 2>&1 || fail "curl é necessário para instalar Homebrew."
  temporary=$(mktemp "${TMPDIR:-/tmp}/cheapskate-brew.XXXXXX") || fail "Não foi possível criar arquivo temporário."
  trap 'rm -f "$temporary"' EXIT
  curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$temporary" || fail "Download do instalador Homebrew falhou."
  /bin/bash "$temporary" || fail "Instalação do Homebrew falhou."
  brew=$default_brew
  [[ -x $brew ]] || fail "Homebrew instalado, mas não encontrado em $brew."
  PATH="${brew%/bin/brew}/bin:$PATH"
  export PATH
fi

if (( need_python )); then
  "$brew" install python@3.11 || fail "Instalação do Python falhou."
  python=$(find_python || true)
  [[ -n $python ]] || fail "Python 3.11+ não foi encontrado após a instalação."
fi
if (( need_node )); then
  "$brew" install node || fail "Instalação do Node.js falhou."
  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    fail "Node.js/npm não foram encontrados após a instalação."
  fi
fi
if (( need_pipx )); then
  "$brew" install pipx || fail "Instalação do pipx falhou."
  command -v pipx >/dev/null 2>&1 || fail "pipx não foi encontrado após a instalação."
fi
if (( need_codex )); then
  "$brew" install --cask codex || fail "Instalação do Codex CLI falhou."
  command -v codex >/dev/null 2>&1 || fail "Codex CLI não foi encontrado após a instalação."
fi
if (( need_claude )); then
  "$brew" install --cask claude-code || fail "Instalação do Claude Code falhou."
  command -v claude >/dev/null 2>&1 || fail "Claude Code não foi encontrado após a instalação."
fi

marker="# Cheapskate bootstrap PATH"
if [[ ! -f $profile ]] || ! grep -Fqx "$marker" "$profile"; then
  mkdir -p "${profile%/*}" || fail "Não foi possível criar o diretório do perfil."
  brew_profile=${brew:-$default_brew}
  {
    printf '\n%s\n' "$marker"
    # These variables must expand when the user's shell loads the profile.
    # shellcheck disable=SC2016
    if [[ ${SHELL##*/} == fish ]]; then
      printf 'if test -x "%s"; eval ("%s" shellenv fish); end\n' "$brew_profile" "$brew_profile"
      printf 'fish_add_path "$HOME/.local/bin"\n'
    else
      printf 'if [ -x "%s" ]; then eval "$(%s shellenv)"; fi\n' "$brew_profile" "$brew_profile"
      printf 'export PATH="$HOME/.local/bin:$PATH"\n'
    fi
  } >> "$profile" || fail "Não foi possível configurar $profile."
fi
if ! codex login status >/dev/null 2>&1; then
  answer=""
  read -r -p "Codex: deseja entrar agora? Sem conta, pode pular. [s/N] " answer || true
  if [[ $answer == s ]]; then
    if ! codex login; then
      echo "Aviso: Login do Codex não foi concluído. A instalação continuará."
    elif ! codex login status >/dev/null 2>&1; then
      echo "Aviso: Login do Codex não foi confirmado. A instalação continuará."
    fi
  fi
  if ! codex login status >/dev/null 2>&1; then
    echo "Codex: autenticação pendente. Para entrar depois: codex login"
  fi
fi
if ! claude auth status >/dev/null 2>&1; then
  answer=""
  read -r -p "Claude Code: deseja entrar agora? Sem conta, pode pular. [s/N] " answer || true
  if [[ $answer == s ]]; then
    if ! claude auth login; then
      echo "Aviso: Login do Claude Code não foi concluído. A instalação continuará."
    elif ! claude auth status >/dev/null 2>&1; then
      echo "Aviso: Login do Claude Code não foi confirmado. A instalação continuará."
    fi
  fi
  if ! claude auth status >/dev/null 2>&1; then
    echo "Claude Code: autenticação pendente. Para entrar depois: claude auth login"
  fi
fi

"$python" "$root/scripts/cheapskate.py" install --dry-run || fail "Prévia do instalador Cheapskate falhou."
"$python" "$root/scripts/cheapskate.py" install || fail "Instalação do Cheapskate falhou."
"$python" "$root/scripts/cheapskate.py" check || fail "Verificação do Cheapskate falhou."
echo "Preparação concluída. Abra um novo terminal para carregar o PATH."
