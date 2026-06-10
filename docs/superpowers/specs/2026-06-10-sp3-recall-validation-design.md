# Design — SP3 : validation du rappel (investigation)

**Date :** 2026-06-10
**Statut :** Design validé, prêt pour exécution (investigation, pas un build)
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Programme :** chantier SP3 de « faire vivre la mémoire centrale ».

## Objectif

Savoir si la **valeur** se produit : Claude **récupère-t-il le bon fait** quand c'est pertinent ?
C'est le moment de vérité du système — un système d'écriture sans lecture utile ne sert à rien.

**Contrainte structurelle :** la question centrale (« Claude sort-il le fait *spontanément* en
travail réel ») est **comportementale** et ne peut pas être simulée fidèlement depuis la session du
projet *plugin*. Une partie de SP3 est donc **manuelle** (à lancer dans un projet branché,
`newnegocian-workspace`).

## Méthodologie — trois sondes

### Sonde 1 — Qualité de récupération (automatable)
Sur le **vrai** vault `negocian-memory` (9 faits réels, dont 6 partageables), ~6-10 requêtes
**paraphrasées en français** (une par fait partageable + quelques distracteurs) passées dans
`embed.search` (modèle multilingue FR). Mesure : le bon fait est-il en **top-1 / top-3** ?
Répond à : *« l'outil sort-il le bon fait sur du contenu réel ? »* (l'éval antérieure était sur du
synthétique uniforme).

### Sonde 2 — Diagnostic du câblage : rappel natif vs sharding (le cœur)
Documenter ce que la **mémoire native** de Claude Code charge réellement face à un vault **shardé** :
`MEMORY.md` est chargé au démarrage, mais après le sharding c'est une **carte de domaines**
(pointeurs `→ index/<domaine>.md`), pas des résumés de faits. Les faits sont à **deux sauts**
(`index/<domaine>.md` → `<domaine>/<fait>.md`). Hypothèse à confirmer : le sharding a borné le coût
**tokens de démarrage** *au prix* de la **visibilité directe des faits au rappel natif** → le rappel
dépend désormais (a) d'un parcours multi-saut décidé par Claude, ou (b) d'un appel à `search_memory`.
Livrable : le **mécanisme réel** (ce qui est chargé / atteignable) + le **risque** explicité.

### Sonde 3 — Protocole comportemental (manuel)
Une expérience **reproductible** à lancer dans `newnegocian-workspace` : N scénarios de travail réel
où un fait connu *devrait* être rappelé, + une **grille d'observation** (rappelé ? via natif / via
`search_memory` / pas du tout ?). C'est la moitié non automatisable.

## Livrable

Un document de constats `docs/superpowers/specs/2026-06-10-sp3-recall-findings.md` :
- résultats Sonde 1 (tableau requête → rang du bon fait) ;
- diagnostic Sonde 2 (mécanisme + risque) ;
- protocole Sonde 3 (scénarios + grille) ;
- **correctifs recommandés priorisés** — chacun deviendra son propre petit chantier si retenu.

## Process

SP3 est une **investigation**, pas un build TDD : après cette spec, on **exécute directement** les
sondes 1-2 et on écrit les constats, plutôt que de passer par writing-plans/subagents (faits pour
construire du logiciel). La convention **doc + tests** s'applique uniquement si une sonde produit un
**bout de code réutilisable** (alors il est testé) ; ici l'éval Sonde 1 est un script jetable de
mesure, pas un produit.

## Hors scope

- **Corriger** le rappel : SP3 ne fait que **constater** ; les correctifs recommandés sont des
  chantiers ultérieurs (priorisés dans le livrable).
- Construire un **harnais d'éval réutilisable** : écarté pour ce tour (investigation légère).
