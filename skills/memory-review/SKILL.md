---
name: memory-review
description: This skill should be used when the user asks to "valider la mémoire", "relire les propositions de mémoire", "fusionner une branche mémoire", "review memory", "valider une proposition", or "/memory-review". It reviews proposed memory branches in the vault with git (diff against main) and, once approved, merges them into main — using git only, no GitHub CLI.
argument-hint: "[nom-de-branche]"
allowed-tools: Bash, Read
version: 0.1.0
---

# memory-review — Valider les propositions de mémoire (git seul)

Relit les **branches de proposition** (`promote/…`) poussées sur le vault, montre leur diff
par rapport à `main`, et — une fois approuvées — les **fusionne dans `main`**. Tout en **git**,
sans `gh`. La mémoire canonique ne change que par cette revue
(voir `${CLAUDE_PLUGIN_ROOT}/skills/memory-promote/references/governance.md`).

## Pré-requis

- `git` authentifié avec accès en **écriture** sur `main` du vault (rôle référent).

## Procédure

1. **Localiser le clone du vault** :

   ```bash
   bash -c 'source ${CLAUDE_PLUGIN_ROOT%/}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
   ```

2. **Récupérer et lister les propositions** :

   ```bash
   git -C "<clone>" fetch --prune origin
   git -C "<clone>" branch -r --list 'origin/promote/*'
   ```

3. **Afficher le diff** de la branche choisie vs `main` (faits markdown, lisibles) :

   ```bash
   git -C "<clone>" diff origin/main...origin/<branche>
   ```

   Lire chaque fait et, si besoin, le **confronter au code actuel** pour juger s'il est vrai
   et non contradictoire avec le canonique.

4. **Décision** :
   - **Approuver et fusionner** :

     ```bash
     git -C "<clone>" checkout main
     git -C "<clone>" pull --ff-only origin main
     git -C "<clone>" merge --no-ff origin/<branche> -m "memory: <résumé>"
     git -C "<clone>" push origin main
     git -C "<clone>" push origin --delete <branche>     # nettoyage de la branche
     ```

   - **Refuser / demander des corrections** : ne pas fusionner ; communiquer à l'auteur le
     fait à corriger, il relancera `/memory-promote`.

## Points d'attention

- **Ne pas valider sa propre proposition** : le référent ≠ l'auteur.
- **`main` protégée** : seuls les référents poussent sur `main` (GitHub → Settings → Branches →
  *Restrict who can push to matching branches*). Les autres ne poussent que des `promote/*`.

## Prochaine étape (guider l'utilisateur)

Après une fusion, indiquer mot pour mot : « C'est canonique. Les autres récupéreront ce fait
au prochain démarrage de session ou via `/memory-setup` (qui fait un pull). »

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/skills/memory-promote/references/governance.md`** — revue de branche,
  protection de `main`.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — localisation du vault.
