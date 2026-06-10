# Viewer scalable — Backend (Plan A, 1/2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner au viewer un backend scalable : `build-viewer` expose un `path[]` récursif et un mode métadonnées-seules (sans body), et un nouveau `serve-viewer.py` sert le HTML + le body d'un fait à la demande + une recherche full-text, le tout en `http.server` stdlib (localhost), couvert par `unittest`.

**Architecture:** `collect_facts` gagne un champ `path` (segments du dossier, pour l'arbre N-niveaux) et un paramètre `include_body` (False = index léger). `serve-viewer.py` importe `build-viewer` via `importlib` (nom à tiret), expose `GET /` (HTML + métadonnées), `GET /fact?f=` (body validé anti-traversal) et `GET /search?q=` (grep). **Le mode statique actuel n'est pas touché** → le viewer existant continue de fonctionner jusqu'au Plan B.

**Tech Stack:** Python 3 stdlib (`http.server`, `urllib`, `threading`), `unittest`.

**Conditions d'exécution (validées) :** travail sur `main` de `/var/www/shared-memory`, **commits autorisés**, tests en `unittest`.

**Hors scope (→ Plan B) :** refonte du `viewer-template` (arbre récursif, lazy-render, fetch, recherche hybride), bascule de `view.sh`/`memory-ui` sur le serveur, auto-stop/cycle de vie, retrait de l'ancien mode statique.

---

## Rappel — `collect_facts` actuel (après le sharding)

```python
def collect_facts(vault):
    facts, index_body = [], ""
    for root, _dirs, files in os.walk(vault):
        for fn in sorted(files):
            if not fn.endswith(".md"):
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, vault)
            parts = rel.split(os.sep)
            if rel == "MEMORY.md":   # racine uniquement
                _, index_body = parse_md(full)
                continue
            if parts[0] == "index":  # sous-index niveau 1
                continue
            domain = parts[0] if len(parts) > 1 else "général"
            fm, body = parse_md(full)
            facts.append({
                "file": rel, "name": fm.get("name", fn[:-3]),
                "description": fm.get("description", ""),
                "type": fm.get("metadata.type") or fm.get("type", "project"),
                "domain": domain, "body": body,
            })
    facts.sort(key=lambda f: (f["domain"], f["name"]))
    return facts, index_body
```

## File Structure

- **Modify** `scripts/build-viewer.py` : `collect_facts` gagne `path` (Task A1) et `include_body` (Task A2).
- **Create** `scripts/serve-viewer.py` : serveur stdlib (Tasks A3-A5).
- **Modify** `tests/test_build_viewer.py` : tests `path` + `include_body`.
- **Create** `tests/test_serve_viewer.py` : tests des endpoints.

---

### Task A1 : champ `path` (segments du dossier) dans `collect_facts`

**Files:**
- Modify: `scripts/build-viewer.py` (dict du fait dans `collect_facts`)
- Modify: `tests/test_build_viewer.py`

- [ ] **Step 1: Écrire les tests `path`**

Ajouter à `tests/test_build_viewer.py`, avant `if __name__`:

```python
class PathTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_path_is_folder_segments(self):
        write(os.path.join(self.vault, "mailing", "transactionnel", "relances.md"),
              "---\nname: relances\nmetadata:\n  type: project\n---\nx")
        facts, _ = bv.collect_facts(self.vault)
        f = facts[0]
        self.assertEqual(f["path"], ["mailing", "transactionnel"])
        self.assertEqual(f["domain"], "mailing")

    def test_root_fact_path_empty(self):
        write(os.path.join(self.vault, "note.md"), "---\nname: note\n---\nx")
        facts, _ = bv.collect_facts(self.vault)
        self.assertEqual(facts[0]["path"], [])
        self.assertEqual(facts[0]["domain"], "général")
```

- [ ] **Step 2: Lancer pour voir échouer**

Run: `cd /var/www/shared-memory && python3 -m unittest tests.test_build_viewer.PathTest -v`
Expected: FAIL — `KeyError: 'path'`

- [ ] **Step 3: Ajouter `path` au dict du fait**

Dans `scripts/build-viewer.py`, fonction `collect_facts`, remplacer le bloc :

```python
            domain = parts[0] if len(parts) > 1 else "général"
            fm, body = parse_md(full)
            facts.append({
                "file": rel, "name": fm.get("name", fn[:-3]),
                "description": fm.get("description", ""),
                "type": fm.get("metadata.type") or fm.get("type", "project"),
                "domain": domain, "body": body,
            })
```

par :

```python
            domain = parts[0] if len(parts) > 1 else "général"
            path = parts[:-1]   # segments du dossier (arbre N-niveaux) ; [] à la racine
            fm, body = parse_md(full)
            facts.append({
                "file": rel, "name": fm.get("name", fn[:-3]),
                "description": fm.get("description", ""),
                "type": fm.get("metadata.type") or fm.get("type", "project"),
                "domain": domain, "path": path, "body": body,
            })
```

- [ ] **Step 4: Lancer toute la suite**

Run: `cd /var/www/shared-memory && python3 -m unittest tests.test_build_viewer -v`
Expected: PASS (9 tests — les 7 existants + 2 nouveaux)

- [ ] **Step 5: Commit**

```bash
cd /var/www/shared-memory
git add scripts/build-viewer.py tests/test_build_viewer.py
git commit -m "feat(viewer): add recursive path[] to facts for N-level tree"
```

---

### Task A2 : paramètre `include_body` (index métadonnées-seules)

**Files:**
- Modify: `scripts/build-viewer.py` (signature + dict de `collect_facts`)
- Modify: `tests/test_build_viewer.py`

- [ ] **Step 1: Écrire les tests `include_body`**

Ajouter à `tests/test_build_viewer.py`, dans la classe `PathTest` (mêmes setUp/tearDown), ces méthodes :

```python
    def test_metadata_only_omits_body(self):
        write(os.path.join(self.vault, "mailing", "audit.md"),
              "---\nname: audit\nmetadata:\n  type: project\n---\nle corps")
        facts, _ = bv.collect_facts(self.vault, include_body=False)
        self.assertNotIn("body", facts[0])
        self.assertEqual(facts[0]["name"], "audit")
        self.assertEqual(facts[0]["path"], ["mailing"])

    def test_default_includes_body(self):
        write(os.path.join(self.vault, "mailing", "audit.md"),
              "---\nname: audit\n---\nle corps")
        facts, _ = bv.collect_facts(self.vault)
        self.assertEqual(facts[0]["body"], "le corps")
```

- [ ] **Step 2: Lancer pour voir échouer**

Run: `cd /var/www/shared-memory && python3 -m unittest tests.test_build_viewer.PathTest.test_metadata_only_omits_body -v`
Expected: FAIL — `TypeError: collect_facts() got an unexpected keyword argument 'include_body'`

- [ ] **Step 3: Ajouter le paramètre**

Dans `scripts/build-viewer.py`, modifier la signature et le dict :

```python
def collect_facts(vault, include_body=True):
```

et remplacer le bloc d'ajout du fait par :

```python
            domain = parts[0] if len(parts) > 1 else "général"
            path = parts[:-1]   # segments du dossier (arbre N-niveaux) ; [] à la racine
            fm, body = parse_md(full)
            fact = {
                "file": rel, "name": fm.get("name", fn[:-3]),
                "description": fm.get("description", ""),
                "type": fm.get("metadata.type") or fm.get("type", "project"),
                "domain": domain, "path": path,
            }
            if include_body:
                fact["body"] = body
            facts.append(fact)
```

- [ ] **Step 4: Lancer toute la suite**

Run: `cd /var/www/shared-memory && python3 -m unittest tests.test_build_viewer -v`
Expected: PASS (11 tests). `main()` appelle `collect_facts(vault)` → `include_body=True` par défaut, donc le mode statique reste identique.

- [ ] **Step 5: Commit**

```bash
cd /var/www/shared-memory
git add scripts/build-viewer.py tests/test_build_viewer.py
git commit -m "feat(viewer): add include_body flag for metadata-only index"
```

---

### Task A3 : `serve-viewer.py` — serveur + `GET /` (HTML + métadonnées)

**Files:**
- Create: `scripts/serve-viewer.py`
- Create: `tests/test_serve_viewer.py`

- [ ] **Step 1: Écrire le test du `GET /`**

`tests/test_serve_viewer.py` :

```python
import importlib.util
import json
import os
import tempfile
import threading
import unittest
import urllib.request
from http.server import HTTPServer

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "serve_viewer", os.path.join(HERE, "..", "scripts", "serve-viewer.py"))
sv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sv)


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class ServerTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.vault = os.path.join(self.root, "vault")
        write(os.path.join(self.vault, "mailing", "audit.md"),
              "---\nname: audit\ndescription: desc audit\nmetadata:\n  type: project\n---\nle corps secret du fait")
        self.tmpl = os.path.join(self.root, "tmpl.html")
        write(self.tmpl, "<x>/*__DATA__*/</x>")
        self.httpd = HTTPServer(("127.0.0.1", 0), sv.make_handler(self.vault, self.tmpl))
        self.port = self.httpd.server_address[1]
        self.t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.t.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self._tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
            return r.status, r.read().decode("utf-8")


class IndexRouteTest(ServerTestBase):
    def test_root_serves_html_with_metadata_no_body(self):
        status, html = self.get("/")
        self.assertEqual(status, 200)
        data = json.loads(html[html.index("<x>") + 3: html.index("</x>")])
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["facts"][0]["name"], "audit")
        self.assertEqual(data["facts"][0]["path"], ["mailing"])
        self.assertNotIn("body", data["facts"][0])   # métadonnées seules


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Lancer pour voir échouer**

Run: `cd /var/www/shared-memory && python3 -m unittest tests.test_serve_viewer -v`
Expected: FAIL — `AttributeError: module 'serve_viewer' has no attribute 'make_handler'`

- [ ] **Step 3: Créer `scripts/serve-viewer.py`**

```python
#!/usr/bin/env python3
"""Serveur local (lecture seule) du vault mémoire.

Usage: serve-viewer.py <vault-dir> <template-html> [port]
- GET /            -> HTML du viewer + index métadonnées (sans body)
- GET /fact?f=…    -> body d'UN fait (chemin validé : reste dans le vault, .md)
- GET /search?q=…  -> grep full-text sur les faits, renvoie les métadonnées matchantes
Bind 127.0.0.1 uniquement.
"""
import importlib.util
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "build_viewer", os.path.join(_HERE, "build-viewer.py"))
bv = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bv)


def make_handler(vault, template):
    vault_real = os.path.realpath(vault)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="text/plain; charset=utf-8"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/":
                facts, index_body = bv.collect_facts(vault, include_body=False)
                data = {"facts": facts, "index": index_body, "vault": vault, "count": len(facts)}
                html = open(template, encoding="utf-8").read().replace(
                    "/*__DATA__*/", json.dumps(data, ensure_ascii=False))
                self._send(200, html, "text/html; charset=utf-8")
            else:
                self._send(404, "not found")

        def log_message(self, *a):
            pass

    return Handler


def main():
    vault, template = sys.argv[1], sys.argv[2]
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    httpd = HTTPServer(("127.0.0.1", port), make_handler(vault, template))
    print("http://127.0.0.1:%d" % httpd.server_address[1])
    httpd.serve_forever()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Lancer le test**

Run: `cd /var/www/shared-memory && python3 -m unittest tests.test_serve_viewer -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /var/www/shared-memory
git add scripts/serve-viewer.py tests/test_serve_viewer.py
git commit -m "feat(server): serve-viewer with GET / (html + metadata-only index)"
```

---

### Task A4 : `GET /fact?f=` (body à la demande + anti-traversal)

**Files:**
- Modify: `scripts/serve-viewer.py` (router `do_GET`)
- Modify: `tests/test_serve_viewer.py`

- [ ] **Step 1: Écrire les tests `/fact`**

Ajouter à `tests/test_serve_viewer.py`, avant `if __name__`:

```python
import urllib.error


class FactRouteTest(ServerTestBase):
    def test_fact_returns_body(self):
        status, body = self.get("/fact?f=mailing/audit.md")
        self.assertEqual(status, 200)
        self.assertIn("le corps secret du fait", body)

    def test_fact_rejects_traversal(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get("/fact?f=../../../../etc/passwd")
        self.assertEqual(cm.exception.code, 404)

    def test_fact_missing_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get("/fact?f=mailing/nope.md")
        self.assertEqual(cm.exception.code, 404)
```

- [ ] **Step 2: Lancer pour voir échouer**

Run: `cd /var/www/shared-memory && python3 -m unittest tests.test_serve_viewer.FactRouteTest -v`
Expected: FAIL — la route `/fact` renvoie 404 sur tout, donc `test_fact_returns_body` échoue (404 au lieu de 200).

- [ ] **Step 3: Ajouter la route `/fact`**

Dans `scripts/serve-viewer.py`, dans `do_GET`, remplacer le `else` final par :

```python
            elif u.path == "/fact":
                f = (parse_qs(u.query).get("f") or [""])[0]
                full = os.path.realpath(os.path.join(vault, f))
                inside = full == vault_real or full.startswith(vault_real + os.sep)
                if not f or not full.endswith(".md") or not inside or not os.path.isfile(full):
                    self._send(404, "not found"); return
                _, body = bv.parse_md(full)
                self._send(200, body, "text/markdown; charset=utf-8")
            else:
                self._send(404, "not found")
```

- [ ] **Step 4: Lancer les tests**

Run: `cd /var/www/shared-memory && python3 -m unittest tests.test_serve_viewer -v`
Expected: PASS (tous, dont les 3 `/fact`)

- [ ] **Step 5: Commit**

```bash
cd /var/www/shared-memory
git add scripts/serve-viewer.py tests/test_serve_viewer.py
git commit -m "feat(server): GET /fact serves body on demand with path-traversal guard"
```

---

### Task A5 : `GET /search?q=` (grep full-text)

**Files:**
- Modify: `scripts/serve-viewer.py` (router `do_GET`)
- Modify: `tests/test_serve_viewer.py`

- [ ] **Step 1: Écrire les tests `/search`**

Ajouter à `tests/test_serve_viewer.py`, avant `if __name__`:

```python
class SearchRouteTest(ServerTestBase):
    def test_search_matches_body(self):
        status, payload = self.get("/search?q=corps%20secret")
        self.assertEqual(status, 200)
        res = json.loads(payload)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["name"], "audit")
        self.assertNotIn("body", res[0])   # résultats = métadonnées seules

    def test_search_no_match_is_empty(self):
        status, payload = self.get("/search?q=zzzznotfound")
        self.assertEqual(json.loads(payload), [])
```

- [ ] **Step 2: Lancer pour voir échouer**

Run: `cd /var/www/shared-memory && python3 -m unittest tests.test_serve_viewer.SearchRouteTest -v`
Expected: FAIL — `/search` renvoie 404, JSON decode échoue.

- [ ] **Step 3: Ajouter la route `/search`**

Dans `scripts/serve-viewer.py`, dans `do_GET`, ajouter avant le `else` final :

```python
            elif u.path == "/search":
                q = (parse_qs(u.query).get("q") or [""])[0].lower()
                facts, _ = bv.collect_facts(vault, include_body=True)
                res = []
                for f in facts:
                    hay = (f["name"] + f["description"] + f["body"]).lower()
                    if q and q in hay:
                        res.append({k: f[k] for k in ("file", "name", "description", "type", "path")})
                self._send(200, json.dumps(res, ensure_ascii=False),
                           "application/json; charset=utf-8")
```

- [ ] **Step 4: Lancer toute la suite (build + serveur)**

Run: `cd /var/www/shared-memory && python3 -m unittest discover -s tests -v`
Expected: PASS — 11 (build-viewer) + 6 (serveur : 1 index + 3 fact + 2 search) = 17 tests.

- [ ] **Step 5: Commit**

```bash
cd /var/www/shared-memory
git add scripts/serve-viewer.py tests/test_serve_viewer.py
git commit -m "feat(server): GET /search full-text grep over facts"
```

---

## Self-Review (rempli à la rédaction)

**Couverture du spec (périmètre Plan A) :**
- `path[]` récursif → Task A1. ✓
- Index métadonnées-seules (`include_body=False`) → Task A2. ✓
- Serveur `GET /` (HTML + métadonnées) → Task A3. ✓
- `GET /fact` body à la demande + anti-traversal → Task A4. ✓
- `GET /search` full-text → Task A5. ✓
- Bind `127.0.0.1` → A3 (`HTTPServer(("127.0.0.1", port), …)`). ✓
- Mode statique intact (`main()` inchangé, `include_body=True` par défaut) → A2. ✓
- (Arbre récursif UI, lazy-render, fetch, view.sh, auto-stop → Plan B.)

**Placeholders :** aucun ; code complet et exécutable à chaque étape.

**Cohérence des signatures :** `collect_facts(vault, include_body=True) -> (facts, index_body)` ; chaque fait a `file/name/description/type/domain/path` (+`body` si `include_body`). `make_handler(vault, template) -> Handler`. `bv.parse_md(full) -> (fm, body)`. Le champ `path` produit en A1 est consommé par `/` (A3) et `/search` (A5). Les routes utilisent `parse_qs(u.query)` de façon cohérente.

---

## Tests — commande globale

```bash
cd /var/www/shared-memory && python3 -m unittest discover -s tests -v
```
Expected: 17 tests PASS.
