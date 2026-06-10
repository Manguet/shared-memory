# Design — CRUD local des faits dans le viewer

**Date :** 2026-06-10
**Statut :** Design validé, prêt pour le plan
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Prérequis :** viewer serveur (`serve-viewer.py`), sharding par domaine, `reshard.py` (livrés).

## Objectif et contrainte

Permettre de **gérer les faits directement dans l'UI** (créer, éditer, supprimer, déplacer entre
domaines, renommer un domaine) au lieu du seul flux conversationnel `/memory-import`
(snippet à copier). Aujourd'hui le viewer est **lecture seule** par décision d'architecture
(ARCHITECTURE.md §8).

**Contrainte non négociable — la gouvernance est préservée.** Le CRUD écrit **uniquement dans la
working copy locale** (étage 1, brouillons libres), **exactement comme `/memory-import`**. Il ne
pousse **rien** : le canonique passe toujours par `/memory-promote` → `/memory-review` (revue de
branche par un référent). Donc **aucun git dans l'UI**, aucune écriture vers le canonique — la
décision « pas d'UI qui fait du git / pas d'écriture vers le canonique » tient. Ce qui change : le
serveur de lecture gagne des **endpoints d'écriture limités au clone local**.

## Architecture

Approche retenue (A) : **étendre `serve-viewer.py`** avec des routes d'écriture, plutôt qu'un
microserveur séparé (B, surcoût) ou une UI qui compose une commande (C, = statu quo snippet).

```
Navigateur (formulaires)  ──POST/PUT/DELETE──►  serve-viewer.py (bind 127.0.0.1, vault = CLONE)
   créer/éditer/supprimer/déplacer/renommer            │ 1. vérifie le jeton same-origin (CSRF)
                                                        │ 2. valide (slug, type, domaine, anti-traversal)
                                                        │ 3. écrit/déplace/supprime le .md dans le clone
                                                        │ 4. reshard(clone) → régénère index/**
                                                        │ 5. renvoie les métadonnées fraîches
                                                        ▼
                                  working copy locale (étage 1, NON poussée)
   … plus tard, séparément …  /memory-promote → branche promote/* → /memory-review → canonique
```

Le serveur reçoit déjà le chemin du **clone** en argument (`serve-viewer.py <vault> <template>`),
et possède déjà `collect_facts`/`parse_md` (via `build-viewer.py`) et la garde anti-traversal
(`realpath` dans le vault, `.md` only). Les écritures réutilisent `reshard.reshard(vault)` comme
**moteur unique d'index** (idempotent, préserve `MEMORY.md` curée).

## Endpoints (les GET `/`, `/fact`, `/search` restent inchangés)

| Route | Effet | Corps JSON |
|---|---|---|
| `POST /api/fact` | **Créer** un fait | `{name, description, type, body, domain}` |
| `PUT /api/fact?f=<file>` | **Éditer** (nom, desc, type, corps) **et déplacer** (si `domain` change) | `{name, description, type, body, domain}` |
| `DELETE /api/fact?f=<file>` | **Supprimer** | — |
| `POST /api/rename-domain` | **Renommer** un domaine | `{old, new}` |

Note : `/api/move` envisagé en brainstorming est **fusionné dans `PUT`** — déplacer = éditer en
changeant le champ `domain` (le handler détecte le changement de domaine et relocalise le fait).
Une route de moins.

**Cycle commun à toute écriture** : (1) jeton CSRF, (2) validation, (3) mutation de fichier dans le
clone, (4) `reshard(vault)`, (5) réponse `200` avec `{facts, index, count}` (mêmes métadonnées que
`GET /`, sans body) → le client reconstruit l'arbre en un aller-retour.

## Validations (rejet `400` + message, sauf indication)

- **`name`** : slug `^[a-z0-9-]+$` ; **unique dans le domaine cible** (invariant `reshard`, qui lève
  sinon). Collision → `400`.
- **`type`** ∈ `project | reference | user | feedback`. Autre → `400`.
- **Faits perso** (`user` / `feedback`) : **forcés à la racine** (`domain` ignoré), jamais rangés en
  domaine, jamais partagés (règle existante de la convention).
- **`domain`** : slug ; le chemin résolu (`realpath`) doit rester **dans le vault** ; on n'écrit que
  des `.md`. Path-traversal (`../`, absolu) → `404` (même garde que `/fact`).
- **Édition / suppression d'un `file` inexistant** ou hors vault → `404`.
- **Jeton CSRF** absent ou faux → `403`.

## Cas particuliers

- **Renommer un domaine** (`POST /api/rename-domain`) : renomme le dossier `<old>/` → `<new>/`
  (réécriture des chemins des faits) puis **patch ciblé de la ligne du domaine dans `MEMORY.md`**
  (la carte est curée à la main : on remplace `…<old>… → index/<old>.md` par la version `<new>`,
  sans régénérer le reste de `MEMORY.md`), puis `reshard`. C'est le **seul** endpoint qui touche
  `MEMORY.md`. Refus `400` si `<new>` existe déjà.
- **Éditer le nom d'un fait** : `reshard` renomme le fichier en `<name>.md` ; l'identifiant `file`
  côté client devient périmé → le client se rafraîchit avec les métadonnées renvoyées (déjà prévu).
- **reshard après chaque écriture** : idempotent ; à l'échelle d'un vault local (dizaines de faits)
  c'est quasi instantané ; il préserve `MEMORY.md` (cf. son contrat). DRY : pas de seconde logique
  d'index.
- **Suppression récupérable** : le fichier est retiré du clone mais reste **récupérable via git**
  tant que non commité/poussé. L'UI exige une **confirmation**.
- **Sécurité CSRF** : un **jeton aléatoire** est généré au lancement du serveur, injecté dans la
  page servie (variable JS) et **exigé en en-tête** (`X-SM-Token`) sur toute écriture → une autre
  page locale ne peut pas le lire (same-origin) et ne peut donc pas écrire. Bind `127.0.0.1`
  conservé.
- **Concurrence** Claude (skills) ⇄ humain (UI) sur le même clone : **dernier-écrit-gagne**, pas de
  verrou (YAGNI ; c'est du local, git rattrape l'historique).

## UI (viewer-template.html)

- **Créer** : la tab « Rédiger un fait » (aujourd'hui un snippet à copier) devient un **vrai
  formulaire** (nom, description, type, **domaine** = liste des domaines existants + saisie libre
  pour en créer un ; désactivé/forcé-racine pour `user`/`feedback`, corps). Bouton **Créer** →
  `POST` → navigation vers le fait créé. Le snippet/`copier` est **retiré**.
- **Éditer / Supprimer** : sur la **carte de détail** d'un fait, deux actions en haut à droite.
  « Éditer » bascule la carte en formulaire pré-rempli → « Enregistrer » (`PUT`). « Supprimer » →
  **confirmation inline** (« récupérable via git tant que non poussé ») → `DELETE`.
- **Déplacer** : via le **champ domaine du formulaire d'édition** (changer le domaine relocalise).
- **Renommer un domaine** : petite **icône crayon** au survol d'un nœud de domaine dans la
  sidebar → saisie inline → `POST /api/rename-domain`.
- **Bandeau « local »** discret : « modifications locales — `/memory-promote` pour proposer à
  l'équipe » → rappelle l'étage 1 et la gouvernance.
- Après chaque écriture, le client **reconstruit** filtres + arbre à partir des métadonnées
  renvoyées (réutilise `rebuildNav()`).

## Testing

`tests/test_serve_viewer.py` (même pattern : `http.server` en thread + `urllib`, vault temporaire) :

- **créer** : `POST` → le `.md` existe dans le clone avec le bon frontmatter, apparaît dans
  `index/<domaine>.md`, `reshard` exécuté ;
- **créer perso** (`user`/`feedback`) → fichier à la **racine**, **absent** des index ;
- **éditer** : `PUT` modifie desc/type/corps ; changer le **nom** → fichier renommé ;
- **déplacer** : `PUT` avec un `domain` différent → fait relocalisé sous le nouveau domaine ;
- **supprimer** : `DELETE` retire le fichier, disparaît de l'index ; `404` si inexistant ;
- **renommer domaine** : dossier renommé + ligne `MEMORY.md` mise à jour ;
- **validations** : slug invalide → `400`, nom en double → `400`, traversal → `404`, **jeton CSRF
  absent → `403`** ;
- **UI JS** (formulaires) : vérification manuelle dans le viewer live.

## Découpage du plan

Un seul spec, **plan en 2 phases** :
- **Phase 1 — Cœur CRUD** : jeton CSRF + `POST`/`PUT`/`DELETE /api/fact` (créer/éditer/supprimer,
  validations, reshard, réponse métadonnées) + UI (formulaire de création, édition/suppression sur
  la carte, bandeau local) + tests. Livre déjà l'essentiel.
- **Phase 2 — Organiser** : déplacement (via le champ domaine du `PUT`) + `POST /api/rename-domain`
  (+ patch `MEMORY.md`) + UI (crayon de renommage) + tests.

## Hors scope / évolutions

- **Écriture vers le canonique** depuis l'UI / git dans le navigateur : **exclu** (gouvernance).
- **Édition collaborative temps réel / verrous** : exclu (local, dernier-écrit-gagne).
- **Validation/preview markdown riche** dans le formulaire : possible plus tard (le viewer rend déjà
  le markdown en lecture).
- **Export / import en masse** : hors scope.

## Décisions clés (récapitulatif)

1. Le CRUD écrit **uniquement** dans la working copy locale (étage 1) ; **aucun git, aucun push** —
   gouvernance `/memory-promote` → `/memory-review` intacte.
2. Implémentation = **extension de `serve-viewer.py`** (routes `/api/*`), réutilise `reshard` comme
   moteur d'index et la garde anti-traversal existante.
3. Endpoints : `POST`/`PUT`/`DELETE /api/fact` (+ déplacement fusionné dans `PUT`) et
   `POST /api/rename-domain` (seul à toucher `MEMORY.md`, par patch ciblé).
4. Faits perso (`user`/`feedback`) forcés à la racine ; jamais partagés.
5. Sécurité : bind localhost + **jeton same-origin** exigé sur les écritures.
6. UI : formulaire de création (remplace le snippet), édition/suppression sur la carte, renommage de
   domaine au survol, bandeau « local ».
7. Plan en 2 phases (cœur CRUD, puis organiser).
