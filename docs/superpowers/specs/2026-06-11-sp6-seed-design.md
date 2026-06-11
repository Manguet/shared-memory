# Design — SP6 : amorçage à froid (`/memory-seed`)

**Date :** 2026-06-11
**Statut :** Design validé, prêt pour le plan
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Programme :** dernier chantier de « faire vivre la mémoire centrale ».

## Objectif

Un vault vide n'a aucune valeur, et `/memory-import` traite **un doc à la fois**. SP6 franchit le
**démarrage à froid** : un skill `/memory-seed` qui **peuple** un vault depuis les **sources humaines
existantes** du projet (CLAUDE.md, doc), en réutilisant tout l'existant (conventions d'import, dédup
SP4, reshard, stampage `reviewed`).

## Décisions (validées en brainstorming)

1. **Sources = CLAUDE.md + doc** (`README.md`, `docs/**.md`) — écrites/curées par des humains, donc
   **faits fiables, faible risque d'invention**. **Pas de scan de code** (risque de sur-affirmation).
2. **Nouveau skill `/memory-seed`** (plutôt qu'étendre `/memory-import`) — découvrable, intention
   distincte (peuplement initial). Réutilise les conventions d'import.
3. **Brouillons (étage 1)** : `/memory-seed` écrit dans la working copy, **ne partage rien** ; le
   canonique reste `/memory-promote` → `/memory-review`. Gouvernance intacte.
4. **Confirmation avant écriture en masse** : présenter un récap et **demander l'accord** (pas de
   déversement silencieux).
5. **Dédup contre l'existant** : chaque candidat passe par `scripts/similar.py` (SP4) → mettre à jour
   un fait proche plutôt que créer un doublon.

## Procédure du skill

1. **Localiser le vault** (`lib.sh` : `sm_vault_clone_for_slug`). Absent → demander `/memory-setup`.
2. **Localiser les sources** du projet courant : `CLAUDE.md`, `README.md`, `docs/**.md` (Glob).
3. **Extraire des faits atomiques** (mêmes conventions qu'`/memory-import` : une idée durable = un
   fait ; frontmatter `name`/`description` discriminante/`metadata.type`/`reviewed = aujourd'hui` ;
   domaine déduit ; jamais de faits `user`/`feedback`).
4. **Dédupliquer** chaque candidat contre le vault : `python3 scripts/similar.py "<clone>" --text …` ;
   si un fait existant ressemble (≥ 0.80), **mettre à jour** l'existant plutôt que créer un doublon.
5. **Confirmer** : récap « N faits extraits dans M domaines » → **demander l'accord** avant d'écrire.
6. **Écrire les brouillons** dans `<clone>` (domaines), régénérer les index via `reshard.py`.
7. **Guider** : rappeler mot pour mot `/memory-promote` (rien n'est partagé sans revue).

## Architecture / composants

| Composant | Rôle SP6 | Action |
|---|---|---|
| `skills/memory-seed/SKILL.md` | le skill d'amorçage. | Créer |
| `README.md`, `INSTALL.md`, `docs/ARCHITECTURE.md` | documenter `/memory-seed`. | Modifier |

**Pas de nouveau code Python** : réutilise `scripts/similar.py` (dédup), `scripts/reshard.py`
(index), `assets/fact-template.md` (gabarit + `reviewed`), `scripts/lib.sh` (résolution vault).

## Doc & tests

- **Doc** : `README` (tableau des skills + une ligne), `INSTALL` (commandes utiles), `ARCHITECTURE`
  §12. La convention `doc + tests` s'applique pour la **doc** ; côté **tests**, SP6 ne produit
  **aucun code testable** (c'est un skill = jugement de Claude) → vérification par **relecture du
  skill** (comme SP3), pas de test unitaire.
- **Fumée** : lancer `/memory-seed` dans un projet doté d'un `CLAUDE.md` est une vérification
  manuelle (le skill orchestre Read/Write/Bash) — décrite dans le plan, exécutée par l'humain.

## Hors scope / évolutions

- **Scan du code** pour en déduire des faits : écarté (sur-affirmation ; les sources restent
  humaines).
- **Extraction automatique sans confirmation** : exclue (toujours confirmer avant d'écrire en masse).
- **Auto-promotion** : exclue — les faits semés restent des brouillons à promouvoir/relire.

## Décisions clés (récapitulatif)

1. Skill `/memory-seed` : sources CLAUDE.md + doc, faits fiables, pas de scan code.
2. Brouillons étage 1 ; confirmation avant écriture ; dédup (SP4) contre l'existant ; `reviewed`
   stampé ; reshard pour les index ; renvoi vers `/memory-promote`.
3. Réutilise tout l'existant — pas de nouveau code Python ; vérification = relecture + fumée manuelle.
