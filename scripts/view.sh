#!/usr/bin/env bash
# Construit (et ouvre) le viewer mémoire (lecture seule) pour le projet courant.
# Usage:
#   view.sh [vault-dir]            génère, affiche le lien, tente l'ouverture
#   view.sh --build-only [vault]   régénère seulement le HTML (pas d'ouverture, pas de lien)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

BUILD_ONLY=0
if [ "${1:-}" = "--build-only" ]; then BUILD_ONLY=1; shift; fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
SLUG="$(sm_slug "$PROJECT_DIR")"

VAULT="${1:-}"
if [ -z "$VAULT" ]; then
  VAULT="$(sm_vault_clone_for_slug "$SLUG" || true)"
fi
if [ -z "$VAULT" ] || [ ! -d "$VAULT" ]; then
  # Fallback : résoudre le symlink du dossier mémoire.
  MEM="$(sm_memory_dir "$PROJECT_DIR")"
  if [ -e "$MEM" ]; then VAULT="$(cd "$MEM" && pwd -P)"; fi
fi
[ -d "$VAULT" ] || { echo "Vault introuvable. Lance d'abord /memory-setup."; exit 1; }

# Mode normal : récupère les faits arrivés entre-temps (best-effort, ne clobbe rien).
if [ "$BUILD_ONLY" = 0 ] && [ -d "$VAULT/.git" ]; then
  git -C "$VAULT" pull --ff-only --quiet 2>/dev/null || true
fi

TMPL="$HERE/../assets/viewer-template.html"
STATE="${TMPDIR:-/tmp}/shared-memory-serve-$SLUG.port"

# Le serveur lit le vault à chaque requête : rien à « régénérer », recharger l'onglet suffit.
if [ "$BUILD_ONLY" = 1 ]; then
  echo "Viewer servi : recharge l'onglet (F5) pour voir les changements."
  exit 0
fi

alive() { [ -f "$STATE" ] && kill -0 "$(cut -d: -f1 "$STATE" 2>/dev/null)" 2>/dev/null; }

# Réutilise un serveur déjà lancé pour ce vault, sinon en démarre un (port libre choisi par l'OS).
if ! alive; then
  PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
  nohup python3 "$HERE/serve-viewer.py" "$VAULT" "$TMPL" "$PORT" >/dev/null 2>&1 &
  echo "$!:$PORT" > "$STATE"
  sleep 1
fi
PORT="$(cut -d: -f2 "$STATE")"

echo "Vault : $VAULT"
echo "LIEN À COMMUNIQUER (clique pour ouvrir) : http://127.0.0.1:$PORT/"
