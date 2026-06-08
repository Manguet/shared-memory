---
name: memory-review
description: This skill should be used when the user asks to "valider la mémoire", "relire les PR mémoire", "approuver une promotion", "review memory PRs", "valider une proposition de mémoire", or "/memory-review". It lists open Pull Requests on the project's memory vault, shows their diff inside Claude, and lets a reviewer approve or merge (respecting branch protection).
argument-hint: "[numéro-de-PR]"
allowed-tools: Bash, Read
version: 0.1.0
---

# memory-review — Valider les promotions de mémoire (revue de PR dans Claude)

Surface de revue **conversationnelle** des Pull Requests du vault : lister, afficher le diff,
approuver/merger — l'alternative à l'UI GitHub web pour ceux qui préfèrent rester dans Claude.
La mémoire canonique ne change que par PR
(voir `${CLAUDE_PLUGIN_ROOT}/skills/memory-promote/references/governance.md`).

## Pré-requis

- `gh` (GitHub CLI) authentifié avec accès au vault.
- Connaître le repo du vault (lu depuis le registre / l'URL `vault` de `/memory-setup`).

## Procédure

1. **Localiser le vault et son repo** :

   ```bash
   bash -c 'source ${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
   ```

   Utiliser ce clone comme contexte `gh` (ou passer `--repo <owner/vault>`).

2. **Lister les PR ouvertes** :

   ```bash
   gh pr list --repo <owner/vault> --state open
   ```

3. **Afficher le diff** de la PR choisie (faits markdown, lisibles) :

   ```bash
   gh pr diff --repo <owner/vault> <numéro>
   ```

   Lire chaque fait proposé et, si besoin, le **confronter au code actuel** pour juger s'il
   est vrai et non contradictoire avec le canonique.

4. **Décision** (respecter la protection de branche) :
   - Approuver : `gh pr review --repo <owner/vault> <numéro> --approve`
   - Demander des changements : `gh pr review --repo <owner/vault> <numéro> --request-changes --body "…"`
   - Merger (si règles satisfaites) : `gh pr merge --repo <owner/vault> <numéro> --squash`

## Points d'attention

- **Pas d'auto-validation** : ne pas approuver/merger une PR **dont on est l'auteur**
  (≥1 approbation d'un autre, cf protection de branche).
- **La discussion** peut se faire ici, sur GitHub, ou hors-ligne ; la **décision** est tracée
  par la PR.
- Après merge, l'équipe récupère le canonique par `git pull` (ou au prochain `/memory-setup`/recall).

## Prochaine étape (guider l'utilisateur)

Après un merge, indiquer mot pour mot : « C'est canonique. Les autres récupéreront ce fait
au prochain démarrage de session ou via `/memory-setup` (qui fait un pull). »

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/skills/memory-promote/references/governance.md`** — règles de PR,
  protection de branche, surfaces de revue.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — localisation du vault.
