---
name: memory-seed
description: This skill should be used when the user asks to "amorcer la mémoire", "peupler le vault", "semer la mémoire depuis CLAUDE.md", "initialiser la mémoire du projet", "seed memory", "bootstrap the vault", or "/memory-seed". It populates an empty/sparse vault from existing human-written sources (CLAUDE.md, README, docs) as draft facts, ready for /memory-promote.
argument-hint: ""
allowed-tools: Bash, Read, Write, Grep, Glob, AskUserQuestion
version: 0.1.0
---

# memory-seed — Amorcer un vault depuis les sources existantes

Peuple un vault vide (ou partiel) en extrayant des **faits atomiques** depuis les **sources
humaines** du projet (CLAUDE.md, doc). Écrit des **brouillons** (étage 1, local) ; rien n'est
partagé tant que `/memory-promote` n'a pas eu lieu. Réutilise les conventions d'`/memory-import`.

## Procédure

1. **Localiser le vault** du projet courant :

   ```bash
   bash -c 'source ${CLAUDE_PLUGIN_ROOT%/}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
   ```

   Si rien n'est renvoyé, demander de lancer `/memory-setup` d'abord.

2. **Localiser les sources humaines** du projet (ne PAS scanner le code) :
   `CLAUDE.md`, `README.md`, et `docs/**.md` (via Glob/Read). Ignorer les fichiers générés.

3. **Extraire des faits atomiques** (mêmes règles qu'`/memory-import` →
   `${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`) : une **idée durable** = un fait ; ne pas
   recopier la prose. Pour chaque fait : `name` (slug unique), `description` **discriminante**,
   `metadata.type` (`project`/`reference`), `metadata.reviewed` = **date du jour** (`AAAA-MM-JJ`),
   domaine déduit. **Jamais** de faits `user`/`feedback` (perso). Suivre
   `${CLAUDE_PLUGIN_ROOT}/assets/fact-template.md`.

4. **Dédupliquer contre le vault existant** — pour chaque fait candidat :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/similar.py "<clone>" --text "<nom>. <description>. <corps>"
   ```

   Si un fait existant ressemble (`similar` non vide, cosine ≥ 0.80), **mettre à jour** l'existant
   plutôt que créer un doublon. Si `vector_inactive: true` (fastembed absent), le mentionner et
   continuer sans bloquer.

5. **Confirmer avant d'écrire en masse** : présenter un **récap** « N faits extraits dans M
   domaines » (liste nom + domaine) et **demander l'accord** (AskUserQuestion) avant toute écriture.
   Ne rien écrire sans validation.

6. **Écrire les brouillons** dans le clone (`<domaine>/<fait>.md`), puis régénérer les index :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/reshard.py "<clone>"
   ```

7. **Régénérer le viewer** (optionnel, pour qu'une vue ouverte se mette à jour) :

   ```bash
   bash ${CLAUDE_PLUGIN_ROOT%/}/scripts/view.sh --build-only
   ```

## Points d'attention

- **Sources humaines uniquement** : CLAUDE.md + doc. **Pas de déduction depuis le code** (risque de
  sur-affirmation). Les faits semés doivent être vrais et vérifiables.
- **Brouillons (étage 1)** : on écrit dans la working copy, jamais vers le canonique. Rien n'est
  partagé tant que `/memory-promote` n'a pas poussé une branche relue.
- **Confirmation obligatoire** avant l'écriture en masse — pas de déversement silencieux.
- **Dédup** : ne pas empiler un doublon d'un fait déjà présent (mettre à jour l'existant).
- **Pas de perso** : ne jamais créer de faits `user`/`feedback`.

## Prochaine étape (guider l'utilisateur)

Terminer en disant mot pour mot : « Pour proposer ces faits à l'équipe, lance `/memory-promote`. »
Les faits semés restent locaux tant que ce n'est pas fait.

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`** — structure shardée, faits, fraîcheur.
- **`${CLAUDE_PLUGIN_ROOT}/assets/fact-template.md`** — gabarit d'un fait.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/similar.py`** — dédup sémantique contre l'existant.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/reshard.py`** — régénère `index/**` + `MEMORY.md`.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — résolution du vault.
