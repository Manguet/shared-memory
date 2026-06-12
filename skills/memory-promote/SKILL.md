---
name: memory-promote
description: This skill should be used when the user asks to "promouvoir la mémoire", "partager mes mémoires", "proposer mes faits à l'équipe", "pousser la mémoire d'équipe", "promote memory", "/memory-promote", or at the end of a work session to propose new project facts to the shared vault. It collects new/changed project & reference memories, verifies them against the code, and pushes a proposal branch (git only) for a reviewer to merge.
argument-hint: "[résumé]"
allowed-tools: Bash, Read, Grep, Glob, Edit
version: 0.2.0
---

# memory-promote — Proposer ses mémoires au vault (branche git)

Collecte les faits mémoire **nouveaux ou modifiés** du projet courant, ne garde que les types
partageables (`project`, `reference`), **vérifie chaque fait contre le code actuel**, puis
**pousse une branche de proposition** sur le vault. Tout en **git** (pas de `gh`). Rien n'est
fusionné automatiquement : un référent valide via `/memory-review` (voir `references/governance.md`).

## Pré-requis

- Le projet doit déjà être branché sur un vault (`/memory-setup` exécuté).
- `git` authentifié avec accès en écriture au vault (push de branches).

## Procédure

1. **Localiser le vault.** Résoudre le clone du projet courant :

   ```bash
   bash -c 'source ${CLAUDE_PLUGIN_ROOT%/}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
   ```

   Si rien n'est renvoyé, demander à l'utilisateur de lancer `/memory-setup` d'abord.

2. **Identifier les faits candidats.** Dans le clone, lister les fichiers `.md`
   nouveaux/modifiés non encore dans `main` :

   ```bash
   git -C "<clone>" fetch origin
   git -C "<clone>" status --porcelain
   git -C "<clone>" diff --name-only origin/main
   ```

3. **Filtrer.** Lire le frontmatter de chaque candidat. **Ne garder que** `metadata.type: project`
   ou `reference`. **Exclure** `user`, `feedback`, tout `feedback_*.md`, **et tout fait
   `metadata.local: true`** (faits gardés en local, jamais partagés).

4. **Sélection interactive.** Présenter la liste des candidats restants. Demander à l'utilisateur
   s'il veut **exclure** certains faits de cette promotion. Pour chaque fait exclu, demander :
   - **« toujours »** → poser `metadata.local: true` sur le fait dans le vault (il sort des candidats
     et du compteur, durablement) ;
   - **« cette fois »** → ne pas l'inclure dans cette proposition (aucun drapeau ; il restera candidat
     au prochain promote).
   Les faits restants après ce tri sont les **faits sélectionnés**.

5. **Vérifier sémantiquement chaque fait sélectionné.** Confronter au **code actuel** (Grep/Read/Glob) :
   encore vrai ? contredit-il la version canonique dans `main` ? Écarter ou corriger les faits
   périmés/contradictoires, et résumer à l'utilisateur ce qui est gardé, corrigé, écarté.
   C'est le cœur du skill — ne pas le sauter.
   Pour chaque fait **confirmé vrai** contre le code, mettre à jour son `metadata.reviewed` à la
   **date du jour** (c'est le signal de fraîcheur : « vérifié le … »). Pour re-stamper, tu peux
   utiliser `python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/stale.py --restamp "<clone>/<fait>"`.

6. **Repérer le rangement par domaine** (→ `${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`).
   Chaque fait sélectionné vit dans `<domaine>/<fait>.md` : noter son **chemin relatif** dans le
   vault, c'est lui qui sera recopié à l'identique dans le worktree (étape 7). reshard y régénérera
   `index/**` (lignes compactes) et **découpera en sous-domaines** tout domaine dépassant ~150 faits
   (déplacement de faits). Si un **nouveau domaine** apparaît, sa ligne sera à ajouter à `MEMORY.md` ;
   si un découpage a lieu, le **signaler** dans le résumé de proposition.

7. **Construire la proposition dans un worktree propre** (l'index poussé ne contiendra que les faits
   sélectionnés ; le vault local n'est pas muté) :

   ```bash
   tmp="$(mktemp -d)"
   git -C "<clone>" fetch origin
   git -C "<clone>" worktree add --detach "$tmp" origin/main
   # copier dans $tmp UNIQUEMENT les faits sélectionnés, à leur chemin relatif (mkdir -p au besoin)
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/reshard.py "$tmp"      # index propre, sans les exclus/local
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/lint.py "$tmp"         # advisory
   git -C "$tmp" checkout -b promote/<slug>-<court-descriptif>
   git -C "$tmp" add -A
   git -C "$tmp" commit -m "memory: <résumé>"
   git -C "$tmp" push -u origin HEAD
   git -C "<clone>" worktree remove "$tmp" && git -C "<clone>" worktree prune
   ```

   Si un **nouveau domaine** apparaît, ajouter sa ligne à `MEMORY.md` (dans `$tmp`) avant le commit.
   Le **lint** est **advisory** : s'il signale des erreurs (`severity=error` : champ requis manquant,
   type invalide, `name` en double), les **afficher** et **demander** s'il faut les corriger d'abord
   (via `/memory-lint` ou à la main) — sans bloquer le push de force ; l'utilisateur décide.

8. **Confirmer.** Donner le **nom de la branche** poussée et rappeler qu'un **référent** doit la
   relire et la fusionner via `/memory-review` (jamais l'auteur lui-même) avant qu'elle devienne
   canonique.

## Points d'attention

- **Pas de fusion automatique.** Le skill pousse une branche, point. La fusion vers `main` se
  fait via `/memory-review`, par un référent.
- **Index hiérarchique** : chaque promotion touche `index/<domaine>.md` (par domaine), ce qui
  **réduit les conflits** ; la carte `MEMORY.md` ne change qu'à la **création d'un domaine**.
  Garder la carte = liste de domaines (jamais un fait par ligne).
- **Faits perso** (`user`/`feedback`) : restent en local, ne jamais les inclure dans la branche.
- **Faits `local`** : exclus de toute promotion (drapeau `metadata.local: true`) ; réglable via le
  viewer (case « fait local ») ou la sélection interactive.

## Prochaine étape (guider l'utilisateur)

Donner le nom de la branche et dire mot pour mot : « Un coéquipier doit la valider avec
`/memory-review` avant qu'elle devienne canonique. »

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`** — structure shardée, sous-index, carte, seuil.
- **`references/governance.md`** — revue de branche, protection de `main`, vérification.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — helpers (`sm_slug`, `sm_vault_clone_for_slug`).
