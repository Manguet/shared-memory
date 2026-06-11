---
name: memory-lint
description: This skill should be used when the user asks to "linter la mémoire", "vérifier le format des faits", "nettoyer le vault", "normaliser les faits", "valider les faits", "lint memory", "check memory facts", or "/memory-lint". It reports format/quality problems in a vault's facts and applies only the safe mechanical fix (flat frontmatter → metadata block) after confirmation.
argument-hint: ""
allowed-tools: Bash, Read, AskUserQuestion
version: 0.1.0
---

# memory-lint — Linter et normaliser les faits du vault

Détecte les problèmes de **format** des faits (champs requis, type valide, `name` unique, date
bien formée, frontmatter à plat, wikilinks cassés, perso mal placé), **corrige mécaniquement** la
seule dérive sûre (frontmatter à plat → bloc `metadata:`) **après confirmation**, et **signale** le
reste pour décision humaine. N'écrit jamais sans accord.

## Procédure

1. **Localiser le vault** du projet courant :

   ```bash
   bash -c 'source ${CLAUDE_PLUGIN_ROOT%/}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
   ```

   Si rien n'est renvoyé, demander de lancer `/memory-setup` d'abord.

2. **Lancer le lint** (lecture seule, n'écrit rien) :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/lint.py "<clone>"
   ```

3. **Présenter le rapport** tel quel : erreurs d'abord, puis avertissements. Expliquer brièvement
   les **erreurs** (elles cassent les pointeurs/recherche : champ requis manquant, type invalide,
   `name` en double) — elles se corrigent **à la main** (ou via le viewer `/memory-ui`).

4. **S'il y a des findings `[auto-corrigeable]`** (frontmatter à plat) : indiquer le nombre de faits
   concernés et **demander l'accord** (AskUserQuestion) avant d'écrire. Sans accord, ne rien faire.

5. **Si accord, appliquer** la correction mécanique puis régénérer les index :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/lint.py "<clone>" --fix
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/reshard.py "<clone>"
   ```

6. **Rappeler** que les **avertissements** non corrigés (description courte, `name` non-slug,
   wikilinks cassés, perso mal placé) sont à traiter **à la main** ou via `/memory-ui`, et renvoyer
   vers `/memory-promote` une fois le vault propre.

## Points d'attention

- **Une seule auto-correction** : `flat_frontmatter` (plat → bloc `metadata:`). Tout le reste est
  **signalé**, jamais réécrit (renommer un `name` ou déplacer un perso casserait les pointeurs).
- **Confirmation obligatoire** avant toute écriture — pas de mutation silencieuse.
- **Brouillons (étage 1)** : les corrections restent locales tant que `/memory-promote` n'a pas
  poussé une branche relue.
- **Pas de date inventée** : le lint signale l'absence de `reviewed` mais ne la stampe pas (dater
  est un jugement ; c'est `/memory-promote` qui stampe quand un fait est confirmé vrai).

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/scripts/lint.py`** — moteur (détection + correction mécanique).
- **`${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`** — format canonique d'un fait, types valides.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/reshard.py`** — régénère `index/**` après correction.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — résolution du vault.
