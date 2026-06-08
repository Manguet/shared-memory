#!/usr/bin/env bash
# Vérifie les prérequis de shared-memory. N'écrit rien, ne modifie rien.
# Usage: bash scripts/doctor.sh
set -uo pipefail

MISS=0
ok() { printf '  \033[32mOK\033[0m %s\n' "$1"; }
ko() { printf '  \033[31mX\033[0m %s\n' "$1"; MISS=1; }
opt() { printf '  \033[33m~\033[0m %s\n' "$1"; }

echo "Prérequis shared-memory :"

command -v git >/dev/null 2>&1 \
  && ok "git ($(git --version | awk '{print $3}'))" \
  || ko "git manquant — indispensable"

command -v python3 >/dev/null 2>&1 \
  && ok "python3 ($(python3 --version 2>&1 | awk '{print $2}'))" \
  || ko "python3 manquant — indispensable (viewer + registre)"

# Auth GitHub — vérif locale, NON interactive (aucun appel réseau, aucune passphrase demandée).
# Le plugin est public (pas besoin d'auth) ; ceci ne concerne que le clone des VAULTS privés.
if ls "$HOME"/.ssh/id_* >/dev/null 2>&1; then
  opt "Clé SSH présente — ajoute-la à GitHub (et 'ssh-add' si passphrase) pour cloner les vaults privés"
elif git config --get credential.helper >/dev/null 2>&1; then
  opt "Credential helper git configuré (HTTPS+token) — ok pour les vaults privés"
else
  opt "Auth git non configurée — clé SSH ajoutée à GitHub, ou token HTTPS (voir INSTALL.md), pour les vaults privés"
fi

echo
[ "$MISS" = 0 ] && echo "→ Prêt à installer." || { echo "→ Corrige les éléments en erreur ci-dessus avant de continuer."; exit 1; }
