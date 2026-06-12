#!/usr/bin/env bash
# Hook mémoire shared-memory : synchro au démarrage + rappel visible + rappel de promotion.
# Usage : hook-memory.sh start|end
# BEST-EFFORT : ne bloque jamais la session, silencieux en cas d'échec, sort toujours 0.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$HERE/lib.sh" 2>/dev/null || exit 0
set +e +u +o pipefail            # relâche le set -euo de lib.sh : un hook ne doit jamais aborter

MODE="${1:-start}"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"

clone="$(sm_vault_clone_for_slug "$(sm_slug "$PROJECT_DIR")" 2>/dev/null)"
[ -n "$clone" ] && [ -d "$clone" ] || exit 0

unpromoted="$(sm_count_unpromoted "$clone")"

# ---------- SessionEnd : dernier rappel de promotion (inchangé) ----------
if [ "$MODE" = "end" ]; then
  [ "${unpromoted:-0}" -gt 0 ] 2>/dev/null && \
    printf '%s\n' "📝 Avant de partir : ${unpromoted} fait(s) local(aux) non promu(s) — lance /memory-promote pour les partager."
  exit 0
fi

# ---------- SessionStart : synchro + rappel visible ----------
pull_failed=0
has_remote=0
ahead=0
if git -C "$clone" remote get-url origin >/dev/null 2>&1; then     # ne pull / compte l'amont QUE si un remote existe
  has_remote=1
  GIT_TERMINAL_PROMPT=0 timeout 5 git -C "$clone" pull --ff-only >/dev/null 2>&1 || pull_failed=1
  ahead="$(git -C "$clone" rev-list --count HEAD..origin/HEAD 2>/dev/null || printf 0)"
fi

summary="$(timeout 5 python3 "$HERE/digest.py" --summary "$clone" 2>/dev/null)"
digest="$(timeout 5 python3 "$HERE/digest.py" "$clone" 2>/dev/null)"
issues="$(sm_health_issues "$clone" "$PROJECT_DIR" "$pull_failed" 2>/dev/null)"

# Rappel compact (ce que l'utilisateur verra).
recall=""
[ -n "$summary" ] && recall+="🧠 Mémoire d'équipe — ${summary}"$'\n'
status="📝 ${unpromoted:-0} non promu"
[ "$has_remote" = "1" ] && status="📥 ${ahead:-0} à récupérer · ${status}"   # « à récupérer » n'a de sens qu'avec un remote
recall+="$status"
[ "${unpromoted:-0}" -gt 0 ] 2>/dev/null && \
  recall+=" — pense à /memory-promote avant de fermer."
[ -n "$issues" ] && recall+=$'\n'"⚠ souci de configuration détecté → lance /doctor"

# Instruction au modèle : afficher le rappel à l'utilisateur, puis le digest en contexte silencieux.
printf '%s\n' "[shared-memory] Au début de ta toute première réponse de cette session, affiche tel quel à l'utilisateur le rappel ci-dessous, puis réponds normalement :"
printf '%s\n' "$recall"

if [ -n "$digest" ]; then
  printf '\n%s\n' "<!-- Contexte mémoire d'équipe (pour ton usage : ne le réaffiche pas, il est déjà résumé ci-dessus) -->"
  printf '%s\n' "$digest"
fi
exit 0
