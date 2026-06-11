---
name: memory-promote
description: This skill should be used when the user asks to "promouvoir la mémoire", "partager mes mémoires", "proposer mes faits à l'équipe", "pousser la mémoire d'équipe", "promote memory", "/memory-promote", or at the end of a work session to propose new project facts to the shared vault. It collects new/changed project & reference memories, verifies them against the code, and pushes a proposal branch (git only) for a reviewer to merge.
argument-hint: "[résumé]"
allowed-tools: Bash, Read, Grep, Glob
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

3. **Filtrer par type.** Lire le frontmatter de chaque candidat. **Ne garder que**
   `metadata.type: project` ou `reference`. **Exclure** `user`, `feedback`, et tout
   `feedback_*.md` (perso, jamais partagés).

4. **Vérifier sémantiquement chaque fait retenu.** Confronter au **code actuel** (Grep/Read/Glob) :
   encore vrai ? contredit-il la version canonique dans `main` ? Écarter ou corriger les faits
   périmés/contradictoires, et résumer à l'utilisateur ce qui est gardé, corrigé, écarté.
   C'est le cœur du skill — ne pas le sauter.
   Pour chaque fait **confirmé vrai** contre le code, mettre à jour son `metadata.reviewed` à la
   **date du jour** (c'est le signal de fraîcheur : « vérifié le … »).

5. **Régénérer l'index hiérarchique via reshard** (→ `${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`).
   Chaque fait retenu vit dans `<domaine>/<fait>.md`. Lancer :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/reshard.py "<clone>"
   ```

   reshard régénère `index/**` (lignes compactes) et **découpe en sous-domaines** tout domaine
   dépassant ~150 faits (déplacement de faits). Il **préserve la carte `MEMORY.md`** curée ; si un
   **nouveau domaine** apparaît, ajouter sa ligne à `MEMORY.md` à la main. Si un découpage a lieu,
   le **signaler** dans le résumé de proposition.

6. **Créer la branche + commit + push** depuis le clone (inclure faits + sous-index + carte) :

   ```bash
   git -C "<clone>" checkout -b promote/<slug>-<court-descriptif> origin/main
   git -C "<clone>" add -A     # faits (déplacés en sous-domaines compris), index/**, MEMORY.md
   git -C "<clone>" commit -m "memory: <résumé>"
   git -C "<clone>" push -u origin HEAD
   ```

7. **Confirmer.** Donner le **nom de la branche** poussée et rappeler qu'un **référent** doit la
   relire et la fusionner via `/memory-review` (jamais l'auteur lui-même) avant qu'elle devienne
   canonique.

## Points d'attention

- **Pas de fusion automatique.** Le skill pousse une branche, point. La fusion vers `main` se
  fait via `/memory-review`, par un référent.
- **Index hiérarchique** : chaque promotion touche `index/<domaine>.md` (par domaine), ce qui
  **réduit les conflits** ; la carte `MEMORY.md` ne change qu'à la **création d'un domaine**.
  Garder la carte = liste de domaines (jamais un fait par ligne).
- **Faits perso** (`user`/`feedback`) : restent en local, ne jamais les inclure dans la branche.

## Prochaine étape (guider l'utilisateur)

Donner le nom de la branche et dire mot pour mot : « Un coéquipier doit la valider avec
`/memory-review` avant qu'elle devienne canonique. »

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`** — structure shardée, sous-index, carte, seuil.
- **`references/governance.md`** — revue de branche, protection de `main`, vérification.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — helpers (`sm_slug`, `sm_vault_clone_for_slug`).
