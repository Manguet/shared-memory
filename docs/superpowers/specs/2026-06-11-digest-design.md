# Design — Digest au démarrage (rappel automatique)

**Date :** 2026-06-11
**Statut :** Design validé, prêt pour le plan
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Suite de :** SP1 (hooks) + SP3 (validation du rappel, qui a identifié ce trou).

## Objectif

Rendre le **rappel automatique** : aujourd'hui, au démarrage, seule la **carte** `MEMORY.md`
(domaines) est chargée nativement — **pas le contenu des faits** (SP3). Le rappel dépend donc de
Claude qui décide de creuser. Le **digest** injecte au démarrage une **description compacte de chaque
fait** → Claude **sait** ce qui existe et le **lit** quand le sujet arrive, sans qu'on ait à le lui
demander. C'est le levier qui rend l'outil **quasi mains-libres** (sans le rendre chronophage).

## Décisions (validées en brainstorming)

1. **Digest au `SessionStart`** (pas par message) : une fois par session, **zéro coût par message**.
2. **Borné** : description d'une ligne par fait jusqu'à un **budget** (`max_lines = 120`) ; au-delà →
   digest dégradé (carte + comptes + renvoi `search_memory`/`/memory-list`). Respecte le principe
   « démarrage borné » du sharding : petit vault = conscience totale et cheap ; gros vault = carte +
   recherche.
3. **Pur lecture de fichiers, aucun fastembed** (le digest n'est pas sémantique) → marche toujours.
4. **Réutilise le hook SP1** (`hook-memory.sh start`) + `collect_facts` + `reviewed` (SP2).

## Architecture

```
scripts/digest.py  →  build_digest(vault, max_lines=120) -> str   (réutilise collect_facts + reviewed)
hook-memory.sh start  →  python3 digest.py "$clone"  →  émis EN CONTEXTE avant le rappel synchro/promote
```

## Contenu du digest

Pour un vault sous le budget (`len(facts) ≤ max_lines`) :
- En-tête : `## Mémoire d'équipe (N faits)`.
- **Groupé par domaine** ; pour chaque fait : `` - `<nom>` — <description> · <type> `` avec un
  **`⚠`** si **périmé** (`reviewed` ≥ 90 j ou absent — réutilise SP2).
- **Inclut tous les faits** (project/reference **et** perso `user`/`feedback` — un feedback comme
  « ne jamais committer » guide aussi Claude). Les faits à la racine sous « général ».
- Si `MEMORY.md` contient une section **« Patterns & Conventions »**, l'inclure telle quelle (haute
  valeur transverse).

Au-dessus du budget (`len(facts) > max_lines`) :
- `## Mémoire d'équipe (N faits, M domaines) — digest complet trop volumineux`
- liste des **domaines + comptes**, puis : « utilise `search_memory` ou `/memory-list` pour le
  détail ». (La carte `MEMORY.md` reste chargée nativement.)

## Intégration au hook

Dans `hook-memory.sh` **mode `start` uniquement** : après la résolution du vault, calculer
`digest="$(python3 "$HERE/digest.py" "$clone" 2>/dev/null)"` (best-effort : échec → ignoré). Émettre
le **digest d'abord**, puis le message de synchro/promote existant. Le mode `end` est inchangé.
Best-effort, exit 0, jamais bloquant (inchangé).

## Coût tokens

Assumé et **borné** : ≤ ~`max_lines` lignes (~2 k tokens au pire). Sur le vrai negocian (~5 faits),
quelques lignes. Le bornage garantit l'absence de dérapage ; un gros vault retombe sur la carte.

## Doc & tests (convention du programme)

**Tests (`unittest`) :**
- `build_digest` (`tests/test_digest.py`) : petit vault → les **descriptions** des faits sont
  présentes, groupées par domaine ; un fait `reviewed` ancien → **`⚠`** ; au-delà du budget
  (`max_lines` bas) → digest **dégradé** (comptes, pas toutes les descriptions).
- Hook : `hook-memory.sh start` sur un vault branché (pattern `test_hooks.py`) → la sortie **contient
  une description de fait** (le digest est bien injecté).

**Doc :** `docs/ARCHITECTURE.md` §12 (le digest = rappel automatique au démarrage) + la sous-section
« Boucle vivante / hooks ». *(La refonte README « signaler les automatismes » est un chantier
**séparé**, demandé ensuite.)*

## Découpage du plan (~4 tâches)

1. `scripts/digest.py` (`build_digest` + CLI) + `tests/test_digest.py`.
2. Intégration dans `hook-memory.sh start` + test (hook émet le digest).
3. Doc `ARCHITECTURE.md`.
4. Vérification (suite + fumée hook réelle).

## Hors scope / évolutions

- **Recall par message** (`UserPromptSubmit`) : écarté pour ce tour (latence/bruit par message) ;
  réévaluable si le digest au démarrage s'avère insuffisant.
- **Résumé/abstraction** des faits : non — le digest cite les `description` telles quelles (DRY,
  véracité : la description est déjà l'aiguillage).

## Décisions clés (récapitulatif)

1. Digest au `SessionStart`, borné (`max_lines=120`), pur fichiers (aucun fastembed).
2. Description compacte par fait groupée par domaine + `⚠` périmé + Patterns ; dégradé si trop gros.
3. `scripts/digest.py` (`build_digest`) intégré au hook SP1 ; émis avant le rappel synchro/promote.
4. Doc ARCHITECTURE + tests ; README signalé dans un chantier séparé.
