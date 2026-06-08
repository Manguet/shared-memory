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

command -v gh >/dev/null 2>&1 \
  && ok "gh (GitHub CLI)" \
  || opt "gh absent — requis seulement pour /memory-promote et /memory-review"

# WSL2 : ouverture du navigateur
if grep -qi microsoft /proc/version 2>/dev/null; then
  command -v wslview >/dev/null 2>&1 \
    && ok "wslview (wslu) — ouverture navigateur WSL2" \
    || opt "wslview absent — 'sudo apt install wslu' pour /memory-ui (sinon ouverture manuelle)"
fi

# Auth GitHub (best effort)
if command -v ssh >/dev/null 2>&1 \
   && ssh -T git@github.com -o StrictHostKeyChecking=accept-new 2>&1 | grep -qi 'successfully authenticated'; then
  ok "GitHub SSH authentifié"
elif command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  ok "GitHub authentifié via gh"
else
  opt "Auth GitHub non détectée — fais 'gh auth login' (le plus simple) pour cloner les repos privés"
fi

echo
[ "$MISS" = 0 ] && echo "→ Prêt à installer." || { echo "→ Corrige les éléments en erreur ci-dessus avant de continuer."; exit 1; }
