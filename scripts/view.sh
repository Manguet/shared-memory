#!/usr/bin/env bash
# Construit et ouvre le viewer mémoire (lecture seule) pour le projet courant.
# Usage: view.sh [vault-dir]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

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

OUT="/tmp/shared-memory-view-$SLUG.html"
python3 "$HERE/build-viewer.py" "$VAULT" "$OUT" "$HERE/../assets/viewer-template.html" >/dev/null
URL="$(sm_fileurl "$OUT")"
echo "Vault : $VAULT"
printf 'Mémoire (clique pour ouvrir) : '
sm_hyperlink "$URL" "$URL"
# Tente aussi l'ouverture automatique si un ouvreur est dispo (bonus, silencieux sinon).
sm_open "$OUT" 2>/dev/null || true
