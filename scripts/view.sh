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

OUT="/tmp/shared-memory-view-$SLUG.html"
python3 "$HERE/build-viewer.py" "$VAULT" "$OUT" "$HERE/../assets/viewer-template.html" >/dev/null

# Mode régénération silencieuse (appelé après une mutation pour rafraîchir une vue ouverte).
if [ "$BUILD_ONLY" = 1 ]; then
  echo "Viewer régénéré : $OUT"
  exit 0
fi

URL="$(sm_fileurl "$OUT")"
echo "Vault : $VAULT"
printf 'LIEN À COMMUNIQUER (clique pour ouvrir) : '
sm_hyperlink "$URL" "$URL"
# Aucune ouverture automatique : sous WSL2 elle produit des liens cassés. L'utilisateur clique.
