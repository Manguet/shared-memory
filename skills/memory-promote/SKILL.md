---
name: memory-promote
description: This skill should be used when the user asks to "promouvoir la mémoire", "partager mes mémoires", "ouvrir une PR mémoire", "pousser la mémoire d'équipe", "promote memory", "/memory-promote", or at the end of a work session to propose new project facts to the shared vault. It collects new/changed project & reference memories, verifies them against the code, and opens a Pull Request.
argument-hint: "[message-de-pr]"
allowed-tools: Bash, Read, Grep, Glob
version: 0.1.0
---

# memory-promote — Proposer ses mémoires au vault (via PR)

Collecte les faits mémoire **nouveaux ou modifiés** du projet courant, ne garde que les
types partageables (`project`, `reference`), **vérifie chaque fait contre le code actuel**,
puis ouvre une **Pull Request** sur le vault. Rien n'est mergé automatiquement : la
validation reste humaine (voir `references/governance.md`).

## Pré-requis

- Le projet doit déjà être branché sur un vault (`/memory-setup` exécuté).
- `git` et `gh` (GitHub CLI) authentifiés avec accès au vault.

## Procédure

1. **Localiser le vault.** Résoudre le clone du projet courant :

   ```bash
   bash -c 'source ${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
   ```

   Si rien n'est renvoyé, demander à l'utilisateur de lancer `/memory-setup` d'abord.

2. **Identifier les faits candidats.** Dans le clone, lister les fichiers `.md`
   nouveaux/modifiés non encore dans `main` :

   ```bash
   git -C "<clone>" status --porcelain
   git -C "<clone>" fetch origin && git -C "<clone>" diff --name-only origin/main
   ```

3. **Filtrer par type.** Lire le frontmatter de chaque fichier candidat. **Ne garder que**
   `metadata.type: project` ou `reference`. **Exclure** `user` et `feedback` (perso, jamais
   partagés) ainsi que tout fichier `feedback_*.md`.

4. **Vérifier sémantiquement chaque fait retenu.** Pour chaque fait, confronter son contenu
   au **code actuel** (Grep/Read/Glob) : le fait est-il encore vrai ? contredit-il la version
   canonique déjà dans `main` ? Écarter ou corriger les faits périmés/contradictoires, et
   résumer à l'utilisateur ce qui est gardé, corrigé, écarté. C'est le cœur du skill —
   ne pas le sauter.

5. **Créer la branche + commit + PR.** Depuis le clone :

   ```bash
   git -C "<clone>" checkout -b promote/<slug>-<court-descriptif>
   git -C "<clone>" add <fichiers-retenus> MEMORY.md
   git -C "<clone>" commit -m "memory: <résumé>"
   git -C "<clone>" push -u origin HEAD
   gh pr create --repo <vault-repo> --fill --title "Mémoire : <résumé>" --body "<détail des faits>"
   ```

   Mettre à jour `MEMORY.md` (l'index) si de nouveaux faits sont ajoutés.

6. **Confirmer.** Donner l'URL de la PR et rappeler qu'elle doit être **revue et approuvée**
   (≥1 approbation, pas d'auto-merge) avant de devenir canonique.

## Points d'attention

- **Jamais de merge automatique.** Le skill ouvre une PR, point.
- **Index `MEMORY.md`** : c'est le point de conflit le plus probable — vérifier qu'il reste
  cohérent (une ligne par fait).
- **Faits perso** (`user`/`feedback`) : restent en local, ne jamais les inclure dans la PR.

## Prochaine étape (guider l'utilisateur)

Donner l'URL de la PR et dire mot pour mot : « Un coéquipier doit la valider avec
`/memory-review` (ou sur GitHub) avant qu'elle devienne canonique. »

## Ressources

- **`references/governance.md`** — règle de PR, surfaces de revue, protection de branche.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — helpers (`sm_slug`, `sm_vault_clone_for_slug`).
