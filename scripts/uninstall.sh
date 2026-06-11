#!/usr/bin/env bash
# Désinstallation machine de shared-memory : débranche tous les projets, retire le plugin et les
# caches. GARDE les clones de vault (données) sauf --purge.
# Usage: uninstall.sh [--purge] [--yes]
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh" 2>/dev/null || exit 1
set +e +u +o pipefail

SM_ROOT="$HOME/.shared-memory"
PLUGIN_DIR="${SHARED_MEMORY_HOME:-$SM_ROOT/plugin}"
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
  printf "Confirmer ? tape 'oui' : "
  read -r ans
  [ "$ans" = "oui" ] || { echo "Annulé."; exit 0; }
fi

# 1. Débrancher tous les projets enregistrés (retirer le symlink si c'en est un).
for slug in $(sm_registry_slugs); do
  sym="$(sm_symlink_for_slug "$slug" 2>/dev/null)"
  if [ -n "$sym" ] && [ -L "$sym" ]; then
    rm "$sym" && echo "  symlink retiré : $sym"
  fi
  sm_unregister "$slug"
done
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
