#!/usr/bin/env bash
# Désinstallation machine de shared-memory : débranche tous les projets, retire le plugin et les
# caches. GARDE les clones de vault (données) sauf --purge.
# Usage: uninstall.sh [--purge] [--yes]
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh" 2>/dev/null || exit 1
set +e +u +o pipefail

# Garde-fou : $HOME doit être défini et ≠ racine, sinon les chemins collapsent vers /.shared-memory.
case "${HOME:-}" in
  ""|"/") echo "HOME non défini ou racine — abandon (chemins non fiables)." >&2; exit 1 ;;
esac

SM_ROOT="$HOME/.shared-memory"
PLUGIN_DIR="${SHARED_MEMORY_HOME:-$SM_ROOT/plugin}"

# Garde-fou : ne jamais rm -rf un chemin vide, la racine, ou $HOME lui-même.
case "$PLUGIN_DIR" in
  ""|"/"|"$HOME"|"$HOME/") echo "PLUGIN_DIR douteux ($PLUGIN_DIR) — abandon." >&2; exit 1 ;;
esac

PURGE=0; YES=0
for a in "$@"; do
  case "$a" in
    --purge) PURGE=1 ;;
    --yes)   YES=1 ;;
  esac
done

echo "Désinstallation shared-memory."
echo "  Plugin : $PLUGIN_DIR"
if [ "$PURGE" = 1 ]; then
  echo "  ⚠ --purge : les clones de vault ($SM_ROOT/vaults) seront SUPPRIMÉS"
  echo "    (y compris d'éventuels brouillons NON promus)."
else
  echo "  Clones de vault conservés sous $SM_ROOT/vaults."
fi

if [ "$YES" != 1 ]; then
  if [ ! -t 0 ]; then
    echo "Stdin n'est pas un terminal — relance avec --yes pour confirmer." >&2
    exit 1
  fi
  printf "Confirmer ? tape 'oui' : "
  read -r ans
  [ "$ans" = "oui" ] || { echo "Annulé."; exit 0; }
fi

# 1. Débrancher tous les projets enregistrés (retirer le symlink si c'en est un).
while IFS= read -r slug; do
  [ -n "$slug" ] || continue
  sym="$(sm_symlink_for_slug "$slug" 2>/dev/null)"
  if [ -n "$sym" ] && [ -L "$sym" ]; then
    rm "$sym" && echo "  symlink retiré : $sym"
  fi
  sm_unregister "$slug"
done < <(sm_registry_slugs)
echo "  projets débranchés."

# 2. Retirer le plugin + caches.
cd "$HOME" 2>/dev/null
rm -rf "$PLUGIN_DIR" && echo "  plugin retiré : $PLUGIN_DIR"
rm -rf "$SM_ROOT/models" "$SM_ROOT/embeddings" && echo "  caches retirés."

# 3. Purge éventuelle (données).
if [ "$PURGE" = 1 ]; then
  rm -rf "$SM_ROOT/vaults" && echo "  clones de vault supprimés."
  rm -f "$SM_REGISTRY"
  rmdir "$SM_ROOT" 2>/dev/null
  echo "  purge complète."
fi

cat <<EOF

Pour finir, dans Claude Code :
  /plugin uninstall shared-memory
  /plugin marketplace remove $PLUGIN_DIR
EOF
exit 0
