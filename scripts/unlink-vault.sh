#!/usr/bin/env bash
# Débranche la mémoire native du projet courant : retire le symlink + l'entrée de registre.
# GARDE le clone du vault (données). Usage: unlink-vault.sh [project-dir]
# BEST-EFFORT : ne supprime jamais une vraie mémoire locale (uniquement un symlink).
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh" 2>/dev/null || exit 0
set +e +u +o pipefail

PROJECT_DIR="${1:-${CLAUDE_PROJECT_DIR:-$PWD}}"
SLUG="$(sm_slug "$PROJECT_DIR")"

clone="$(sm_vault_clone_for_slug "$SLUG" 2>/dev/null)"
sym="$(sm_symlink_for_slug "$SLUG" 2>/dev/null)"

if [ -z "$clone" ] && [ -z "$sym" ]; then
  echo "Projet non branché (slug: $SLUG) — rien à débrancher."
  exit 0
fi

if [ -n "$sym" ] && [ -L "$sym" ]; then
  rm "$sym"
  echo "Symlink mémoire retiré : $sym"
elif [ -n "$sym" ] && [ -e "$sym" ]; then
  echo "Attention : $sym est un vrai dossier (pas un symlink) — laissé intact."
fi

sm_unregister "$SLUG"
echo "Entrée de registre retirée (slug: $SLUG)."
[ -n "$clone" ] && echo "Clone du vault conservé : $clone"
echo "Pour re-brancher : /memory-setup <url-du-vault>."
exit 0
