# Harnais d'évaluation du rappel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un moteur `scripts/eval-recall.py` (recall@k / MRR / discriminabilité, via le vrai chemin de recherche) et un skill `/memory-eval` qui mesure si le bon fait remonte au bon moment, et oriente la remédiation.

**Architecture :** Métriques pures + `eval_cases(cases, query_fn, k)` (query_fn injectable → testable sans fastembed) + `auto_cases` + `search_query_fn` (réutilise `embed.search` comme `search_memory`) + CLI. Le skill fait générer par Claude des requêtes réalistes, lance l'éval, interprète. Diagnostique, lecture seule.

**Tech Stack :** Python 3 (stdlib : `importlib`, `json`, `os`, `sys`), réutilise `embed.py`/`build-viewer.py`, `unittest`.

**Référence design :** `docs/superpowers/specs/2026-06-12-recall-eval-design.md`.

**Convention du programme :** doc ET tests à jour à chaque chantier (cf. mémoire `chantier-doc-tests-convention`).

---

## File Structure

| Fichier | Responsabilité | Action |
|---|---|---|
| `scripts/eval-recall.py` | métriques + `eval_cases` + `auto_cases` + `search_query_fn` + CLI. | Créer |
| `tests/test_eval_recall.py` | unitaires (métriques, `eval_cases` stub, `auto_cases`, recherche grep). | Créer |
| `skills/memory-eval/SKILL.md` | skill d'évaluation (paraphrases LLM + interprétation). | Créer |
| `README.md`, `INSTALL.md`, `docs/ARCHITECTURE.md` | documenter. | Modifier |

**Conventions réutilisées :**
- `scripts/embed.py` : `search(query, facts, store, embed_fn, k=8) -> {"results":[{file,name,path,score}], "vector_inactive": bool}` ; `load_fastembed_embed_fn() -> embed_fn|None` ; `refresh_store(facts, store, embed_fn) -> store`.
- `scripts/build-viewer.py` : `collect_facts(vault, include_body) -> (facts, index_body)` (chaque fait : name/description/…).
- Import des scripts (tiret) via `importlib.util.spec_from_file_location` (cf. `digest.py`).

---

## Task 1 : Métriques + `eval_cases` + `auto_cases` + tests

**Files:**
- Create: `scripts/eval-recall.py`
- Create: `tests/test_eval_recall.py`

- [ ] **Step 1 : Écrire les tests (`tests/test_eval_recall.py`)**

```python
import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "scripts", "eval-recall.py")
SPEC = importlib.util.spec_from_file_location("eval_recall", SCRIPT)
er = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(er)


class MetricsTest(unittest.TestCase):
    def test_recall_at_k(self):
        self.assertTrue(er.recall_at_k(["a", "b", "c"], "b", 2))
        self.assertFalse(er.recall_at_k(["a", "b", "c"], "c", 2))   # au-delà de k
        self.assertFalse(er.recall_at_k(["a", "b"], "z", 2))         # absent

    def test_reciprocal_rank(self):
        self.assertEqual(er.reciprocal_rank(["a", "b", "c"], "a"), 1.0)
        self.assertAlmostEqual(er.reciprocal_rank(["a", "b", "c"], "c"), 1.0 / 3)
        self.assertEqual(er.reciprocal_rank(["a", "b"], "z"), 0.0)


class EvalCasesTest(unittest.TestCase):
    def test_aggregate(self):
        cases = [{"query": "q1", "expect": "a"}, {"query": "q2", "expect": "z"}]
        ranks = {"q1": ["a", "b"], "q2": ["x", "y"]}   # q1 -> rang 1 ; q2 -> raté
        rep = er.eval_cases(cases, lambda q: ranks[q], k=2)
        self.assertEqual(rep["n"], 2)
        self.assertEqual(rep["hits"], 1)
        self.assertEqual(rep["recall_pct"], 50)
        self.assertEqual(rep["mrr"], 0.5)            # (1.0 + 0) / 2
        self.assertEqual(rep["rank1"], 1)
        self.assertEqual(rep["misses"], [{"query": "q2", "expect": "z"}])

    def test_empty(self):
        rep = er.eval_cases([], lambda q: [], k=8)
        self.assertEqual(rep["n"], 0)
        self.assertEqual(rep["recall_pct"], 0)
        self.assertEqual(rep["mrr"], 0.0)


class AutoCasesTest(unittest.TestCase):
    def test_builds_cases_and_skips_no_description(self):
        facts = [{"name": "a", "description": "desc a"},
                 {"name": "b", "description": ""},        # ignoré
                 {"name": "c", "description": "desc c"}]
        cases = er.auto_cases(facts)
        self.assertEqual(cases, [{"query": "desc a", "expect": "a"},
                                 {"query": "desc c", "expect": "c"}])


class ReportTest(unittest.TestCase):
    def test_grep_warning_present(self):
        rep = {"n": 1, "hits": 1, "recall_pct": 100, "mrr": 1.0, "rank1": 1, "misses": []}
        out = er._format_report(rep, 8, vector_inactive=True)
        self.assertIn("fastembed absent", out)
        self.assertIn("recall@k", out)

    def test_semantic_no_warning_lists_misses(self):
        rep = {"n": 2, "hits": 1, "recall_pct": 50, "mrr": 0.5, "rank1": 1,
               "misses": [{"query": "q2", "expect": "z"}]}
        out = er._format_report(rep, 8, vector_inactive=False)
        self.assertNotIn("fastembed absent", out)
        self.assertIn("sémantique", out)
        self.assertIn("`z`", out)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2 : Lancer — échec attendu**

Run : `python3 -m unittest tests.test_eval_recall -v`
Expected : ERROR — `scripts/eval-recall.py` n'existe pas.

- [ ] **Step 3 : Écrire `scripts/eval-recall.py` (métriques + agrégation + rapport + auto_cases)**

```python
#!/usr/bin/env python3
"""Harnais d'évaluation du rappel : le bon fait remonte-t-il au bon moment ?

Mesure, pour des cas {query, expect}, si le fait attendu ressort dans le top-k via le VRAI chemin
de recherche (embed.search, comme search_memory). Métriques : recall@k, MRR, rang #1
(discriminabilité). Diagnostique (pas de seuil). Réutilise embed.py / build-viewer.py.

CLI :
  python3 eval-recall.py <vault> [--k 8]                 -> éval auto (description -> fait)
  python3 eval-recall.py <vault> --cases cas.json [--k 8] -> éval des cas fournis
"""
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_bv = _load("build_viewer", "build-viewer.py")
_embed = _load("embed", "embed.py")


def recall_at_k(ranked, expected, k):
    """Vrai si `expected` est dans les k premiers de `ranked`."""
    return expected in ranked[:k]


def reciprocal_rank(ranked, expected):
    """1/rang (1-indexé) si `expected` est trouvé, sinon 0.0."""
    for i, name in enumerate(ranked, start=1):
        if name == expected:
            return 1.0 / i
    return 0.0


def eval_cases(cases, query_fn, k):
    """Agrège l'éval sur des cas {query, expect}. `query_fn(query) -> [noms classés]`."""
    n = len(cases)
    hits = 0
    rr_sum = 0.0
    rank1 = 0
    misses = []
    for c in cases:
        ranked = query_fn(c["query"])
        expected = c["expect"]
        rr = reciprocal_rank(ranked, expected)
        rr_sum += rr
        if rr == 1.0:
            rank1 += 1
        if recall_at_k(ranked, expected, k):
            hits += 1
        else:
            misses.append({"query": c["query"], "expect": expected})
    return {
        "n": n,
        "hits": hits,
        "recall_pct": round(100 * hits / n) if n else 0,
        "mrr": round(rr_sum / n, 3) if n else 0.0,
        "rank1": rank1,
        "misses": misses,
    }


def auto_cases(facts):
    """Éval automatique : chaque fait -> {query: sa description, expect: son nom}.

    Ignore les faits sans description (rien à interroger)."""
    out = []
    for f in facts:
        desc = (f.get("description") or "").strip()
        name = f.get("name")
        if desc and name:
            out.append({"query": desc, "expect": name})
    return out


def _format_report(report, k, vector_inactive):
    lines = []
    if vector_inactive:
        lines.append("⚠ fastembed absent — recall mesuré en lexical (grep), proxy faible ; "
                     "lance /memory-doctor pour l'éval sémantique.")
    mode = "grep (proxy faible)" if vector_inactive else "sémantique"
    lines.append("Éval rappel — %d cas, k=%d, mode %s" % (report["n"], k, mode))
    lines.append("recall@k : %d/%d (%d%%)" % (report["hits"], report["n"], report["recall_pct"]))
    lines.append("MRR      : %.3f" % report["mrr"])
    lines.append("rang #1  : %d/%d (discriminabilité)" % (report["rank1"], report["n"]))
    if report["misses"]:
        lines.append("Ratés (fait absent du top-k) :")
        for m in report["misses"]:
            lines.append('- "%s" → attendu `%s`' % (m["query"], m["expect"]))
    return "\n".join(lines)


def search_query_fn(vault, k=8, embed_fn="auto"):
    """Renvoie (query_fn, vector_inactive) basé sur le VRAI chemin de recherche (embed.search).

    `embed_fn="auto"` charge fastembed si dispo (None -> repli grep). Injectable pour les tests."""
    facts, _ = _bv.collect_facts(vault, include_body=True)
    if embed_fn == "auto":
        embed_fn = _embed.load_fastembed_embed_fn()
    store = {}
    vector_inactive = embed_fn is None
    if embed_fn is not None:
        try:
            store = _embed.refresh_store(facts, {}, embed_fn)
        except Exception:
            embed_fn, store, vector_inactive = None, {}, True

    def query_fn(query):
        res = _embed.search(query, facts, store, embed_fn, k)
        return [r["name"] for r in res["results"]]

    return query_fn, vector_inactive


if __name__ == "__main__":
    argv = sys.argv[1:]
    k = 8
    cases_file = None
    positional = []
    i = 0
    while i < len(argv):
        if argv[i] == "--k" and i + 1 < len(argv):
            k = int(argv[i + 1]); i += 2
        elif argv[i] == "--cases" and i + 1 < len(argv):
            cases_file = argv[i + 1]; i += 2
        else:
            positional.append(argv[i]); i += 1
    vault = positional[0] if positional else "."
    query_fn, vector_inactive = search_query_fn(vault, k)
    if cases_file:
        with open(cases_file, encoding="utf-8") as fh:
            cases = json.load(fh)
    else:
        facts, _ = _bv.collect_facts(vault, include_body=False)
        cases = auto_cases(facts)
    report = eval_cases(cases, query_fn, k)
    print(_format_report(report, k, vector_inactive))
```

- [ ] **Step 4 : Lancer — succès attendu**

Run : `python3 -m unittest tests.test_eval_recall -v`
Expected : PASS (7 tests : MetricsTest×2, EvalCasesTest×2, AutoCasesTest×1, ReportTest×2).

- [ ] **Step 5 : Commit**

```bash
git add scripts/eval-recall.py tests/test_eval_recall.py
git commit -m "feat(eval): moteur d'éval du rappel (recall@k/MRR + eval_cases/auto_cases/recherche)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 : Test d'intégration de la recherche (mode grep) + fumée CLI

**Files:**
- Modify: `tests/test_eval_recall.py`

- [ ] **Step 1 : Ajouter le test d'intégration grep (`tests/test_eval_recall.py`)**

Ajouter cette classe **avant** le `if __name__ == "__main__":` final. Elle teste `search_query_fn`
en **mode grep forcé** (`embed_fn=None`, déterministe, sans fastembed) sur un petit vault.

```python
def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _fact(name, desc):
    return "---\nname: %s\ndescription: %s\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\n%s\n" % (
        name, desc, desc)


class SearchQueryFnTest(unittest.TestCase):
    def test_grep_mode_ranks_lexical_match(self):
        with tempfile.TemporaryDirectory() as v:
            _write(os.path.join(v, "mailing", "relance-j3.md"),
                   _fact("relance-j3", "relancer les paniers abandonnés après 72 heures"))
            _write(os.path.join(v, "facturation", "tva.md"),
                   _fact("tva", "taux de TVA à vingt pour cent"))
            query_fn, vector_inactive, _facts = er.search_query_fn(v, k=8, embed_fn=None)
            self.assertTrue(vector_inactive)                       # grep forcé
            ranked = query_fn("paniers abandonnés relance")
            self.assertIn("relance-j3", ranked)                    # le fait pertinent ressort

    def test_auto_eval_end_to_end_grep(self):
        with tempfile.TemporaryDirectory() as v:
            _write(os.path.join(v, "mailing", "relance-j3.md"),
                   _fact("relance-j3", "relancer les paniers abandonnés après 72 heures"))
            query_fn, _vi, facts = er.search_query_fn(v, k=8, embed_fn=None)
            rep = er.eval_cases(er.auto_cases(facts), query_fn, k=8)
            self.assertEqual(rep["n"], 1)
            self.assertEqual(rep["hits"], 1)                       # description -> son fait (grep)
```

- [ ] **Step 2 : Lancer — succès attendu**

Run : `python3 -m unittest tests.test_eval_recall -v`
Expected : PASS (les précédents + 2 d'intégration).

- [ ] **Step 3 : Fumée CLI (auto)**

Run :
```bash
TMP=$(mktemp -d); mkdir -p "$TMP/mailing"
printf -- '---\nname: relance-j3\ndescription: relancer les paniers abandonnés après 72 heures\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\nx\n' > "$TMP/mailing/relance-j3.md"
python3 scripts/eval-recall.py "$TMP"
rm -rf "$TMP"
```
Expected : un rapport « Éval rappel — 1 cas… » avec `recall@k : 1/1 (100%)` (sémantique si fastembed
présent, sinon grep avec l'avertissement).

- [ ] **Step 4 : Commit**

```bash
git add tests/test_eval_recall.py
git commit -m "test(eval): intégration recherche grep + éval auto bout-en-bout

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 : Skill `/memory-eval`

**Files:**
- Create: `skills/memory-eval/SKILL.md`

- [ ] **Step 1 : Écrire `skills/memory-eval/SKILL.md`**

```markdown
---
name: memory-eval
description: This skill should be used when the user asks to "évaluer le rappel", "tester la recherche mémoire", "mesurer la qualité du rappel", "le bon fait remonte-t-il", "evaluate recall", "test memory search quality", or "/memory-eval". It measures whether the right fact surfaces for realistic queries (recall@k, MRR) via the real search path, and points to remediation.
argument-hint: ""
allowed-tools: Bash, Read, Write
version: 0.1.0
---

# memory-eval — Évaluer la qualité du rappel

Mesure si **le bon fait remonte au bon moment** : pour des requêtes réalistes, le fait attendu
ressort-il dans le **top-k** ? Métriques `recall@k`, `MRR`, `rang #1` (discriminabilité), via le
**vrai** chemin de recherche (`search_memory`). **Lecture seule** : diagnostique, n'écrit aucun fait.

## Procédure

1. **Localiser le vault** du projet courant :

   ```bash
   bash -c 'source ${CLAUDE_PLUGIN_ROOT%/}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
   ```

   Si rien n'est renvoyé, demander de lancer `/memory-setup` d'abord.

2. **Générer des requêtes réalistes** : lire les faits (nom + description) du vault. Pour chaque
   fait, formuler **1-2 requêtes** telles qu'un humain les poserait (questions / mots-clés métier,
   **pas** la description recopiée). Écrire un fichier `cas.json` (dans un tmp) au format
   `[{"query": "<requête>", "expect": "<name-du-fait>"}]` (avec **Write**).

3. **Lancer l'éval** :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/eval-recall.py "<clone>" --cases "<cas.json>"
   ```

4. **Présenter** le rapport : `recall@k`, `MRR`, `rang #1`, et la **liste des ratés** (faits absents
   du top-k). Pour chaque raté ou faiblesse, proposer une **piste** :
   - description peu discriminante → **`/memory-lint`** (signale les descriptions courtes) ;
   - deux faits confusables (l'un masque l'autre) → **dédup** / fusion ;
   - rapport en mode **grep** (fastembed absent) → **`/memory-doctor`** pour l'éval sémantique ;
   - fait douteux/périmé → **`/memory-refresh`**.

5. **Comparaison auto (optionnel)** : `python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/eval-recall.py "<clone>"`
   (sans `--cases`) donne la base « chaque description retrouve-t-elle son fait ? » (retrievabilité /
   confusabilité), utile pour repérer les doublons.

## Points d'attention

- **Lecture seule** : ce skill **mesure**, il ne modifie aucun fait ; la remédiation passe par les
  autres skills.
- **Requêtes réalistes** : ne pas recopier la description (l'éval deviendrait triviale) ; varier les
  formulations comme un vrai utilisateur.
- **Mode grep** : sans fastembed, le recall est un proxy lexical faible — le rapport l'indique.

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/scripts/eval-recall.py`** — moteur d'éval (recall@k / MRR / ratés).
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — résolution du vault.
- **`/memory-lint`**, **`/memory-doctor`**, **`/memory-refresh`** — remédiations selon le diagnostic.
```

- [ ] **Step 2 : Vérifier le frontmatter**

Run :
```bash
head -7 skills/memory-eval/SKILL.md
grep -c "^name: memory-eval" skills/memory-eval/SKILL.md
```
Expected : frontmatter présent ; `grep` renvoie `1`.

- [ ] **Step 3 : Commit**

```bash
git add skills/memory-eval/SKILL.md
git commit -m "feat(eval): skill /memory-eval — mesurer le rappel (paraphrases LLM + interprétation)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 : Documentation

**Files:**
- Modify: `README.md`
- Modify: `INSTALL.md`
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1 : README — tableau des skills**

Dans `README.md`, dans le tableau « ### Skills », après la ligne `| `/memory-refresh` | … |`, insérer :

```markdown
| `/memory-eval` | **mesurer le rappel** : le bon fait remonte-t-il (recall@k, MRR) pour des requêtes réalistes |
```

- [ ] **Step 2 : README — puce « Sous le capot »**

Dans `README.md`, section « ### Sous le capot », après la puce « 🔁 Re-vérification », insérer :

```markdown
- **📊 Éval du rappel (`/memory-eval`)** — mesure si le bon fait remonte au bon moment (`recall@k`,
  `MRR`, discriminabilité) via le vrai chemin de recherche. Les ratés orientent la remédiation
  (description, dédup, fastembed). On **mesure** la valeur, on ne la suppose pas.
```

- [ ] **Step 3 : INSTALL — commandes utiles**

Dans `INSTALL.md`, dans le tableau « Commandes utiles », après la ligne `| `/memory-refresh` | … |`, insérer :

```markdown
| `/memory-eval` | mesurer la qualité du rappel (recall@k, MRR) sur des requêtes réalistes |
```

- [ ] **Step 4 : ARCHITECTURE — nouvelle section §17**

Dans `docs/ARCHITECTURE.md`, à la **fin du fichier** (après §16), ajouter :

```markdown
## 17. Évaluation du rappel

Tout vise à ce que **le bon fait remonte au bon moment** ; `scripts/eval-recall.py` le **mesure**.
Pour des cas `{query, expect}`, il interroge le **vrai** chemin de recherche (`embed.search`, comme
`search_memory`) et calcule **`recall@k`** (le fait attendu est-il dans le top-k ?), **`MRR`** (à
quelle hauteur ?) et **`rang #1`** (discriminabilité : un fait souvent masqué par un autre = descriptions
confusables).

- **`auto_cases`** : éval automatique (chaque description sert de requête → son fait doit ressortir)
  — repère la retrievabilité et les doublons.
- **`/memory-eval`** : Claude génère des **requêtes réalistes** par fait (pas la description brute) →
  éval → **ratés** + pistes de remédiation (`/memory-lint` pour les descriptions, dédup pour les
  confusables, `/memory-doctor` pour activer fastembed, `/memory-refresh` pour les faits périmés).

L'éval est **diagnostique** (pas de seuil/gating) et **honnête** : en repli **grep** (sans fastembed),
le recall est un proxy lexical faible, signalé dans le rapport. Le moteur est **lecture seule**.
```

- [ ] **Step 5 : Vérifier**

Run : `grep -c "memory-eval" README.md INSTALL.md docs/ARCHITECTURE.md`
Expected : chaque fichier ≥ 1.

- [ ] **Step 6 : Commit**

```bash
git add README.md INSTALL.md docs/ARCHITECTURE.md
git commit -m "docs(eval): documenter /memory-eval + eval-recall.py (README/INSTALL/ARCHITECTURE)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 : Vérification

- [ ] **Step 1 : Suite complète (non-régression)**

Run : `python3 -m unittest discover -s . -p 'test_*.py' 2>&1 | tail -3`
Expected : OK — tous les tests passent (existants + ~9 de `test_eval_recall`).

- [ ] **Step 2 : Fumée bout-en-bout (auto + cas)**

Run :
```bash
TMP=$(mktemp -d); mkdir -p "$TMP/mailing" "$TMP/facturation"
printf -- '---\nname: relance-j3\ndescription: relancer les paniers abandonnés après 72 heures\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\nx\n' > "$TMP/mailing/relance-j3.md"
printf -- '---\nname: tva\ndescription: taux de TVA à vingt pour cent sur les prestations\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\nx\n' > "$TMP/facturation/tva.md"
echo "=== auto ===" ; python3 scripts/eval-recall.py "$TMP"
CAS="$TMP/cas.json"
printf '[{"query":"comment relancer un panier abandonné","expect":"relance-j3"},{"query":"quel taux de tva","expect":"tva"}]' > "$CAS"
echo "=== cas réalistes ===" ; python3 scripts/eval-recall.py "$TMP" --cases "$CAS"
rm -rf "$TMP"
```
Expected : deux rapports « Éval rappel … » avec `recall@k` calculé (le mode dépend de la présence de
fastembed ; en grep, l'avertissement apparaît).

- [ ] **Step 3 : Relecture**

Vérifier de visu : `eval-recall.py` réutilise `embed.search` (vrai chemin) ; `eval_cases` a un
`query_fn` injectable (testé en stub et en grep) ; le skill `/memory-eval` est **lecture seule** et
génère des requêtes réalistes (pas la description brute) ; doc §17 cohérente.

---

## Self-Review

**Couverture de la spec :**

| Élément du design | Tâche |
|---|---|
| `recall_at_k`, `reciprocal_rank`, `eval_cases`, `auto_cases` | Task 1 + tests |
| `search_query_fn` (vrai chemin de recherche, `embed_fn` injectable) | Task 1 + test grep (Task 2) |
| Rapport (recall@k/MRR/rang #1/ratés) + avertissement grep | Task 1 (`_format_report`) + ReportTest |
| CLI auto / `--cases` | Task 1 + fumée (Task 2/5) |
| Skill `/memory-eval` (paraphrases LLM, lecture seule, interprétation) | Task 3 |
| Doc (README/INSTALL/ARCHITECTURE §17) | Task 4 |
| Tests (métriques, eval_cases stub, auto_cases, recherche grep, intégration) | Task 1, Task 2, Task 5 |

**Placeholders :** aucun — `eval-recall.py`, `test_eval_recall.py` (deux lots), le `SKILL.md` et les
edits doc sont fournis intégralement.

**Cohérence des types/signatures :** `recall_at_k(ranked, expected, k) -> bool`,
`reciprocal_rank(ranked, expected) -> float`, `eval_cases(cases, query_fn, k) -> dict`
(clés `{n,hits,recall_pct,mrr,rank1,misses}`), `auto_cases(facts) -> list[dict]`,
`search_query_fn(vault, k, embed_fn) -> (query_fn, bool)`, `_format_report(report, k, vector_inactive)
-> str` — mêmes signatures dans le moteur, les tests et la CLI. `embed.search(...)["results"][i]["name"]`
est la clé utilisée pour le classement (cohérent avec `_pointer`). Le test force `embed_fn=None`
(grep déterministe) ; la CLI utilise `"auto"` (fastembed si dispo).
