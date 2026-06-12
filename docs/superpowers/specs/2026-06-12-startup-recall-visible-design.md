# Design — Rappel mémoire visible + nudge santé au démarrage

**Date :** 2026-06-12
**Statut :** Design validé, prêt pour le plan
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Origine :** retour d'usage réel — le hook `SessionStart` produit déjà un digest mémoire, mais
l'utilisateur ne le voit pas au démarrage (rien d'affiché dans le terminal). Il veut un **rappel
visuel** à l'ouverture, et que tout souci de configuration nécessitant `/doctor` soit aussi signalé
dès le démarrage.

## Contrainte technique décisive

Vérifiée sur la doc officielle des hooks Claude Code (https://code.claude.com/docs/en/hooks.md,
section SessionStart) : **un hook `SessionStart` ne peut pas imprimer un bandeau visible dans le
terminal.** Sa sortie stdout (et `hookSpecificOutput.additionalContext`) est **uniquement injectée
dans le contexte du modèle**, pas affichée à l'utilisateur. La seule voie fiable pour rendre un
contenu visible : **formuler la sortie comme une instruction** demandant à Claude d'afficher le
rappel — Claude le ressort alors dans sa **première réponse**.

Conséquence : le rappel apparaît comme **le premier message de Claude** au début de la session, pas
comme un bandeau pré-prompt. C'est le maximum atteignable côté Claude Code.

Le bandeau natif « ⚠ N setup issues: MCP » est affiché **par Claude Code lui-même** (approbation MCP,
etc.) ; notre hook ne peut pas lire ce compteur. Le nudge `/doctor` du plugin repose donc sur **nos
propres vérifications**, distinctes du check natif.

## Décisions (validées en brainstorming)

1. **Contenu du rappel visible : compact + action.** Une accroche courte (nb de faits + domaines,
   faits d'équipe à récupérer, faits non promus → `/memory-promote`, nudge `/doctor` si souci). Le
   **digest complet reste en contexte** pour amorcer le modèle, mais n'est pas étalé à l'écran.
2. **Nudge `/doctor` : vérif santé rapide, nudge si KO.** Le hook lance à chaque démarrage une vérif
   légère et non bloquante ; il n'affiche `⚠ … → /doctor` **que si** un problème est détecté.
   Silencieux si tout va bien.
3. **Injection via stdout reformulé en instruction (option A).** Pas de passage en JSON
   `additionalContext` (échappement fragile en bash, aucun gain fonctionnel ici).
4. **`SessionEnd` inchangé** : le rappel de promotion à la fermeture reste tel quel.

## Modèle / forme de sortie (`hook-memory.sh start`)

La sortie du mode `start` se compose de trois blocs, dans cet ordre :

1. **Instruction au modèle** (une ligne claire) : demande à Claude d'afficher tel quel le rappel
   compact à l'utilisateur en tête de sa première réponse, puis de répondre normalement.
2. **Rappel compact** (ce que l'utilisateur verra). Format :
   - ligne 1 : `🧠 Mémoire d'équipe — N faits (domaine1, domaine2, domaine3…)`
   - ligne 2 : `📥 X à récupérer · 📝 Y non promu` (X = commits amont, Y = faits locaux non promus)
   - ligne 3 (conditionnelle) : `⚠ souci de config → /doctor` **seulement si** la vérif santé
     remonte ≥1 problème.
   - Le rappel `/memory-promote` reste présent quand Y > 0 (formulation actuelle conservée).
3. **Digest complet** (mode actuel de `digest.py`), étiqueté comme contexte silencieux « pour ton
   usage, ne pas tout réafficher » → le modèle reste amorcé avec les faits + patterns sans les
   étaler à l'écran.

Best-effort conservé : le hook ne bloque jamais la session, reste silencieux en cas d'échec, sort
toujours 0 (`set +e +u +o pipefail`, `timeout` sur les commandes réseau / Python).

## Vérif santé (`sm_health_issues`)

Nouvelle fonction dans `scripts/lib.sh`, non bloquante, best-effort. Signature :
`sm_health_issues "<clone>" "<project_dir>" "<pull_failed:0|1>"` → imprime **un libellé de problème par ligne**
(vide si tout va bien). Vérifications :

- `git` et `python3` présents dans le `PATH`.
- **Clone du vault** : le chemin existe et contient un dépôt git (`<clone>/.git`).
- **Lien mémoire** : `~/.claude/projects/<slug>/memory` existe et pointe (symlink résolu) dans le
  clone — réutilise `sm_memory_dir`.
- **Dernier `git pull`** : si l'appelant signale un échec (`pull_failed=1`), c'est un problème.

L'appelant (`hook-memory.sh`) compte les lignes ; ≥1 → affiche le nudge `/doctor`. La fonction est
réutilisable par `doctor.sh` (hors scope de ce chantier d'y brancher, mais l'interface le permet).

## Mode `--summary` de `digest.py`

`digest.py` accepte un flag `--summary` : au lieu du digest complet, il sort **une seule ligne**
`N faits (domaine1, domaine2, domaine3…)` (domaines de 1er niveau, ordre du digest, éventuellement
tronqué au-delà de quelques domaines avec `…`). Le mode complet (sans flag) reste **strictement
inchangé** (compatibilité ascendante, tests existants verts). `hook-memory.sh` appelle `--summary`
pour la ligne 1 du rappel compact, et le mode complet pour le bloc de contexte.

## Architecture / composants

| Composant | Rôle | Action |
|---|---|---|
| `scripts/hook-memory.sh` | assemble instruction + rappel compact + digest contexte ; lance la vérif santé. | Modifier |
| `scripts/lib.sh` | ajoute `sm_health_issues`. | Modifier |
| `scripts/digest.py` | ajoute le mode `--summary` (ligne compacte). | Modifier |
| `tests/test_hook_memory.py` | instruction présente, rappel compact bien formé, nudge KO quand clone/lien cassé, silencieux quand sain. | Créer |
| `tests/test_digest.py` | mode `--summary` ; mode complet inchangé. | Modifier/Créer |
| `docs/ARCHITECTURE.md` | documenter le rappel visible + la vérif santé. | Modifier |

## Tests (convention doc/tests du programme)

- **`test_hook_memory.py`** (sous-process, vault jetable, `SM_REGISTRY`/`SM_CONFIG_DIR` isolés,
  jamais le vrai vault) :
  - `start` émet la **ligne d'instruction** d'affichage.
  - le **rappel compact** contient `🧠 Mémoire d'équipe — N faits` avec les domaines.
  - **nudge KO** : clone absent OU lien mémoire cassé → la ligne `→ /doctor` apparaît.
  - **sain** : clone + lien OK, pull ok → **aucune** ligne `/doctor`.
  - best-effort : registre/clone absent → sortie 0, silencieux (comportement actuel préservé).
- **`test_digest.py`** : `--summary` sort une ligne `N faits (…)` ; le mode complet reste identique
  (un cas d'or sur un petit vault).
- **`sm_health_issues`** : couvert via `test_hook_memory.py` (cas KO/sain) ; pas de test bash dédié.

## Hors scope / évolutions

- **Brancher `sm_health_issues` dans `doctor.sh`** : l'interface le permet, mais non fait ici (reste
  focalisé sur le rappel de démarrage).
- **Sortie JSON `additionalContext` / `sessionTitle`** : écartée (option B) — fragile en bash, sans
  gain.
- **Lire le compteur natif « setup issues » de Claude Code** : impossible depuis un hook ; non visé.
- **Rendre le digest configurable (verbosité par projet)** : YAGNI pour l'instant.

## Décisions clés (récapitulatif)

1. Rappel rendu visible en **instruisant le modèle de l'afficher** (stdout reformulé) ; apparaît en
   première réponse de Claude.
2. Rappel **compact + action** affiché ; **digest complet** conservé en contexte silencieux.
3. **Vérif santé rapide** non bloquante (`sm_health_issues`) ; nudge `/doctor` **seulement si KO**.
4. `digest.py --summary` pour la ligne compacte ; mode complet inchangé. `SessionEnd` inchangé.
   Tests + doc selon la convention du programme.
