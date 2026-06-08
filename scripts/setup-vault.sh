#!/usr/bin/env bash
# Branche la mémoire native du projet courant sur un vault git partagé.
# Usage: setup-vault.sh <vault-git-url> [clone-path] [project-dir]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

VAULT_URL="${1:?URL du vault git requise (ex: git@github.com:Manguet/negocian-memory.git)}"
PROJECT_DIR="${3:-${CLAUDE_PROJECT_DIR:-$PWD}}"
SLUG="$(sm_slug "$PROJECT_DIR")"
DEFAULT_CLONE="$HOME/.shared-memory/vaults/$(basename "${VAULT_URL%.git}")"
CLONE_PATH="${2:-$DEFAULT_CLONE}"
MEMORY_DIR="$(sm_memory_dir "$PROJECT_DIR")"

echo "Projet   : $PROJECT_DIR"
echo "Slug     : $SLUG"
echo "Vault    : $VAULT_URL"
echo "Clone    : $CLONE_PATH"
echo "Mémoire  : $MEMORY_DIR"
echo

# 1. Cloner le vault (ou pull s'il existe déjà).
if [ -d "$CLONE_PATH/.git" ]; then
  echo "Vault déjà cloné — pull…"
  git -C "$CLONE_PATH" pull --ff-only || echo "Attention : pull non fast-forward : à régler manuellement"
else
  mkdir -p "$(dirname "$CLONE_PATH")"
  git clone "$VAULT_URL" "$CLONE_PATH"
fi

# 2. Préparer le parent du dossier mémoire.
mkdir -p "$(dirname "$MEMORY_DIR")"

# 3. Gérer un dossier mémoire existant (ne jamais détruire une mémoire locale).
if [ -L "$MEMORY_DIR" ]; then
  echo "Symlink déjà présent — remplacement."
  rm "$MEMORY_DIR"
elif [ -d "$MEMORY_DIR" ]; then
  BACKUP="$MEMORY_DIR.local-backup-$(date +%Y%m%d-%H%M%S)"
  echo "Attention : Mémoire locale existante → sauvegarde dans : $BACKUP"
  mv "$MEMORY_DIR" "$BACKUP"
  echo "  (Promeus manuellement les faits utiles de cette sauvegarde via /memory-promote.)"
fi

# 4. Créer le symlink mémoire -> clone du vault.
ln -s "$CLONE_PATH" "$MEMORY_DIR"
echo "Symlink créé : $MEMORY_DIR → $CLONE_PATH"

# 5. Enregistrer dans le registre local (JSON, par-machine).
mkdir -p "$SM_CONFIG_DIR"
python3 - "$SM_REGISTRY" "$SLUG" "$PROJECT_DIR" "$VAULT_URL" "$CLONE_PATH" "$MEMORY_DIR" <<'PY'
import json, os, sys
path, slug, proj, vault, clone, symlink = sys.argv[1:7]
reg = {"projets": []}
if os.path.exists(path):
    try:
        reg = json.load(open(path))
    except Exception:
        pass
reg.setdefault("projets", [])
reg["projets"] = [p for p in reg["projets"] if p.get("slug") != slug]
reg["projets"].append({
    "slug": slug, "project_dir": proj, "vault": vault,
    "clone": clone, "symlink": symlink,
})
json.dump(reg, open(path, "w"), indent=2, ensure_ascii=False)
print("Registre mis à jour :", path)
PY

echo
echo "Terminé. La mémoire de ce projet est désormais partagée via le vault."
