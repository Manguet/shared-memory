#!/usr/bin/env bash
# Installateur shared-memory (plugin public).
# Vérifie les prérequis, clone/maj le plugin localement, et affiche les commandes
# d'activation à coller dans Claude Code. L'installation reste 100 % locale :
# le plugin n'est publié dans aucun catalogue.
#
# Usage local  : bash install.sh
# Usage distant: curl -fsSL https://raw.githubusercontent.com/Manguet/shared-memory/main/install.sh | bash
set -uo pipefail

REPO_URL="${SHARED_MEMORY_REPO:-https://github.com/Manguet/shared-memory.git}"
DEST="${SHARED_MEMORY_HOME:-$HOME/.shared-memory/plugin}"

echo "== Installation shared-memory =="

# 1. Prérequis indispensables
for bin in git python3; do
  command -v "$bin" >/dev/null 2>&1 || { echo "  X  $bin manquant (indispensable) — installe-le puis relance."; exit 1; }
done
echo "  OK git, python3"
if grep -qi microsoft /proc/version 2>/dev/null; then
  command -v wslview >/dev/null 2>&1 || echo "  ~  wslview absent (sudo apt install wslu, pour /memory-ui)"
fi

# 2. Cloner ou mettre à jour le plugin
if [ -d "$DEST/.git" ]; then
  echo "  Mise à jour du plugin dans $DEST"
  git -C "$DEST" pull --ff-only || { echo "  X  pull impossible (modifs locales ?)"; exit 1; }
else
  mkdir -p "$(dirname "$DEST")"
  git clone "$REPO_URL" "$DEST" || { echo "  X  clone impossible (repo accessible ?)"; exit 1; }
fi
echo "  OK plugin dans $DEST"

# 3. Activation (à faire dans Claude Code — un script ne peut pas lancer les commandes /plugin)
cat <<EOF

Plugin prêt. Pour l'activer, dans Claude Code, colle :

  /plugin marketplace add $DEST
  /plugin install shared-memory

Puis, dans un projet déjà ouvert dans Claude Code :

  /memory-setup <url-du-vault>

(Installation locale : rien n'est publié dans un catalogue public.)
EOF
