# Plan V2-B — `search_memory` (MCP vectoriel) + Doctor (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner à Claude un outil MCP `search_memory(query, k)` qui court-circuite la lecture des index et renvoie des **pointeurs** de faits (jamais de body), via une recherche vectorielle **locale et optionnelle** (fastembed) avec **fallback grep** ; plus un **Doctor** qui diagnostique les prérequis et propose les installs, sans jamais dégrader en silence.

**Architecture :** Cœur pur et testable dans `scripts/embed.py` (l'`embed_fn` est **injecté** — aucun import fastembed au niveau module ; la suite passe **sans** installer fastembed). `scripts/sm_paths.py` reflète `lib.sh` en Python (slug, registre, store). `scripts/mcp-server.py` est un serveur **JSON-RPC 2.0 stdio minimal en stdlib pur** qui réutilise `collect_facts` (de `build-viewer.py`) + `embed.py`. `scripts/doctor.py` rend un rapport structuré à sondes injectables. Store d'embeddings **hors vault** (`~/.shared-memory/embeddings/<slug>/index.json`), fraîcheur **lazy par hash**.

**Tech Stack :** Python 3 stdlib (json, hashlib, math, importlib, http jamais). Dépendance **optionnelle** : `fastembed` (ONNX local). Tests : `unittest` (pattern `importlib.util` déjà en place dans `tests/`).

**Référence design :** `docs/superpowers/specs/2026-06-10-v2-token-optimization-design.md` (Volets **B** et **C**). Le Volet A (index compact) est livré (Plan V2-A, mergé). Ce plan **ne dépend pas** de fastembed étant présent : à la livraison, `search_memory` tourne en **fallback grep** ; le vectoriel s'active après `pip install fastembed` (que `/memory-doctor` proposera).

**Principe non négociable :** l'outil **aiguille**, le fait est la **source**. `search_memory` ne renvoie **jamais** de body ni de résumé — uniquement `{file, name, path, score}`. Toute affirmation vient du fait lu ensuite.

---

## File Structure

| Fichier | Responsabilité | Action |
|---|---|---|
| `scripts/sm_paths.py` | Slug projet (miroir `lib.sh`), chemin registre, résolution vault, chemin du store. Pur, sans I/O réseau. | Créer |
| `scripts/embed.py` | Cœur recherche : `fact_text`/`content_hash`, store (`load`/`save`/`refresh_store` lazy par hash), `cosine`/`semantic_topk`, `grep_matches`, `search` hybride, `load_fastembed_embed_fn` (import gardé). | Créer |
| `scripts/mcp-server.py` | Serveur MCP stdio (JSON-RPC 2.0 stdlib) : `initialize`/`tools/list`/`tools/call`→`search_memory`. `handle_request` injecte le runner (testable). | Créer |
| `.mcp.json` | Déclare le serveur MCP du plugin (auto-découvert par Claude Code). | Créer |
| `scripts/doctor.py` | Diagnostic structuré (python, fastembed, modèle, `.mcp.json`) avec remède par manque. Sondes injectables. | Créer |
| `skills/memory-doctor/SKILL.md` | Lance le doctor, présente le diagnostic, **propose** les installs (l'utilisateur valide). | Créer |
| `skills/memory-setup/SKILL.md` | Appelle le doctor en fin de configuration. | Modifier |
| `README.md` | Ajoute `/memory-doctor` au tableau des skills + `.mcp.json` à la structure. | Modifier |
| `tests/test_sm_paths.py`, `tests/test_embed.py`, `tests/test_mcp_server.py`, `tests/test_doctor.py` | Couverture unittest. | Créer |

**Hors scope (rappel design) :** ré-embedding distribué / index vectoriel partagé (le store reste local par-machine) ; re-ranking cross-encoder (seulement si le top-k devient limitant).

---

# Partie B — `search_memory`

## Task 1 : `scripts/sm_paths.py` — slug, registre, store (miroir Python de `lib.sh`)

**Files:**
- Create: `scripts/sm_paths.py`
- Test: `tests/test_sm_paths.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `tests/test_sm_paths.py` :

```python
import importlib.util
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "sm_paths", os.path.join(HERE, "..", "scripts", "sm_paths.py"))
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


class SlugTest(unittest.TestCase):
    def test_slug_matches_libsh_rule(self):
        # runs non-alphanumériques -> '-', y compris le '/' de tête
        self.assertEqual(P.slug("/var/www/newnegocian-workspace"),
                         "-var-www-newnegocian-workspace")


class RegistryTest(unittest.TestCase):
    def test_vault_clone_for_slug_found(self):
        with tempfile.TemporaryDirectory() as d:
            reg = os.path.join(d, "registry.json")
            with open(reg, "w", encoding="utf-8") as f:
                json.dump({"projets": [{"slug": "-p", "clone": "/clones/p"}]}, f)
            self.assertEqual(P.vault_clone_for_slug("-p", registry=reg), "/clones/p")

    def test_vault_clone_for_slug_absent_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            reg = os.path.join(d, "registry.json")
            with open(reg, "w", encoding="utf-8") as f:
                json.dump({"projets": []}, f)
            self.assertIsNone(P.vault_clone_for_slug("-x", registry=reg))

    def test_missing_registry_returns_none(self):
        self.assertIsNone(P.vault_clone_for_slug("-p", registry="/no/such/file.json"))


class StorePathTest(unittest.TestCase):
    def test_store_path_under_shared_memory(self):
        sp = P.store_path_for_slug("-p")
        self.assertTrue(sp.endswith(os.path.join(".shared-memory", "embeddings", "-p", "index.json")))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `python3 -m unittest tests.test_sm_paths -v`
Expected : FAIL — `No module named` / `module_from_spec` lève `FileNotFoundError` (fichier `scripts/sm_paths.py` absent).

- [ ] **Step 3 : Écrire l'implémentation minimale**

Créer `scripts/sm_paths.py` :

```python
#!/usr/bin/env python3
"""Chemins & résolution vault — miroir Python de lib.sh (slug, registre, store d'embeddings)."""
import json
import os
import re


def slug(directory):
    """Runs non-alphanumériques -> '-' (identique à sm_slug de lib.sh)."""
    return re.sub(r"[^a-zA-Z0-9]+", "-", directory)


def config_dir():
    return os.environ.get(
        "SM_CONFIG_DIR",
        os.path.join(os.path.expanduser("~"), ".config", "shared-memory"))


def registry_path():
    return os.environ.get("SM_REGISTRY", os.path.join(config_dir(), "registry.json"))


def vault_clone_for_slug(s, registry=None):
    """Chemin du clone pour un slug, lu dans le registre. None si introuvable."""
    path = registry or registry_path()
    try:
        with open(path, encoding="utf-8") as f:
            reg = json.load(f)
    except (OSError, ValueError):
        return None
    for p in reg.get("projets", []):
        if p.get("slug") == s:
            return p.get("clone") or None
    return None


def embeddings_root():
    return os.path.join(os.path.expanduser("~"), ".shared-memory", "embeddings")


def store_path_for_slug(s):
    """Store d'embeddings HORS vault, reconstructible : ~/.shared-memory/embeddings/<slug>/index.json."""
    return os.path.join(embeddings_root(), s, "index.json")
```

- [ ] **Step 4 : Lancer le test, vérifier le succès**

Run : `python3 -m unittest tests.test_sm_paths -v`
Expected : PASS (5 tests).

- [ ] **Step 5 : Commit**

```bash
git add scripts/sm_paths.py tests/test_sm_paths.py
git commit -m "feat(embed): sm_paths — slug/registre/store (miroir Python de lib.sh)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 : `scripts/embed.py` — store + fraîcheur lazy par hash

**Files:**
- Create: `scripts/embed.py`
- Test: `tests/test_embed.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `tests/test_embed.py` (un `embed_fn` **factice déterministe** : aucune dépendance) :

```python
import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "embed", os.path.join(HERE, "..", "scripts", "embed.py"))
E = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E)


def fake_embed_fn(texts):
    """Vecteur déterministe 3D : longueur, nb 'a', nb 'e'. Suffisant pour la plomberie."""
    return [[float(len(t)), float(t.count("a")), float(t.count("e"))] for t in texts]


def fact(file, name, desc, body):
    return {"file": file, "name": name, "description": desc, "body": body, "path": file.split("/")[:-1]}


class StoreFreshnessTest(unittest.TestCase):
    def test_refresh_embeds_all_first_time(self):
        facts = [fact("d/a.md", "a", "da", "corps a"), fact("d/b.md", "b", "db", "corps b")]
        store = E.refresh_store(facts, {}, fake_embed_fn)
        self.assertEqual(set(store), {"d/a.md", "d/b.md"})
        self.assertIn("vec", store["d/a.md"])
        self.assertIn("hash", store["d/a.md"])

    def test_unchanged_fact_is_not_reembedded(self):
        facts = [fact("d/a.md", "a", "da", "corps a")]
        store = E.refresh_store(facts, {}, fake_embed_fn)
        calls = []
        def counting(texts):
            calls.append(texts); return fake_embed_fn(texts)
        store2 = E.refresh_store(facts, store, counting)
        self.assertEqual(calls, [])                 # rien à ré-embedder
        self.assertEqual(store2, store)

    def test_changed_body_triggers_reembed(self):
        facts = [fact("d/a.md", "a", "da", "corps a")]
        store = E.refresh_store(facts, {}, fake_embed_fn)
        facts[0]["body"] = "corps a modifié"
        store2 = E.refresh_store(facts, store, fake_embed_fn)
        self.assertNotEqual(store2["d/a.md"]["hash"], store["d/a.md"]["hash"])

    def test_deleted_fact_drops_from_store(self):
        facts = [fact("d/a.md", "a", "da", "x"), fact("d/b.md", "b", "db", "y")]
        store = E.refresh_store(facts, {}, fake_embed_fn)
        store2 = E.refresh_store(facts[:1], store, fake_embed_fn)
        self.assertEqual(set(store2), {"d/a.md"})

    def test_save_then_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "index.json")
            store = {"d/a.md": {"hash": "h", "vec": [1.0, 2.0]}}
            E.save_store(path, store)
            self.assertEqual(E.load_store(path), store)

    def test_load_missing_store_is_empty(self):
        self.assertEqual(E.load_store("/no/such/store.json"), {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `python3 -m unittest tests.test_embed -v`
Expected : FAIL — `scripts/embed.py` absent (`FileNotFoundError` au chargement du module).

- [ ] **Step 3 : Écrire l'implémentation minimale**

Créer `scripts/embed.py` avec **uniquement** ce dont les tests ci-dessus ont besoin (le reste vient aux Tasks 3-5) :

```python
#!/usr/bin/env python3
"""Recherche mémoire : embeddings locaux OPTIONNELS + hybride grep.

Cœur pur et testable : `embed_fn` est INJECTÉ (aucun import fastembed au niveau module).
embed_fn(list[str]) -> list[list[float]]. Si embed_fn is None, `search` (Task 4) retombe
sur le grep et signale vector_inactive.
"""
import hashlib
import json
import math
import os


def fact_text(fact):
    """Texte embeddé/hashé d'un fait : name + description + body."""
    return "\n".join((fact.get("name", ""), fact.get("description", ""), fact.get("body", "")))


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_store(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_store(path, store):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f)
    os.replace(tmp, path)


def refresh_store(facts, store, embed_fn):
    """Store à jour {file: {hash, vec}} ; ne (ré)embedde que les hash changés (lazy).
    Les faits disparus sortent du store. embed_fn(list[str]) -> list[list[float]]."""
    fresh, to_embed, keys = {}, [], []
    for fact in facts:
        h = content_hash(fact_text(fact))
        prev = store.get(fact["file"])
        if prev and prev.get("hash") == h and "vec" in prev:
            fresh[fact["file"]] = prev
        else:
            to_embed.append(fact_text(fact))
            keys.append((fact["file"], h))
    if to_embed:
        vecs = embed_fn(to_embed)
        for (file, h), vec in zip(keys, vecs):
            fresh[file] = {"hash": h, "vec": [float(x) for x in vec]}
    return fresh
```

- [ ] **Step 4 : Lancer le test, vérifier le succès**

Run : `python3 -m unittest tests.test_embed -v`
Expected : PASS (6 tests).

- [ ] **Step 5 : Commit**

```bash
git add scripts/embed.py tests/test_embed.py
git commit -m "feat(embed): store d'embeddings + fraîcheur lazy par hash

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 : `scripts/embed.py` — cosine + top-k sémantique

**Files:**
- Modify: `scripts/embed.py`
- Test: `tests/test_embed.py`

- [ ] **Step 1 : Ajouter les tests qui échouent**

Ajouter dans `tests/test_embed.py` (avant le `if __name__`) :

```python
class CosineTopkTest(unittest.TestCase):
    def test_cosine_identical_is_one(self):
        self.assertAlmostEqual(E.cosine([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]), 1.0, places=6)

    def test_cosine_orthogonal_is_zero(self):
        self.assertAlmostEqual(E.cosine([1.0, 0.0], [0.0, 1.0]), 0.0, places=6)

    def test_cosine_zero_vector_is_zero(self):
        self.assertEqual(E.cosine([0.0, 0.0], [1.0, 1.0]), 0.0)

    def test_topk_orders_by_score_and_limits(self):
        store = {
            "a": {"vec": [1.0, 0.0]},
            "b": {"vec": [0.9, 0.1]},
            "c": {"vec": [0.0, 1.0]},
        }
        top = E.semantic_topk([1.0, 0.0], store, k=2)
        self.assertEqual([f for f, _ in top], ["a", "b"])
        self.assertEqual(len(top), 2)
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `python3 -m unittest tests.test_embed.CosineTopkTest -v`
Expected : FAIL — `module 'embed' has no attribute 'cosine'`.

- [ ] **Step 3 : Implémenter**

Ajouter à `scripts/embed.py` (après `refresh_store`) :

```python
def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)


def semantic_topk(query_vec, store, k):
    """Top-k (file, score) par cosine décroissant."""
    scored = [(file, cosine(query_vec, rec["vec"]))
              for file, rec in store.items() if "vec" in rec]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:k]
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `python3 -m unittest tests.test_embed -v`
Expected : PASS (9 tests cumulés).

- [ ] **Step 5 : Commit**

```bash
git add scripts/embed.py tests/test_embed.py
git commit -m "feat(embed): cosine brute-force + top-k sémantique

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 : `scripts/embed.py` — recherche hybride + fallback grep

**Files:**
- Modify: `scripts/embed.py`
- Test: `tests/test_embed.py`

La recherche renvoie **des pointeurs** `{file, name, path, score}` (jamais de body) et un drapeau `vector_inactive`. Le grep réutilise la logique de `/search` du viewer (`serve-viewer.py:55-64`).

- [ ] **Step 1 : Ajouter les tests qui échouent**

Ajouter dans `tests/test_embed.py` :

```python
class SearchHybridTest(unittest.TestCase):
    def _facts(self):
        return [
            fact("mailing/a.md", "relance-j3", "relance paniers 72h", "corps relance"),
            fact("mailing/b.md", "objet-ab", "ab test objets", "corps objet"),
            fact("ecommerce/c.md", "tva", "taux tva", "corps fiscal"),
        ]

    def test_grep_only_when_embed_fn_none(self):
        facts = self._facts()
        out = E.search("relance", facts, store={}, embed_fn=None, k=8)
        self.assertTrue(out["vector_inactive"])
        files = [r["file"] for r in out["results"]]
        self.assertIn("mailing/a.md", files)
        # pointeurs uniquement : jamais de body
        self.assertTrue(all("body" not in r for r in out["results"]))
        self.assertEqual(set(out["results"][0]), {"file", "name", "path", "score"})

    def test_hybrid_unions_semantic_and_grep(self):
        facts = self._facts()
        store = E.refresh_store(facts, {}, fake_embed_fn)
        # embed_fn factice : la query 'tva' matche c.md par grep ; le sémantique ajoute d'autres
        out = E.search("tva", facts, store, embed_fn=fake_embed_fn, k=8)
        self.assertFalse(out["vector_inactive"])
        files = [r["file"] for r in out["results"]]
        self.assertIn("ecommerce/c.md", files)          # garanti par le grep exact
        self.assertEqual(len(files), len(set(files)))     # dédupliqué

    def test_results_carry_name_and_path(self):
        facts = self._facts()
        out = E.search("relance", facts, store={}, embed_fn=None, k=8)
        r = next(r for r in out["results"] if r["file"] == "mailing/a.md")
        self.assertEqual(r["name"], "relance-j3")
        self.assertEqual(r["path"], ["mailing"])
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `python3 -m unittest tests.test_embed.SearchHybridTest -v`
Expected : FAIL — `module 'embed' has no attribute 'search'`.

- [ ] **Step 3 : Implémenter**

Ajouter à `scripts/embed.py` :

```python
def grep_matches(query, facts):
    """Fichiers dont name+description+body contient `query` (insensible casse).
    Même logique que /search du viewer (serve-viewer.py)."""
    q = (query or "").strip().lower()
    if not q:
        return []
    out = []
    for f in facts:
        hay = " ".join((f.get("name", ""), f.get("description", ""), f.get("body", ""))).lower()
        if q in hay:
            out.append(f["file"])
    return out


def _pointer(fact, score):
    return {"file": fact["file"], "name": fact.get("name", ""),
            "path": fact.get("path", []), "score": score}


def search(query, facts, store, embed_fn, k=8):
    """Recherche hybride -> {"results": [pointeurs], "vector_inactive": bool}.

    - embed_fn None : grep seul, vector_inactive=True.
    - embed_fn fourni : top-k sémantique PUIS union des matches grep exacts, dédupliqué
      (exhaustivité : un terme exact présent n'est jamais raté).
    Ne renvoie JAMAIS de body : l'outil aiguille, le fait est la source.
    """
    by_file = {f["file"]: f for f in facts}
    grep_files = grep_matches(query, facts)
    if embed_fn is None:
        results = [_pointer(by_file[fp], None) for fp in grep_files if fp in by_file]
        return {"results": results, "vector_inactive": True}
    qvec = embed_fn([query])[0]
    ordered, seen = [], set()
    for file, score in semantic_topk(qvec, store, k):
        if file in by_file and file not in seen:
            ordered.append(_pointer(by_file[file], round(score, 4)))
            seen.add(file)
    for fp in grep_files:
        if fp in by_file and fp not in seen:
            ordered.append(_pointer(by_file[fp], None))
            seen.add(fp)
    return {"results": ordered, "vector_inactive": False}
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `python3 -m unittest tests.test_embed -v`
Expected : PASS (12 tests cumulés).

- [ ] **Step 5 : Commit**

```bash
git add scripts/embed.py tests/test_embed.py
git commit -m "feat(embed): recherche hybride (sémantique ∪ grep) renvoyant des pointeurs

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 : `scripts/embed.py` — chargeur fastembed à import gardé

**Files:**
- Modify: `scripts/embed.py`
- Test: `tests/test_embed.py`

L'unique point qui touche fastembed. Import **dans la fonction** (jamais au niveau module) → la suite reste dep-free. Sur cette machine fastembed est **absent** : le test vérifie le **retour None sans exception**.

- [ ] **Step 1 : Ajouter le test qui échoue**

Ajouter dans `tests/test_embed.py` :

```python
class FastembedLoaderTest(unittest.TestCase):
    def test_loader_returns_callable_or_none_never_raises(self):
        fn = E.load_fastembed_embed_fn()
        self.assertTrue(fn is None or callable(fn))
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `python3 -m unittest tests.test_embed.FastembedLoaderTest -v`
Expected : FAIL — `module 'embed' has no attribute 'load_fastembed_embed_fn'`.

- [ ] **Step 3 : Implémenter**

Ajouter à `scripts/embed.py` :

```python
def load_fastembed_embed_fn():
    """Renvoie un embed_fn fastembed, ou None si fastembed indisponible.
    Import GARDÉ : aucune dépendance au niveau module ; ne lève jamais."""
    try:
        from fastembed import TextEmbedding
    except Exception:
        return None
    try:
        model = TextEmbedding()  # modèle par défaut (~90 Mo), téléchargé/caché localement
    except Exception:
        return None
    def embed_fn(texts):
        return [[float(x) for x in v] for v in model.embed(list(texts))]
    return embed_fn
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `python3 -m unittest tests.test_embed -v`
Expected : PASS (13 tests). Sur cette machine, `load_fastembed_embed_fn()` renvoie `None` (fastembed absent) sans erreur.

- [ ] **Step 5 : Commit**

```bash
git add scripts/embed.py tests/test_embed.py
git commit -m "feat(embed): chargeur fastembed à import gardé (None si absent)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 : `scripts/mcp-server.py` — dispatch JSON-RPC (testable)

**Files:**
- Create: `scripts/mcp-server.py`
- Test: `tests/test_mcp_server.py`

Le serveur MCP stdio minimal. On sépare le **dispatch** (`handle_request`, pur, runner injecté) de l'**I/O** (boucle `main`, Task 7) pour le tester sans process ni vault.

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `tests/test_mcp_server.py` :

```python
import importlib.util
import json
import os
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "mcp_server", os.path.join(HERE, "..", "scripts", "mcp-server.py"))
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def fake_runner(query, k):
    return {"results": [{"file": "d/a.md", "name": "a", "path": ["d"], "score": 0.5}],
            "vector_inactive": False, "echo": [query, k]}


class HandleRequestTest(unittest.TestCase):
    def test_initialize_echoes_protocol_and_serverinfo(self):
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2025-06-18"}}
        resp = M.handle_request(req, fake_runner)
        self.assertEqual(resp["id"], 1)
        self.assertEqual(resp["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(resp["result"]["serverInfo"]["name"], "shared-memory")
        self.assertIn("tools", resp["result"]["capabilities"])

    def test_initialized_notification_returns_none(self):
        self.assertIsNone(M.handle_request(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}, fake_runner))

    def test_tools_list_exposes_search_memory(self):
        resp = M.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, fake_runner)
        names = [t["name"] for t in resp["result"]["tools"]]
        self.assertEqual(names, ["search_memory"])
        self.assertIn("query", resp["result"]["tools"][0]["inputSchema"]["properties"])

    def test_tools_call_runs_search_and_wraps_text(self):
        req = {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
               "params": {"name": "search_memory", "arguments": {"query": "relance", "k": 5}}}
        resp = M.handle_request(req, fake_runner)
        payload = json.loads(resp["result"]["content"][0]["text"])
        self.assertEqual(payload["echo"], ["relance", 5])
        self.assertEqual(payload["results"][0]["file"], "d/a.md")
        self.assertNotIn("body", payload["results"][0])

    def test_unknown_tool_is_error(self):
        req = {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
               "params": {"name": "nope", "arguments": {}}}
        resp = M.handle_request(req, fake_runner)
        self.assertIn("error", resp)

    def test_unknown_method_is_error(self):
        resp = M.handle_request({"jsonrpc": "2.0", "id": 5, "method": "foo/bar"}, fake_runner)
        self.assertEqual(resp["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `python3 -m unittest tests.test_mcp_server -v`
Expected : FAIL — `scripts/mcp-server.py` absent.

- [ ] **Step 3 : Écrire l'implémentation minimale (dispatch + outil, sans I/O ni vault)**

Créer `scripts/mcp-server.py` :

```python
#!/usr/bin/env python3
"""Serveur MCP (stdio) exposant `search_memory` pour Claude Code.

Renvoie des POINTEURS de faits (jamais de body) : l'outil aiguille, le fait est la source.
Sémantique optionnelle (fastembed) ; fallback grep si absente (vector_inactive=true).
JSON-RPC 2.0 minimal, newline-delimited, stdlib pur.
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


PROTOCOL_VERSION = "2025-06-18"
TOOL = {
    "name": "search_memory",
    "description": (
        "Cherche des FAITS dans la mémoire d'équipe du projet et renvoie des POINTEURS "
        "(file, name, path, score) — JAMAIS le contenu. Lis ensuite chaque fait pointé avant "
        "d'affirmer quoi que ce soit : l'outil aiguille, le fait est la source. Si "
        "vector_inactive=true, la recherche sémantique est inactive (fallback grep) — signale-le "
        "à l'utilisateur et propose `pip install fastembed`."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Termes ou question."},
            "k": {"type": "integer", "description": "Nb de pointeurs (défaut 8).", "default": 8},
        },
        "required": ["query"],
    },
}


def handle_request(req, runner):
    """Dispatch JSON-RPC. `runner(query, k) -> dict` exécute la recherche (injecté → testable).
    Renvoie un dict réponse, ou None pour une notification (pas de réponse)."""
    method = req.get("method")
    rid = req.get("id")
    if method == "initialize":
        client_pv = (req.get("params") or {}).get("protocolVersion", PROTOCOL_VERSION)
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": client_pv,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "shared-memory", "version": "0.1.0"},
        }}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": [TOOL]}}
    if method == "tools/call":
        params = req.get("params") or {}
        if params.get("name") != "search_memory":
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32602, "message": "unknown tool"}}
        args = params.get("arguments") or {}
        out = runner(args.get("query", ""), int(args.get("k", 8) or 8))
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}]
        }}
    if rid is None:
        return None
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": "method not found: %s" % method}}
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `python3 -m unittest tests.test_mcp_server -v`
Expected : PASS (6 tests).

- [ ] **Step 5 : Commit**

```bash
git add scripts/mcp-server.py tests/test_mcp_server.py
git commit -m "feat(mcp): dispatch JSON-RPC + outil search_memory (pointeurs only)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7 : `scripts/mcp-server.py` — contexte vault + recherche réelle + boucle stdio

**Files:**
- Modify: `scripts/mcp-server.py`
- Test: `tests/test_mcp_server.py`

Câble le runner réel : résoudre le vault (slug → registre), `collect_facts`, rafraîchir le store si fastembed dispo, appeler `embed.search`. La boucle stdio reste fine.

- [ ] **Step 1 : Ajouter les tests qui échouent**

Ajouter dans `tests/test_mcp_server.py` :

```python
import tempfile


class ContextTest(unittest.TestCase):
    def test_build_context_errors_when_vault_unresolved(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["SM_REGISTRY"] = os.path.join(d, "registry.json")  # absent
            os.environ["CLAUDE_PROJECT_DIR"] = "/no/such/project"
            try:
                ctx = M.build_context()
            finally:
                os.environ.pop("SM_REGISTRY", None)
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            self.assertIn("error", ctx)

    def test_run_search_grep_fallback_returns_pointers(self):
        # vault réel temporaire ; fastembed absent -> vector_inactive, pointeurs grep
        with tempfile.TemporaryDirectory() as d:
            vault = os.path.join(d, "vault", "mailing")
            os.makedirs(vault)
            with open(os.path.join(vault, "a.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: relance-j3\ndescription: relance paniers 72h\n"
                        "metadata:\n  type: project\n---\ncorps relance")
            ctx = {"slug": "-t", "vault": os.path.join(d, "vault")}
            out = M.run_search(ctx, "relance", 8)
            files = [r["file"] for r in out["results"]]
            self.assertIn(os.path.join("mailing", "a.md"), files)
            self.assertTrue(all("body" not in r for r in out["results"]))
```

Note : `run_search` doit fonctionner même sans fastembed (store vide, `embed_fn=None` → grep). `build_context` lit `CLAUDE_PROJECT_DIR` (sinon `os.getcwd()`).

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `python3 -m unittest tests.test_mcp_server.ContextTest -v`
Expected : FAIL — `module 'mcp_server' has no attribute 'build_context'`.

- [ ] **Step 3 : Implémenter le contexte + le runner réel + la boucle**

Ajouter à `scripts/mcp-server.py`, **après** la définition de `TOOL` les imports des modules cœur, et **à la fin** le runner/boucle. D'abord, juste après `_load` et avant `PROTOCOL_VERSION`, ajouter :

```python
bv = _load("build_viewer", "build-viewer.py")
embed = _load("embed", "embed.py")
paths = _load("sm_paths", "sm_paths.py")
```

Puis, **après** `handle_request`, ajouter :

```python
def build_context():
    """Résout le vault du projet courant. Renvoie {'slug','vault'} ou {'error': ...}."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    s = paths.slug(project_dir)
    vault = paths.vault_clone_for_slug(s)
    if not vault or not os.path.isdir(vault):
        return {"error": "vault introuvable pour ce projet ; lance /memory-setup."}
    return {"slug": s, "vault": vault}


def run_search(ctx, query, k):
    """Charge les faits, rafraîchit le store si fastembed dispo, renvoie la recherche hybride."""
    facts, _ = bv.collect_facts(ctx["vault"], include_body=True)
    embed_fn = embed.load_fastembed_embed_fn()
    store = {}
    if embed_fn is not None:
        store_path = paths.store_path_for_slug(ctx["slug"])
        store = embed.refresh_store(facts, embed.load_store(store_path), embed_fn)
        embed.save_store(store_path, store)
    return embed.search(query, facts, store, embed_fn, k)


def main():
    ctx = build_context()

    def runner(query, k):
        if "error" in ctx:
            return {"results": [], "vector_inactive": True, "error": ctx["error"]}
        return run_search(ctx, query, k)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        resp = handle_request(req, runner)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `python3 -m unittest tests.test_mcp_server -v`
Expected : PASS (8 tests cumulés).

- [ ] **Step 5 : Commit**

```bash
git add scripts/mcp-server.py tests/test_mcp_server.py
git commit -m "feat(mcp): résolution vault + recherche réelle + boucle stdio

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8 : `.mcp.json` — déclarer le serveur MCP du plugin

**Files:**
- Create: `.mcp.json`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1 : Ajouter le test qui échoue**

Ajouter dans `tests/test_mcp_server.py` :

```python
class McpJsonTest(unittest.TestCase):
    def test_mcp_json_declares_server_with_plugin_root(self):
        path = os.path.join(HERE, "..", ".mcp.json")
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        srv = cfg["mcpServers"]["shared-memory"]
        self.assertEqual(srv["command"], "python3")
        self.assertTrue(any("${CLAUDE_PLUGIN_ROOT}" in a and a.endswith("mcp-server.py")
                            for a in srv["args"]))
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `python3 -m unittest tests.test_mcp_server.McpJsonTest -v`
Expected : FAIL — `.mcp.json` absent (`FileNotFoundError`).

- [ ] **Step 3 : Créer `.mcp.json`**

Créer `.mcp.json` à la racine du plugin :

```json
{
  "mcpServers": {
    "shared-memory": {
      "command": "python3",
      "args": ["${CLAUDE_PLUGIN_ROOT}/scripts/mcp-server.py"]
    }
  }
}
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `python3 -m unittest tests.test_mcp_server -v`
Expected : PASS (9 tests cumulés).

- [ ] **Step 5 : Commit**

```bash
git add .mcp.json tests/test_mcp_server.py
git commit -m "feat(mcp): déclare le serveur MCP shared-memory (.mcp.json)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

# Partie C — Doctor

## Task 9 : `scripts/doctor.py` — diagnostic structuré à sondes injectables

**Files:**
- Create: `scripts/doctor.py`
- Test: `tests/test_doctor.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `tests/test_doctor.py` :

```python
import importlib.util
import os
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "doctor", os.path.join(HERE, "..", "scripts", "doctor.py"))
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)

ALL_OK = {"python_ok": lambda: True, "has_fastembed": lambda: True,
          "model_cached": lambda: True, "mcp_json_present": lambda: True}


def by_name(checks):
    return {c["name"]: c for c in checks}


class DiagnoseTest(unittest.TestCase):
    def test_all_present_all_ok(self):
        checks = D.diagnose(probes=ALL_OK)
        self.assertTrue(all(c["ok"] for c in checks))

    def test_fastembed_absent_flags_semantic_and_model_with_remedy(self):
        probes = dict(ALL_OK, has_fastembed=lambda: False, model_cached=lambda: False)
        checks = by_name(D.diagnose(probes=probes))
        fe = next(c for c in checks.values() if "fastembed" in c["name"])
        self.assertFalse(fe["ok"])
        self.assertIn("pip install fastembed", fe["remedy"])
        model = next(c for c in checks.values() if "modèle" in c["name"])
        self.assertFalse(model["ok"])              # pas de modèle sans fastembed

    def test_mcp_json_absent_flagged(self):
        probes = dict(ALL_OK, mcp_json_present=lambda: False)
        checks = by_name(D.diagnose(probes=probes))
        mj = next(c for c in checks.values() if ".mcp.json" in c["name"])
        self.assertFalse(mj["ok"])

    def test_default_probes_run_without_error(self):
        # sur cette machine fastembed est absent : ne doit pas lever, doit produire des checks
        checks = D.diagnose()
        self.assertTrue(any("fastembed" in c["name"] for c in checks))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `python3 -m unittest tests.test_doctor -v`
Expected : FAIL — `scripts/doctor.py` absent.

- [ ] **Step 3 : Implémenter**

Créer `scripts/doctor.py` :

```python
#!/usr/bin/env python3
"""Diagnostic des prérequis de la recherche mémoire. N'INSTALLE rien.

`diagnose(probes=None)` -> liste de checks {name, ok, remedy}. Sondes injectables (tests).
CLI : impression lisible + exit code (1 si manque)."""
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


def _default_probes():
    def has_fastembed():
        return importlib.util.find_spec("fastembed") is not None

    def model_cached():
        cache = os.path.join(os.path.expanduser("~"), ".cache", "fastembed")
        return os.path.isdir(cache) and bool(os.listdir(cache))

    def mcp_json_present():
        return os.path.isfile(os.path.join(_HERE, "..", ".mcp.json"))

    return {
        "python_ok": lambda: sys.version_info >= (3, 8),
        "has_fastembed": has_fastembed,
        "model_cached": model_cached,
        "mcp_json_present": mcp_json_present,
    }


def diagnose(probes=None):
    p = dict(_default_probes())
    if probes:
        p.update(probes)
    fe = p["has_fastembed"]()
    return [
        {"name": "python3 ≥ 3.8", "ok": p["python_ok"](),
         "remedy": "Installer Python 3.8+ (indispensable)."},
        {"name": "fastembed importable (recherche sémantique)", "ok": fe,
         "remedy": "pip install fastembed  — active la recherche vectorielle locale."},
        {"name": "modèle d'embeddings téléchargé", "ok": bool(fe and p["model_cached"]()),
         "remedy": "Au 1er appel search_memory le modèle (~90 Mo) se télécharge ; "
                   "ou pré-charger : python3 -c \"from fastembed import TextEmbedding; TextEmbedding()\""},
        {"name": ".mcp.json en place", "ok": p["mcp_json_present"](),
         "remedy": "Fichier .mcp.json manquant — réinstaller/mettre à jour le plugin."},
    ]


def main():
    checks = diagnose()
    miss = 0
    for c in checks:
        print("  [%s] %s" % ("OK" if c["ok"] else "X", c["name"]))
        if not c["ok"]:
            miss += 1
            print("       -> %s" % c["remedy"])
    if miss:
        print("\n%d prérequis manquant(s). search_memory tourne en fallback grep "
              "en attendant (la véracité reste garantie : le fait est lu)." % miss)
        sys.exit(1)
    print("\nTout est prêt : recherche sémantique active.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `python3 -m unittest tests.test_doctor -v`
Expected : PASS (4 tests).

- [ ] **Step 5 : Commit**

```bash
git add scripts/doctor.py tests/test_doctor.py
git commit -m "feat(doctor): diagnostic structuré des prérequis (sondes injectables)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10 : skill `/memory-doctor` + entrée README

**Files:**
- Create: `skills/memory-doctor/SKILL.md`
- Modify: `README.md`

Pas de test unitaire (markdown). Vérif par relecture + `grep`.

- [ ] **Step 1 : Créer `skills/memory-doctor/SKILL.md`**

```markdown
---
name: memory-doctor
description: This skill should be used when the user asks to "diagnostiquer la mémoire", "vérifier la recherche mémoire", "activer la recherche sémantique", "pourquoi search_memory est en grep", "memory doctor", or "/memory-doctor". It runs the prerequisites diagnostic for search_memory and proposes the missing installs (the user validates; nothing is installed without consent).
argument-hint: ""
allowed-tools: Bash, Read, AskUserQuestion
version: 0.1.0
---

# memory-doctor — Diagnostiquer la recherche mémoire et proposer les installs

Vérifie les prérequis de `search_memory` (recherche vectorielle locale) et **propose** les
correctifs manquants. **N'installe jamais rien sans l'accord** de l'utilisateur. Sans
prérequis, `search_memory` reste fonctionnel en **fallback grep** — la véracité est garantie
(le fait est toujours lu).

## Procédure

1. **Lancer le diagnostic** :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/doctor.py
   ```

2. **Présenter le rapport** ligne à ligne (OK / manquant). Pour chaque manque, montrer le
   **remède** indiqué par le doctor.

3. **Proposer les installs manquantes** — typiquement `pip install fastembed` (recherche
   sémantique). **Demander l'accord** via AskUserQuestion avant toute commande qui installe ;
   ne rien exécuter sinon. Si l'utilisateur accepte :

   ```bash
   pip install fastembed
   ```

   puis (optionnel) pré-télécharger le modèle (~90 Mo) :

   ```bash
   python3 -c "from fastembed import TextEmbedding; TextEmbedding()"
   ```

4. **Re-vérifier** : relancer `doctor.py` pour confirmer que tout est OK.

## Points d'attention

- **Pas de dégradation silencieuse** : si `search_memory` renvoie `vector_inactive: true`,
  c'est que la sémantique est inactive (fastembed absent) — le signaler et proposer ce skill.
- **Local & privé** : fastembed embedde en local (ONNX), aucun appel réseau aux faits.
- **Consentement** : Claude n'installe rien sans validation explicite de l'utilisateur.

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py`** — diagnostic structuré + remèdes.
- **`${CLAUDE_PLUGIN_ROOT}/docs/superpowers/specs/2026-06-10-v2-token-optimization-design.md`** —
  conception (Volets B & C).
```

- [ ] **Step 2 : Ajouter la ligne `/memory-doctor` au tableau des skills du README**

Dans `README.md`, dans le tableau « ## Skills », après la ligne `/memory-ui`, ajouter :

```markdown
| `/memory-doctor` | diagnostiquer la recherche mémoire (`search_memory`) et proposer les installs (fastembed) |
```

- [ ] **Step 3 : Mentionner `.mcp.json` dans la structure du README**

Dans le bloc « ## Structure » de `README.md`, sous la ligne `├── .claude-plugin/`, ajouter une ligne pour `.mcp.json` (déclare le serveur MCP). Exemple à insérer juste après `│   └── marketplace.json` :

```markdown
├── .mcp.json            # déclare le serveur MCP (search_memory)
```

- [ ] **Step 4 : Vérifier**

Run :
```bash
grep -n "memory-doctor" README.md skills/memory-doctor/SKILL.md && grep -n "\.mcp\.json" README.md
```
Expected : au moins une occurrence dans chaque (README + SKILL), et la ligne `.mcp.json` dans la structure.

- [ ] **Step 5 : Commit**

```bash
git add skills/memory-doctor/SKILL.md README.md
git commit -m "feat(memory-doctor): skill de diagnostic + propositions d'install; README

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 11 : `memory-setup` appelle le doctor en fin de configuration

**Files:**
- Modify: `skills/memory-setup/SKILL.md`

- [ ] **Step 1 : Ajouter une étape « diagnostic » à la procédure**

Dans `skills/memory-setup/SKILL.md`, à la fin de la procédure (après l'étape 4 « Vérifier la sortie. »), ajouter l'étape 5 :

```markdown
5. **Annoncer d'emblée les prérequis de recherche.** Lancer le doctor pour signaler tout de
   suite ce qui manque (sans rien installer) :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/doctor.py
   ```

   Si fastembed manque, l'indiquer : `search_memory` tournera en **fallback grep** en attendant,
   et `/memory-doctor` propose d'activer la recherche sémantique (`pip install fastembed`).
```

- [ ] **Step 2 : Ajouter le renvoi ressource**

Dans la section `## Ressources` de `skills/memory-setup/SKILL.md`, ajouter :

```markdown
- **`${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py`** — diagnostic des prérequis de `search_memory`
  (lancé en fin de configuration ; détail via `/memory-doctor`).
```

- [ ] **Step 3 : Vérifier**

Run :
```bash
grep -n "doctor.py\|memory-doctor\|fallback grep" skills/memory-setup/SKILL.md
```
Expected : les renvois au doctor sont présents.

- [ ] **Step 4 : Commit**

```bash
git add skills/memory-setup/SKILL.md
git commit -m "feat(memory-setup): lance le doctor en fin de configuration

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 12 : Vérification d'ensemble

- [ ] **Step 1 : Suite complète**

Run : `python3 -m unittest discover -s . -p 'test_*.py' -v`
Expected : tous les tests passent (16 existants + nouveaux : sm_paths 5, embed 13, mcp_server 9, doctor 4). Aucune régression sur build-viewer / serve-viewer.

- [ ] **Step 2 : Fumée du serveur MCP (handshake réel via stdio)**

Run :
```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}' '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | python3 scripts/mcp-server.py
```
Expected : deux lignes JSON — la réponse `initialize` (avec `serverInfo.name = shared-memory`) puis `tools/list` exposant `search_memory`. (Le serveur lit stdin jusqu'à EOF ; `build_context` peut renvoyer une erreur vault si le projet n'est pas branché — c'est normal, le handshake répond quand même.)

- [ ] **Step 3 : Doctor en conditions réelles**

Run : `python3 scripts/doctor.py; echo "exit=$?"`
Expected : fastembed listé **manquant** sur cette machine, avec remède `pip install fastembed`, exit=1. `.mcp.json` et python3 **OK**.

- [ ] **Step 4 : (pas de commit)** Vérification seule.

---

## Self-Review

**Couverture du design (Volets B & C) :**

| Élément du design | Tâche |
|---|---|
| `search_memory(query, k)` MCP, renvoie des pointeurs `{file,name,path,score}`, jamais de body | Task 6, 7 |
| Embeddings fastembed local, **optionnel**, `embed_fn` injectable | Task 5 (chargeur), Tasks 2-4 (injection) |
| Fallback grep quand fastembed absent + signalement `vector_inactive` | Task 4, 7, 9, 10 |
| Store hors vault `~/.shared-memory/embeddings/<slug>/index.json` | Task 1 (`store_path_for_slug`), 2, 7 |
| Fraîcheur lazy par hash (ré-embedder seulement le changé) | Task 2 |
| Cosine brute-force pur Python | Task 3 |
| Hybride exhaustivité (top-k ∪ grep exact, dédupliqué) | Task 4 |
| `.mcp.json` déclare le serveur | Task 8 |
| `doctor.py` : prérequis + remèdes, pas d'install | Task 9 |
| `/memory-doctor` : présente + propose les installs (consentement) | Task 10 |
| `memory-setup` appelle le doctor en fin de config | Task 11 |
| Tests passent **sans** fastembed (embed_fn factice) | Tasks 2-7, 9, 12 |

**Cohérence des types (vérifiée) :**
- `embed_fn(list[str]) -> list[list[float]]` : même signature dans `refresh_store`, `search` (via `embed_fn([query])[0]`), le `fake_embed_fn` des tests, et `load_fastembed_embed_fn`.
- Fait = dict `{file, name, description, path, body?}` produit par `collect_facts` (build-viewer.py:66-76) ; `fact_text`, `grep_matches`, `_pointer` lisent ces clés via `.get`.
- Pointeur = `{file, name, path, score}` : produit par `_pointer` (Task 4), attendu par les tests MCP (Task 6-7), conforme au design.
- `search` renvoie `{"results": [...], "vector_inactive": bool}` partout (Task 4, runner Task 7, fake_runner Task 6).
- `diagnose` renvoie `[{name, ok, remedy}]` : produit Task 9, consommé par `main` (doctor) et le skill Task 10.

**Placeholders :** aucun — chaque étape de code montre le code complet ; chaque étape markdown montre le texte exact.

**Décalage potentiel à surveiller (noté, non bloquant) :** la version de protocole MCP est **échoée** depuis la requête `initialize` du client (fallback `2025-06-18`), ce qui évite un désaccord de version si Claude Code négocie une autre révision. `build_context` lit `CLAUDE_PROJECT_DIR` (sinon `os.getcwd()`) pour résoudre le vault — hypothèse : Claude Code lance le serveur MCP avec ce contexte projet.
