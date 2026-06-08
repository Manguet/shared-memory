#!/usr/bin/env bash
# Helpers communs aux skills shared-memory.
set -euo pipefail

SM_CONFIG_DIR="${SM_CONFIG_DIR:-$HOME/.config/shared-memory}"
SM_REGISTRY="${SM_REGISTRY:-$SM_CONFIG_DIR/registry.json}"

# Slug projet, tel que dérivé par Claude Code (runs non-alphanumériques -> '-').
# Ex: /var/www/newnegocian-workspace -> -var-www-newnegocian-workspace
sm_slug() {
  local dir="${1:-$PWD}"
  printf '%s' "$dir" | sed -E 's#[^a-zA-Z0-9]+#-#g'
}

# Dossier mémoire natif de Claude Code pour un projet donné.
sm_memory_dir() {
  local slug
  slug="$(sm_slug "${1:-$PWD}")"
  printf '%s' "$HOME/.claude/projects/$slug/memory"
}

# Ouvre une URL ou un fichier dans le navigateur (mac, WSL2, Linux).
sm_open() {
  local target="$1"
  if command -v wslview >/dev/null 2>&1; then
    wslview "$target"
  elif command -v open >/dev/null 2>&1; then
    open "$target"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$target"
  else
    echo "Ouvre manuellement dans ton navigateur : $target"
  fi
}

# Chemin du clone (vault) pour un slug, lu depuis le registre local.
sm_vault_clone_for_slug() {
  local slug="$1"
  [ -f "$SM_REGISTRY" ] || return 1
  python3 - "$SM_REGISTRY" "$slug" <<'PY'
import json, sys
try:
    reg = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(1)
slug = sys.argv[2]
for p in reg.get("projets", []):
    if p.get("slug") == slug:
        print(p.get("clone", ""))
        break
PY
}
