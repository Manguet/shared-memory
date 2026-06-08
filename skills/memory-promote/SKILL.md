---
name: memory-promote
description: This skill should be used when the user asks to "promouvoir la mémoire", "partager mes mémoires", "proposer mes faits à l'équipe", "pousser la mémoire d'équipe", "promote memory", "/memory-promote", or at the end of a work session to propose new project facts to the shared vault. It collects new/changed project & reference memories, verifies them against the code, and pushes a proposal branch (git only) for a reviewer to merge.
argument-hint: "[résumé]"
allowed-tools: Bash, Read, Grep, Glob
version: 0.1.0
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
   bash -c 'source ${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
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

5. **Créer la branche + commit + push** depuis le clone :

   ```bash
   git -C "<clone>" checkout -b promote/<slug>-<court-descriptif> origin/main
   git -C "<clone>" add <fichiers-retenus> MEMORY.md
   git -C "<clone>" commit -m "memory: <résumé>"
   git -C "<clone>" push -u origin HEAD
   ```

   Mettre à jour `MEMORY.md` (l'index) si de nouveaux faits sont ajoutés.

6. **Confirmer.** Donner le **nom de la branche** poussée et rappeler qu'un **référent** doit la
   relire et la fusionner via `/memory-review` (jamais l'auteur lui-même) avant qu'elle devienne
   canonique.

## Points d'attention

- **Pas de fusion automatique.** Le skill pousse une branche, point. La fusion vers `main` se
  fait via `/memory-review`, par un référent.
- **Index `MEMORY.md`** : point de conflit le plus probable — vérifier qu'il reste cohérent
  (une ligne par fait).
- **Faits perso** (`user`/`feedback`) : restent en local, ne jamais les inclure dans la branche.

## Prochaine étape (guider l'utilisateur)

Donner le nom de la branche et dire mot pour mot : « Un coéquipier doit la valider avec
`/memory-review` avant qu'elle devienne canonique. »

## Ressources

- **`references/governance.md`** — revue de branche, protection de `main`, vérification.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — helpers (`sm_slug`, `sm_vault_clone_for_slug`).
