# Design — SP4 : dédup sémantique à la création

**Date :** 2026-06-11
**Statut :** Design validé, prêt pour le plan
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Programme :** chantier SP4 de « faire vivre la mémoire centrale ».

## Objectif

Éviter l'**accumulation de quasi-doublons** (même savoir, slugs différents) qui dilue la mémoire.
Au **moment où un fait naît** (import ou CRUD), réutiliser les embeddings pour détecter « ce fait
ressemble à 0,9 à un fait existant X » → **proposer de mettre à jour X** plutôt que d'empiler un
doublon. La détection à la création est la prévention à la source.

## Décisions (validées en brainstorming)

1. **Déclenchement à la création** : skill `/memory-import` **et** création CRUD du viewer.
2. **Signaler, jamais fusionner** : on propose « mettre à jour X » ou « créer quand même » ;
   **l'humain tranche** (cohérent avec la gouvernance — pas d'action automatique).
3. **Seuil de quasi-doublon : cosine ≥ 0.80** (constante, réglable). Assez haut pour éviter les faux
   positifs (l'éval SP3 : ~0,6-0,79 pour des faits *distincts* ; un vrai doublon reformulé monte ~0,9).
4. **Texte comparé** = `name + description + body` du candidat (même base que les embeddings, via
   `embed.fact_text`).
5. **fastembed optionnel** : absent → dédup sémantique **inactive** (`vector_inactive: true`), les
   appelants le **signalent** sans bloquer (cohérent avec `search_memory`).

## Architecture

Cœur réutilisable dans `embed.py`, branché à deux points de création.

```
embed.find_similar(text, facts, store, embed_fn, threshold=0.80, k=3, exclude=None)
  └─ embed le candidat → semantic_topk → filtre ≥ seuil, exclut `exclude` → pointeurs

Branchement 1 (import) : scripts/similar.py <clone> --text … → /memory-import propose
Branchement 2 (CRUD)   : POST /api/similar (serve-viewer) → UI avertit avant de créer
```

## Cœur — `embed.find_similar`

`find_similar(text, facts, store, embed_fn, threshold=0.80, k=3, exclude=None)` :
- `embed_fn=None` → `{"similar": [], "vector_inactive": True}` (pas de blocage).
- sinon : `qvec = embed_fn([text])[0]` → `semantic_topk(qvec, store, k+1)` → garder les `(file, score)`
  avec `score ≥ threshold` et `file != exclude`, mapper en **pointeurs** `{file, name, path, score}`
  (jamais de body), top `k`. → `{"similar": [...], "vector_inactive": False}`.
- Pur, testable avec un `embed_fn` factice (comme le reste d'`embed.py`).

## Branchement 1 — Import (`scripts/similar.py` + `/memory-import`)

**`scripts/similar.py`** (CLI + cœur testable) :
- `similar.py <vault> --text "<texte>" [--threshold 0.80] [--exclude <file>]`.
- Orchestration : `collect_facts(vault)` + `load_fastembed_embed_fn` + (rafraîchir le store via
  `sm_paths.store_path_for_slug` sur le slug du projet courant) + `find_similar` → imprime un JSON
  `{"similar": [...], "vector_inactive": bool}`.
- Le **cœur** (`run(vault, text, threshold, exclude, embed_fn)`) prend l'`embed_fn` en paramètre →
  testable avec un factice.

**`/memory-import`** : à l'étape 5 (avant d'écrire le fait), lancer `similar.py` sur le candidat ;
si des quasi-doublons remontent, **proposer** « ce fait ressemble à X — mettre à jour X plutôt que
créer ? ». Si `vector_inactive`, le **mentionner** (sans bloquer).

## Branchement 2 — CRUD (`POST /api/similar` + UI)

**`POST /api/similar`** (serve-viewer) :
- Corps `{name, description, body, domain, exclude?}` → construit le texte (`fact_text`-like) →
  `collect_facts` + charge fastembed (lazy) + rafraîchit le store + `find_similar` →
  `{"similar": [...], "vector_inactive": bool}`.
- **Pas de jeton requis** : c'est une **requête en lecture** (aucune mutation) — comme `/search`.
- Réutilise `embed.find_similar`.

**UI (viewer)** : au clic « créer le fait », appeler d'abord `/api/similar` ; s'il y a des
quasi-doublons → **panneau d'avertissement** (faits similaires cliquables + bouton **« créer quand
même »**) ; sinon, création directe. `vector_inactive` → pas d'avertissement (silencieux).

## Doc & tests (convention du programme — partie de « terminé »)

**Tests (`unittest`) :**
- `find_similar` (`tests/test_embed.py`) : mock `embed_fn` → renvoie les faits ≥ seuil, **exclut**
  `exclude`, `vector_inactive` si `embed_fn=None`.
- `scripts/similar.py` cœur (`tests/test_similar.py`) : `run(...)` avec un `embed_fn` factice →
  quasi-doublon détecté ; sans → vide.
- `POST /api/similar` (`tests/test_serve_viewer.py`) : monkeypatch de l'`embed_fn` (comme les tests
  MCP) → renvoie le similaire ; absent → `vector_inactive`.
- UI = **vérif manuelle** (panneau d'avertissement + « créer quand même »).

**Documentation :** `docs/domain-convention.md` (dédup à la création), `README.md` (une ligne),
`skills/memory-import/SKILL.md` (déjà câblé par le branchement), `docs/ARCHITECTURE.md` §12.

## Découpage du plan — **2 phases** (arrêt possible après la Phase 1)

- **Phase 1 — Import** : `find_similar` + `scripts/similar.py` + câblage `/memory-import` + doc +
  tests. Livre la prévention sur le chemin principal de création.
- **Phase 2 — CRUD** : `POST /api/similar` + UI d'avertissement (« créer quand même ») + tests.

## Hors scope / évolutions

- **Scan global** (`/memory-dedup` sur tout le vault) : écarté pour ce tour (chantier ultérieur de
  nettoyage d'un vault déjà peuplé).
- **Fusion automatique** : exclue — on signale, l'humain met à jour.
- **Re-ranking / déduplication transitive** : hors scope.

## Décisions clés (récapitulatif)

1. `embed.find_similar(text, …, threshold=0.80, exclude=None)` → pointeurs des quasi-doublons.
2. Déclenchement à la création (import via `similar.py` ; CRUD via `POST /api/similar`).
3. Signaler, jamais fusionner ; seuil 0,85 ; fastembed optionnel (`vector_inactive` sinon).
4. Plan en 2 phases (import puis CRUD).
5. Doc + tests dans « terminé ».
