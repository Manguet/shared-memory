# Design — Résolution de conflits du vault (`resolve-conflicts.py` + `/memory-review`)

**Date :** 2026-06-11
**Statut :** Design validé, prêt pour le plan
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Programme :** « consolider la mémoire centrale » — chantier 2/5 (workflow d'équipe).

## Objectif

La boucle d'équipe `promote → review → merge` n'a jamais tourné en **concurrence réelle**, et
`/memory-review` fait `git merge --no-ff` **sans rien dire des conflits**. Ce chantier comble ce trou :
une **procédure** de résolution + un **outil** qui résout automatiquement le cas mécanique fréquent
et ne laisse à l'humain que les vrais arbitrages.

Constat structurant : `index/**` est un **artefact dérivé** (régénéré par `reshard.py` depuis les
faits), tandis que `<domaine>/<fait>.md` est la **source** et `MEMORY.md` la **carte curée**. Donc :

- **Deux personnes ajoutent des faits différents au même domaine** (cas fréquent) → les faits sont
  des fichiers séparés (git les fusionne sans heurt) ; **seul `index/<domaine>.md` entre en conflit**
  → conflit *dérivé*, **régénérable** par reshard, sans jugement humain.
- **Deux personnes éditent le même fait** (rare) → vrai conflit de contenu → **humain**.
- **Conflit sur `MEMORY.md`** (deux nouveaux domaines) → carte curée, non régénérée → **humain**
  (et c'est souhaitable : la revue doit justement vérifier qu'on ne double pas un domaine).

## Décisions (validées en brainstorming)

1. **Procédure + outil** : doc dans `/memory-review` + outil qui résout automatiquement les conflits
   sur `index/**` (régénération reshard) et signale les vrais conflits (faits, carte) à l'humain.
2. **Intégration dans `/memory-review`** (pas de skill dédié) : la résolution de conflit est une
   étape de la revue.
3. **Pas de fusion de contenu de faits** : fusionner deux versions d'un même fait demande un jugement
   (véracité) → toujours humain. L'outil ne touche jamais au contenu d'un fait.

## Architecture / composants

| Composant | Rôle | Action |
|---|---|---|
| `scripts/resolve-conflicts.py` | `classify_conflicts` (testable) + CLI d'orchestration git. | Créer |
| `tests/test_resolve_conflicts.py` | unitaires (classification) + intégration (vrais conflits git). | Créer |
| `skills/memory-review/SKILL.md` | gestion de conflit à l'étape de merge. | Modifier |
| `skills/memory-promote/references/governance.md` | section « Conflits ». | Modifier |
| `docs/ARCHITECTURE.md` | §14 « Résolution de conflits ». | Modifier |

**`scripts/resolve-conflicts.py`** (stdlib seule ; lance `reshard.py` en sous-processus) :

- `classify_conflicts(paths) -> dict` — cœur **testable**. Prend les chemins en conflit (relatifs au
  vault) et renvoie `{"derived": [...], "facts": [...], "map": [...], "other": [...]}` :
  - chemin sous `index/` (y compris `index/<domaine>/<sous>.md`) → `derived` ;
  - `MEMORY.md` (racine) → `map` ;
  - autre `*.md` → `facts` ;
  - reste → `other`.
- CLI `python3 resolve-conflicts.py <clone>` (orchestration) :
  1. conflits : `git -C <clone> diff --name-only --diff-filter=U` ;
  2. `classify_conflicts` ;
  3. **Cas A — `facts`/`map`/`other` non vides** → les afficher groupés avec consigne (résoudre à la
     main, `git add`, relancer), **ne rien écrire ni stager**, sortir **1** ;
  4. **Cas B — uniquement `derived`** → `python3 reshard.py <clone>`, puis `git -C <clone> add -A
     index/`, afficher « ✅ N index régénéré(s) et résolu(s) — termine par `git commit` », sortir **0** ;
  5. **Cas C — aucun conflit** → « Aucun conflit à résoudre. », sortir **0**.

## Flux en deux temps

Garantit que reshard ne voit **jamais** de marqueurs de conflit (il n'est lancé qu'au cas B, quand
tous les faits sont propres) :

1. Premier lancement après un merge conflictuel : s'il y a des faits/carte en conflit → cas A,
   l'outil s'arrête et liste ce que l'humain doit arbitrer.
2. L'humain résout faits + carte, `git add`.
3. Re-lancement : il ne reste que des `index/**` → cas B, régénération + staging automatiques.
4. Le référent finalise par `git commit` (le merge est complété).

## Intégration `/memory-review`

À l'étape « Approuver et fusionner », après `git merge --no-ff origin/<branche>` :

- **Si le merge réussit sans conflit** : flux actuel inchangé (push).
- **Si le merge signale un conflit** : lancer `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-conflicts.py "<clone>"` :
  - **sortie 1** (cas A) → présenter les faits/carte à arbitrer ; après résolution humaine + `git add`,
    relancer l'outil ;
  - **sortie 0** (cas B) → les index sont régénérés et stagés ; finaliser par
    `git -C "<clone>" commit` puis `git push origin main`.
- En cas de doute ou de conflit ingérable : `git -C "<clone>" merge --abort` annule proprement
  (rien n'est poussé ; la branche `promote/*` reste intacte pour réessayer).

## Doc & tests (convention du programme)

**Tests — `tests/test_resolve_conflicts.py`** (`unittest`) :
- **Unitaires `classify_conflicts`** : `index/mailing.md` et `index/mailing/sous.md` → `derived` ;
  `MEMORY.md` → `map` ; `mailing/relance.md` et `feedback_x.md` → `facts` ; `notes.txt` → `other` ;
  liste vide → tous vides.
- **Intégration (vrai dépôt git, style `test_hooks`/`test_reshard`)** :
  - *Conflit dérivé seul* : deux branches ajoutent des **faits différents** au même domaine →
    conflit sur `index/<domaine>.md` uniquement → l'outil sort **0**, l'index régénéré contient les
    **deux** faits, et `git diff --diff-filter=U` est vide (résolu).
  - *Vrai conflit de fait* : deux branches éditent **le même** `<domaine>/<fait>.md` → l'outil sort
    **1**, signale le fait, **ne stage rien**, le fichier reste en conflit.

**Doc :**
- `skills/memory-review/SKILL.md` — gestion de conflit à l'étape de merge (cas A/B, `merge --abort`).
- `skills/memory-promote/references/governance.md` — section « Conflits » (dérivé vs source vs carte,
  l'outil, flux en deux temps).
- `docs/ARCHITECTURE.md` **§14 (nouvelle)** — « Résolution de conflits ».

## Hors scope / évolutions

- **Fusion automatique du contenu d'un fait** : exclue (jugement de véracité ; toujours humain).
- **Auto-union de `MEMORY.md`** : exclue (carte curée avec descriptions + Patterns ; un conflit force
  utilement la vérification des doublons de domaine).
- **Détection préventive de conflits avant le push** (côté promote) : hors scope ; le conflit se
  traite à la fusion, côté référent.
- **Test réel à 2 humains en concurrence** : reste à la charge de l'utilisateur ; ce chantier livre la
  procédure, l'outil et la doc qui le rendent gérable.

## Décisions clés (récapitulatif)

1. `scripts/resolve-conflicts.py` : `classify_conflicts` (testable) + CLI (cas A humain / cas B auto /
   cas C rien).
2. `index/**` régénéré par reshard (auto) ; faits et `MEMORY.md` → humain ; jamais de fusion de
   contenu de fait.
3. Flux en deux temps (reshard ne voit jamais de marqueurs) ; intégré à `/memory-review` ;
   `merge --abort` comme échappatoire sûr.
4. Doc (review, governance, ARCHITECTURE §14) + tests (unitaires + intégration git).
