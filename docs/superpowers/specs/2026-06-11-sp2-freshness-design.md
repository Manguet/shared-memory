# Design — SP2 : fraîcheur / anti-péremption

**Date :** 2026-06-11
**Statut :** Design validé, prêt pour le plan
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Programme :** chantier SP2 de « faire vivre la mémoire centrale ».

## Objectif

Les faits sont des **observations datées**. Sans suivi de fraîcheur, un fait devenu faux (le code a
changé) reste indistinguable d'un fait vérifié hier → la mémoire perd la **confiance**, et une
mémoire à laquelle on ne se fie plus est morte. SP2 ajoute une **date de vérification** aux faits et
**surface les faits périmés** pour qu'ils soient revérifiés.

## Décisions (validées en brainstorming)

1. **Champ `metadata.reviewed: AAAA-MM-JJ`** = « dernière fois que ce fait a été confirmé vrai ».
   Un seul champ, exposé par `collect_facts` (`fact.reviewed`).
2. **Stampé automatiquement** à : **création** (gabarit, CRUD, `memory-import`), **édition** dans le
   CRUD (on vient de toucher/relire le fait), et **promote/review** (qui vérifient déjà le fait
   contre le code — c'est le vrai signal de confiance).
3. **Faits hérités sans date** = traités **« à vérifier »** (péremption inconnue → remontent dans la
   surface). **Pas de backfill forcé** (on n'invente pas une date de vérification).
4. **Seuil de péremption : 90 jours** par défaut (constante ; le code bouge vite).
5. **Péremption calculée côté client** (viewer JS : `aujourd'hui − reviewed > seuil`) — pas de
   nouvel endpoint serveur ; le stampage seul écrit la date.

## Architecture / composants

| Composant | Rôle dans SP2 |
|---|---|
| `assets/fact-template.md` | + champ `reviewed` dans le gabarit. |
| `scripts/build-viewer.py` (`collect_facts`) | expose `fact.reviewed` (depuis `metadata.reviewed`). |
| `scripts/serve-viewer.py` (`_fact_text`/`create_fact`/`update_fact`) | **stampe `reviewed = date.today()`** à la création et à l'édition. |
| `assets/viewer-template.html` | **badge de fraîcheur** sur la carte + **vue « périmés »** (client). |
| `skills/memory-import`, `memory-promote`, `memory-list` | stamper à la création / re-stamper les vérifiés / signaler la fraîcheur. |
| `docs/domain-convention.md` | la règle `reviewed` + le seuil. |

`reshard` **préserve** le frontmatter (il réécrit le contenu brut) → `reviewed` survit aux
redécoupages, sans traitement spécial.

## Surfaces

**1. Badge dans le viewer** (carte de détail, calcul client depuis `f.reviewed`) :
- `✓ vérifié il y a Nj` en **vert** si N < 90 ;
- `⚠ vérifié il y a Nj` en **orange/rouge** si N ≥ 90 ;
- `à vérifier` (neutre) si **pas de date** (fait hérité).

**2. Vue « périmés » dans le viewer** : un bouton outil (`≡ à revérifier`) qui liste les faits dont
la fraîcheur dépasse le seuil **ou non datés**, **triés du plus vieux**, cliquables (réutilise le
rendu de liste existant). Pur client.

**3. Liste conversationnelle** : édition légère de `/memory-list` — il **signale la fraîcheur** des
faits restitués et peut répondre « qu'est-ce qui est à revérifier ? » (Claude lit `reviewed` et
compare à aujourd'hui ; aucun nouveau script).

## Stampage (mécanique)

- **Création** (`_fact_text` CRUD, gabarit, `memory-import`) → `reviewed = date.today().isoformat()`.
- **Édition** (CRUD `update_fact`) → re-stampe `reviewed = aujourd'hui`.
- **Promote/review** → re-stampe `reviewed = aujourd'hui` sur les faits **vérifiés contre le code**
  (instruction de skill ; c'est déjà l'étape de vérification).
- Format : date seule `AAAA-MM-JJ` (pas d'heure/fuseau).

## Doc & tests (convention du programme — partie de « terminé »)

**Documentation :**
- `docs/domain-convention.md` : champ `reviewed`, règle de péremption, seuil 90 j.
- `assets/fact-template.md` : le champ dans le gabarit.
- `README.md` : une ligne « fraîcheur » ; `docs/ARCHITECTURE.md` : note (§12 ou §10).

**Tests (`unittest`) :**
- `collect_facts` expose `reviewed` (`tests/test_build_viewer.py`) — fait avec `metadata.reviewed`
  → `fact["reviewed"]` correct ; absent → `""`.
- `create_fact` / `update_fact` stampent `reviewed: <aujourd'hui>` dans le frontmatter écrit
  (`tests/test_serve_viewer.py`) — vérifier la présence de la date du jour.
- Le **calcul de péremption** (badge + vue périmés) est **client JS** trivial → **vérif manuelle**
  dans le viewer live (un fait daté récent = vert ; daté > 90 j = rouge ; non daté = « à vérifier »).

## Découpage du plan (≈ 6 tâches)

1. `reviewed` dans `fact-template` + `collect_facts` l'expose + test.
2. CRUD (`_fact_text`/`create_fact`/`update_fact`) stampe `reviewed` + test.
3. UI viewer : badge de fraîcheur + vue « périmés » (vérif manuelle).
4. Skills : `memory-import` (stampe), `memory-promote` (re-stampe vérifiés), `memory-list` (signale).
5. Doc : `domain-convention` + `fact-template` + `README` + `ARCHITECTURE`.
6. Vérification d'ensemble (suite + fumée création datée + relecture).

## Hors scope / évolutions

- **Re-vérification automatique** d'un fait contre le code (un `/memory-verify` dédié) : chantier
  ultérieur — ici la re-vérification passe par l'édition CRUD ou le promote/review (qui re-stampent).
- **Seuil configurable** par projet : constante 90 j pour ce tour ; surchargeable plus tard.
- **Nudge au démarrage** (hook SP1 « N faits périmés ») : écarté pour garder SP2 découplé de SP1.

## Décisions clés (récapitulatif)

1. Champ `metadata.reviewed: AAAA-MM-JJ`, exposé par `collect_facts`.
2. Stampé à création / édition CRUD / promote-review (vérification contre code).
3. Faits non datés = « à vérifier » ; pas de backfill forcé.
4. Seuil 90 j ; péremption calculée **côté client** (badge + vue périmés).
5. Doc (convention/template/README/ARCHITECTURE) + tests (`collect_facts.reviewed`, stampage CRUD) dans « terminé ».
