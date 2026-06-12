# Design — Harnais d'évaluation du rappel (`eval-recall.py` + `/memory-eval`)

**Date :** 2026-06-12
**Statut :** Design validé, prêt pour le plan
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Programme :** « consolider la mémoire centrale » — chantier 5/5 (mesurer la valeur).

## Objectif

Tout l'édifice (digest, `search_memory`, fraîcheur) vise à ce que **le bon fait remonte au bon
moment**, mais rien ne le **mesure**. Ce chantier fournit un harnais qui évalue la **qualité du
rappel** : pour une requête, le fait attendu ressort-il dans le **top-k** ? Via le **vrai** chemin de
recherche (`embed.search`, comme `search_memory`).

## Décisions (validées en brainstorming)

1. **Cas auto (description→fait) + paraphrases LLM** : le moteur évalue automatiquement (chaque
   description sert de requête, le fait doit ressortir) ; le skill `/memory-eval` enrichit en faisant
   générer par Claude des requêtes réalistes variées. Le moteur prend les cas en entrée (injectables).
2. **Métriques diagnostiques** : `recall@k`, `MRR`, `rang #1` (discriminabilité) + liste des **ratés**.
   Pas de seuil pass/fail — on lit et on agit.
3. **Honnêteté grep** : l'éval est pertinente en **sémantique** (fastembed) ; en repli **grep**
   (lexical), chercher par la description matche trivialement → le rapport le **signale**.

## Architecture / composants

| Composant | Rôle | Action |
|---|---|---|
| `scripts/eval-recall.py` | métriques + `eval_cases` + `auto_cases` + recherche prod + CLI. | Créer |
| `tests/test_eval_recall.py` | unitaires (métriques, `eval_cases` stub, `auto_cases`) + intégration CLI. | Créer |
| `skills/memory-eval/SKILL.md` | skill d'évaluation (paraphrases LLM + interprétation). | Créer |
| `README.md`, `INSTALL.md`, `docs/ARCHITECTURE.md` | documenter. | Modifier |

**`scripts/eval-recall.py`** (stdlib ; réutilise `embed.py`, `build-viewer.py` via `importlib`) :

- `recall_at_k(ranked, expected, k) -> bool` — `expected` dans `ranked[:k]`. **Pur.**
- `reciprocal_rank(ranked, expected) -> float` — `1/rang` si trouvé (1-indexé), sinon `0.0`. **Pur.**
- `eval_cases(cases, query_fn, k) -> dict` — `cases = [{"query","expect"}]` ; pour chaque,
  `ranked = query_fn(query)` (liste de noms classés) ; agrège
  `{"n","hits","recall_pct","mrr","rank1","misses":[{"query","expect"}]}`. `query_fn` **injectable**.
- `auto_cases(facts) -> [{"query": <description>, "expect": <name>}]` — l'éval automatique (ignore
  les faits sans description).
- `search_query_fn(vault) -> (query_fn, vector_inactive)` — **prod** : charge les faits, réutilise le
  chemin de `search_memory` (`embed.load_fastembed_embed_fn` + `embed.refresh_store` si dispo +
  `embed.search`), renvoie un `query_fn(query)` qui produit la liste des **noms** classés ;
  `vector_inactive=True` si repli grep.
- CLI :
  - `python3 eval-recall.py <vault> [--k 8]` → éval **auto** + rapport.
  - `python3 eval-recall.py <vault> --cases cas.json [--k 8]` → éval des cas fournis (JSON
    `[{"query","expect"}]`).

**Rapport** (`_format_report(report, k, vector_inactive)`) :
```
Éval rappel — N cas, k=8, mode sémantique
recall@k : 7/8 (88%)
MRR      : 0.812
rang #1  : 6/8 (discriminabilité)
Ratés (fait absent du top-k) :
- "comment relancer un panier" → attendu `relance-j3`
```
Si `vector_inactive`, une ligne d'avertissement en tête : *« ⚠ fastembed absent — recall mesuré en
lexical (grep), proxy faible ; lance /memory-doctor pour l'éval sémantique. »*

## Flux du skill `/memory-eval`

1. **Localiser le vault** (`lib.sh`). Absent → demander `/memory-setup`.
2. **Générer des requêtes réalistes** : lire les faits (descriptions) et, pour chacun, produire 1-2
   **paraphrases / questions** que poserait un humain (formulations variées, pas la description
   brute) → écrire un `cas.json` (`[{"query","expect": <name>}]`) dans un fichier temporaire.
3. **Lancer l'éval** : `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/eval-recall.py "<clone>" --cases <cas.json>`.
4. **Présenter** : `recall@k`, `MRR`, `rang #1`, et la **liste des ratés**. Pour chaque raté, une
   piste : améliorer la **description** (aiguillage) → `/memory-lint` ; fusionner un **doublon**
   confusable (dédup) ; activer **fastembed** si en grep → `/memory-doctor` ; re-vérifier un fait
   périmé → `/memory-refresh`.
5. **Lecture seule** : le skill **n'écrit aucun fait** ; il diagnostique et oriente.

## Doc & tests (convention du programme)

**Tests — `tests/test_eval_recall.py`** (`unittest`) :
- `recall_at_k` : attendu dans top-k → vrai ; au-delà de k → faux ; absent → faux.
- `reciprocal_rank` : rang 1 → `1.0` ; rang 3 → `1/3` ; absent → `0.0`.
- `eval_cases` avec un `query_fn` **stub** déterministe → vérifie `n`, `hits`, `recall_pct`, `mrr`,
  `rank1`, et le contenu de `misses`.
- `auto_cases` : faits → cas `[{query: description, expect: name}]` ; un fait sans description est ignoré.
- **Intégration** : CLI auto sur un petit vault fixture (repli grep déterministe) → produit un rapport
  contenant `recall@k`.

**Doc :**
- `docs/ARCHITECTURE.md` **§17 (nouvelle)** — « Évaluation du rappel » (`eval-recall.py` +
  `/memory-eval` ; recall@k / MRR / discriminabilité ; sémantique vs grep).
- `README.md` — ligne `/memory-eval` (tableau des skills) + une puce « Sous le capot ».
- `INSTALL.md` — `/memory-eval` dans les commandes utiles.

## Hors scope / évolutions

- **Seuil pass/fail** ou gating CI : exclu — l'éval est diagnostique (le projet n'a pas de vault).
- **Cas manuels maintenus** : non prioritaire (les paraphrases LLM couvrent le besoin sans fichier à
  maintenir) ; le format `--cases` reste ouvert si l'utilisateur veut figer des cas.
- **Réglage des hyperparamètres** de recherche (k, modèle) : hors scope ; on **mesure**, on ne tune pas.
- **Éval du digest** (passif) : hors scope ; le rappel actif (`search_memory`) est le levier mesurable.

## Décisions clés (récapitulatif)

1. `scripts/eval-recall.py` : `recall_at_k` / `reciprocal_rank` / `eval_cases` (query_fn injectable) /
   `auto_cases` / `search_query_fn` (vrai chemin de recherche) + CLI (auto / `--cases`).
2. Métriques `recall@k` + `MRR` + `rang #1` + ratés ; diagnostique, pas de gating ; avertissement grep.
3. Skill `/memory-eval` : Claude génère des requêtes réalistes → éval → interprétation (oriente vers
   lint / dédup / doctor / refresh). Lecture seule.
4. Doc (ARCHITECTURE §17, README, INSTALL) + tests (`test_eval_recall.py`).
