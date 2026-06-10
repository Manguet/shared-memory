#!/usr/bin/env bash
# Hook mémoire shared-memory : synchro au démarrage + rappel de promotion.
# Usage : hook-memory.sh start|end
# BEST-EFFORT : ne bloque jamais la session, silencieux en cas d'échec, sort toujours 0.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$HERE/lib.sh" 2>/dev/null || exit 0
set +e +u +o pipefail            # relâche le set -euo de lib.sh : un hook ne doit jamais aborter

MODE="${1:-start}"

clone="$(sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")" 2>/dev/null)"
[ -n "$clone" ] && [ -d "$clone" ] || exit 0

ahead=0
if [ "$MODE" = "start" ]; then
  GIT_TERMINAL_PROMPT=0 timeout 5 git -C "$clone" pull --ff-only >/dev/null 2>&1 || true   # non destructif, sans prompt TTY
  ahead="$(git -C "$clone" rev-list --count HEAD..origin/main 2>/dev/null || printf 0)"
fi

unpromoted="$(sm_count_unpromoted "$clone")"

msg=""
if [ "$MODE" = "start" ]; then
  [ "${ahead:-0}" -gt 0 ] 2>/dev/null && msg+="📥 ${ahead} nouveau(x) fait(s) d'équipe en amont à récupérer. "
  [ "${unpromoted:-0}" -gt 0 ] 2>/dev/null && msg+="📝 ${unpromoted} fait(s) local(aux) non promu(s) — prévois /memory-promote AVANT de fermer pour éviter les décalages."
else
  [ "${unpromoted:-0}" -gt 0 ] 2>/dev/null && msg+="📝 Avant de partir : ${unpromoted} fait(s) local(aux) non promu(s) — lance /memory-promote pour les partager."
fi

[ -n "$msg" ] && printf '%s\n' "$msg"
exit 0
