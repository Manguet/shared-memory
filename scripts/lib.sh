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

# Ouvre une URL ou un fichier dans le navigateur (mac, WSL2, Linux). Silencieux si aucun
# ouvreur n'est dispo (renvoie 1) — l'appelant affiche alors un lien cliquable.
sm_open() {
  local target="$1"
  if grep -qi microsoft /proc/version 2>/dev/null; then
    # WSL2 : seul wslview ouvre le navigateur Windows ; xdg-open n'aide pas.
    command -v wslview >/dev/null 2>&1 && { wslview "$target"; return; }
    return 1
  fi
  if command -v open >/dev/null 2>&1; then
    open "$target"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$target"
  else
    return 1
  fi
}

# Construit une URL file:// cliquable pour un fichier local (convertit le chemin sous WSL2).
sm_fileurl() {
  local f="$1" w
  if grep -qi microsoft /proc/version 2>/dev/null && command -v wslpath >/dev/null 2>&1; then
    w="$(wslpath -w "$f" 2>/dev/null)"
    if [ -n "$w" ]; then
      w="${w//\\//}"                       # backslashes -> slashes
      case "$w" in
        //*) printf 'file:%s' "$w" ;;      # UNC \\wsl.localhost\... -> file://wsl.localhost/...
        *)   printf 'file:///%s' "$w" ;;   # C:\... -> file:///C:/...
      esac
      return
    fi
  fi
  printf 'file://%s' "$f"
}

# Affiche un lien cliquable (séquence OSC 8) ; les terminaux qui ne la gèrent pas montrent l'URL.
sm_hyperlink() {
  local url="$1" label="${2:-$1}"
  printf '\033]8;;%s\033\\%s\033]8;;\033\\\n' "$url" "$label"
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

# Compte les faits .md partageables modifiés/ajoutés/supprimés dans la working copy d'un clone
# (modifs NON COMMITÉES = brouillons étage 1), hors MEMORY.md, index/**, et faits perso
# (feedback_* ou frontmatter type: user|feedback). Renvoie un entier sur stdout. Best-effort : 0 si
# pas un dépôt git. Utilise `status --porcelain -z` (NUL-séparé, SANS quoting) pour gérer
# correctement les noms accentués / avec espaces / les renommages.
sm_count_unpromoted() {
  local clone="$1" n=0 rec st path type _old
  [ -d "$clone" ] || { printf '0'; return 0; }
  while IFS= read -r -d '' rec; do
    st="${rec:0:2}"
    path="${rec:3}"
    case "$st" in R*|C*|*R*|*C*) IFS= read -r -d '' _old ;; esac   # renommage/copie : consomme l'ancien chemin
    case "$path" in *.md) ;; *) continue ;; esac
    case "$path" in
      MEMORY.md|index/*) continue ;;
      feedback_*|*/feedback_*) continue ;;
    esac
    type="$(sed -n 's/^[[:space:]]*type:[[:space:]]*//p' "$clone/$path" 2>/dev/null | head -1)"
    case "$type" in user|feedback) continue ;; esac
    n=$((n + 1))
  done < <(git -C "$clone" status --porcelain -z 2>/dev/null)
  printf '%s' "$n"
}
