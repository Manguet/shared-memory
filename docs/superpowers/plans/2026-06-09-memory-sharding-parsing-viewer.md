# Mémoire shardée — Parsing récursif & viewer arborescent (Plan 1/2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire passer le viewer de la mémoire d'un index plat à une structure shardée par domaine : `build-viewer.py` collecte les faits récursivement (domaine = sous-dossier) et le viewer affiche un arbre de domaines en sidebar.

**Architecture:** `build-viewer.py` parcourt le vault en récursif ; chaque `.md` sous `<domaine>/` devient un fait avec un champ `domain` ; `MEMORY.md` reste l'index (la carte) ; les fichiers sous `index/` (sous-index niveau 1) sont ignorés à l'affichage ; les faits à la racine prennent le domaine implicite `« général »` (mode mixte / rétrocompat). Le template HTML groupe la nav par `domain` au lieu du `type` ; le `type` devient un filtre secondaire.

**Tech Stack:** Python 3 (stdlib uniquement), **`unittest`** (stdlib) pour les tests, HTML/CSS/JS vanilla (template autonome).

**Conditions d'exécution (validées avec l'utilisateur) :** travail directement sur `main` du repo `/var/www/shared-memory` ; **commits autorisés** (phase de test). Tests en `unittest` (pas de pytest dans l'environnement).

**Hors scope (→ Plan 2) :** modifications des skills (`/memory-promote`, `/memory-import`, `/memory-review`, `/memory-list`), seuil semi-auto à ~150 lignes, suggestion de domaine proche, migration des 5 faits du vault negocian.

---

## Convention de structure (rappel, définie par le spec)

```
vault/
├── MEMORY.md            # carte des domaines (index, niveau 0)
├── index/
│   └── <domaine>.md     # sous-index (niveau 1) — IGNORÉ par le viewer
├── <domaine>/
│   └── <fait>.md        # fait (niveau 2) — domain = nom du dossier
└── <fait>.md            # fait à la racine → domain = « général »
```

## File Structure

- **Modifier** `scripts/build-viewer.py` : extraire `collect_facts(vault)`, la rendre récursive, ajouter le champ `domain`.
- **Créer** `tests/__init__.py` : fichier vide (permet `python3 -m unittest tests.test_build_viewer`).
- **Créer** `tests/test_build_viewer.py` : tests `unittest` de `collect_facts` + un test d'intégration de `main`.
- **Modifier** `assets/viewer-template.html` : `renderNav()` groupe par `domain` ; `b.title` montre le type.

---

## Phase A — `build-viewer.py` récursif + domaine

### Task A1 : Mise en place des tests + refactor `collect_facts` (non-régression)

**Files:**
- Modify: `scripts/build-viewer.py` (extraire la boucle de `main()` dans `collect_facts`)
- Create: `tests/__init__.py` (vide)
- Create: `tests/test_build_viewer.py`

- [ ] **Step 1: Créer `tests/__init__.py` vide**

```bash
cd /var/www/shared-memory && mkdir -p tests && : > tests/__init__.py
```

- [ ] **Step 2: Écrire le test de non-régression (comportement plat actuel)**

`tests/test_build_viewer.py` :

```python
import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "build_viewer", os.path.join(HERE, "..", "scripts", "build-viewer.py")
)
bv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bv)


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class CollectFactsBaselineTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_flat_fact_is_collected(self):
        write(os.path.join(self.vault, "regle.md"),
              "---\nname: regle\ndescription: une regle\nmetadata:\n  type: project\n---\ncorps du fait")
        facts, index = bv.collect_facts(self.vault)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["name"], "regle")
        self.assertEqual(facts[0]["description"], "une regle")
        self.assertEqual(facts[0]["type"], "project")
        self.assertEqual(facts[0]["body"], "corps du fait")

    def test_memory_md_is_index_not_a_fact(self):
        write(os.path.join(self.vault, "MEMORY.md"), "# Carte\n- mailing")
        write(os.path.join(self.vault, "regle.md"), "---\nname: regle\n---\nx")
        facts, index = bv.collect_facts(self.vault)
        self.assertEqual([f["name"] for f in facts], ["regle"])
        self.assertIn("Carte", index)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Lancer les tests pour les voir échouer (`collect_facts` n'existe pas)**

Run: `cd /var/www/shared-memory && python3 -m unittest tests.test_build_viewer -v`
Expected: FAIL avec `AttributeError: module 'build_viewer' has no attribute 'collect_facts'`

- [ ] **Step 4: Extraire `collect_facts` dans `scripts/build-viewer.py`**

Remplacer la fonction `main()` (lignes 43-69) par :

```python
def collect_facts(vault):
    """Renvoie (facts, index_body) pour un vault PLAT (sera rendu récursif en Task A2)."""
    facts, index_body = [], ""
    for fn in sorted(os.listdir(vault)):
        if not fn.endswith(".md"):
            continue
        fm, body = parse_md(os.path.join(vault, fn))
        if fn == "MEMORY.md":
            index_body = body
            continue
        facts.append({
            "file": fn,
            "name": fm.get("name", fn[:-3]),
            "description": fm.get("description", ""),
            "type": fm.get("metadata.type") or fm.get("type", "project"),
            "body": body,
        })
    return facts, index_body


def main():
    vault = sys.argv[1]
    out = sys.argv[2]
    tmpl = sys.argv[3]
    facts, index_body = collect_facts(vault)
    data = {"facts": facts, "index": index_body, "vault": vault, "count": len(facts)}
    html = open(tmpl, encoding="utf-8").read()
    html = html.replace("/*__DATA__*/", json.dumps(data, ensure_ascii=False))
    open(out, "w", encoding="utf-8").write(html)
    print(out)
```

- [ ] **Step 5: Lancer les tests pour les voir passer**

Run: `cd /var/www/shared-memory && python3 -m unittest tests.test_build_viewer -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
cd /var/www/shared-memory
git add scripts/build-viewer.py tests/__init__.py tests/test_build_viewer.py
git commit -m "refactor(viewer): extract collect_facts + add baseline unittest"
```

---

### Task A2 : Parcours récursif + champ `domain` + mode mixte

**Files:**
- Modify: `scripts/build-viewer.py` (corps de `collect_facts`)
- Modify: `tests/test_build_viewer.py` (nouvelle classe de tests)

- [ ] **Step 1: Écrire les tests de récursivité, domaine et mode mixte**

Ajouter à `tests/test_build_viewer.py`, AVANT le bloc `if __name__ == "__main__":` :

```python
class DomainTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_fact_in_subfolder_gets_domain(self):
        write(os.path.join(self.vault, "mailing", "audit.md"),
              "---\nname: audit\nmetadata:\n  type: project\n---\ncorps")
        write(os.path.join(self.vault, "ui", "ux.md"),
              "---\nname: ux\nmetadata:\n  type: project\n---\ncorps")
        facts, _ = bv.collect_facts(self.vault)
        by_name = {f["name"]: f for f in facts}
        self.assertEqual(by_name["audit"]["domain"], "mailing")
        self.assertEqual(by_name["ux"]["domain"], "ui")
        self.assertEqual(by_name["audit"]["file"], os.path.join("mailing", "audit.md"))

    def test_root_fact_domain_is_general(self):
        write(os.path.join(self.vault, "feedback_no_commit.md"),
              "---\nname: fb\ntype: feedback\n---\nx")
        facts, _ = bv.collect_facts(self.vault)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["domain"], "général")
        self.assertEqual(facts[0]["type"], "feedback")

    def test_index_subfolder_is_ignored(self):
        write(os.path.join(self.vault, "index", "mailing.md"), "# sous-index mailing")
        write(os.path.join(self.vault, "mailing", "audit.md"), "---\nname: audit\n---\nx")
        facts, _ = bv.collect_facts(self.vault)
        self.assertEqual([f["name"] for f in facts], ["audit"])

    def test_memory_md_index_in_mixed_mode(self):
        write(os.path.join(self.vault, "MEMORY.md"), "# Carte\n- mailing")
        write(os.path.join(self.vault, "mailing", "audit.md"), "---\nname: audit\n---\nx")
        facts, index = bv.collect_facts(self.vault)
        self.assertIn("Carte", index)
        self.assertEqual([f["name"] for f in facts], ["audit"])
```

- [ ] **Step 2: Lancer les tests pour voir les nouveaux échouer**

Run: `cd /var/www/shared-memory && python3 -m unittest tests.test_build_viewer.DomainTest -v`
Expected: FAIL — `KeyError: 'domain'` (le champ n'existe pas encore)

- [ ] **Step 3: Rendre `collect_facts` récursive avec domaine**

Remplacer entièrement le corps de `collect_facts` par :

```python
def collect_facts(vault):
    """Renvoie (facts, index_body) en parcourant récursivement le vault.

    - `MEMORY.md` à la racine -> index_body (la carte).
    - tout `.md` sous `index/` -> ignoré (sous-index niveau 1).
    - tout autre `.md` -> un fait ; `domain` = 1er segment du chemin relatif
      s'il est dans un sous-dossier, sinon « général » (faits à la racine = mode mixte).
    `file` = chemin relatif au vault (unique même entre domaines).
    """
    facts, index_body = [], ""
    for root, _dirs, files in os.walk(vault):
        for fn in sorted(files):
            if not fn.endswith(".md"):
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, vault)
            parts = rel.split(os.sep)
            if rel == "MEMORY.md":
                _, index_body = parse_md(full)
                continue
            if parts[0] == "index":
                continue
            domain = parts[0] if len(parts) > 1 else "général"
            fm, body = parse_md(full)
            facts.append({
                "file": rel,
                "name": fm.get("name", fn[:-3]),
                "description": fm.get("description", ""),
                "type": fm.get("metadata.type") or fm.get("type", "project"),
                "domain": domain,
                "body": body,
            })
    facts.sort(key=lambda f: (f["domain"], f["name"]))
    return facts, index_body
```

- [ ] **Step 4: Lancer toute la suite pour la voir passer**

Run: `cd /var/www/shared-memory && python3 -m unittest tests.test_build_viewer -v`
Expected: PASS (6 tests — les 2 baseline incluant le fait plat, qui doit toujours donner `domain == "général"`)

- [ ] **Step 5: Commit**

```bash
cd /var/www/shared-memory
git add scripts/build-viewer.py tests/test_build_viewer.py
git commit -m "feat(viewer): recursive fact collection with domain from subfolder"
```

---

### Task A3 : Test d'intégration de `main` (le DATA injecté contient `domain`)

**Files:**
- Modify: `tests/test_build_viewer.py`

- [ ] **Step 1: Écrire le test d'intégration end-to-end**

Ajouter à `tests/test_build_viewer.py`, AVANT le bloc `if __name__ == "__main__":` :

```python
class MainIntegrationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_main_injects_domain_into_html(self):
        vault = os.path.join(self.root, "vault")
        write(os.path.join(vault, "mailing", "audit.md"),
              "---\nname: audit\nmetadata:\n  type: project\n---\ncorps")
        tmpl = os.path.join(self.root, "tmpl.html")
        write(tmpl, "<x>/*__DATA__*/</x>")
        out = os.path.join(self.root, "out.html")
        argv = ["build-viewer.py", vault, out, tmpl]
        with mock.patch.object(sys, "argv", argv):
            bv.main()
        with open(out, encoding="utf-8") as f:
            html = f.read()
        m = re.search(r"<x>(.*)</x>", html, re.S)
        data = json.loads(m.group(1))
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["facts"][0]["domain"], "mailing")
```

- [ ] **Step 2: Lancer le test**

Run: `cd /var/www/shared-memory && python3 -m unittest tests.test_build_viewer.MainIntegrationTest -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
cd /var/www/shared-memory
git add tests/test_build_viewer.py
git commit -m "test(viewer): end-to-end domain injection in generated HTML"
```

---

## Phase B — Viewer : arbre de domaines en sidebar

### Task B1 : Grouper la nav par domaine (au lieu du type)

**Files:**
- Modify: `assets/viewer-template.html` (fonction `renderNav`, lignes 285-305)

- [ ] **Step 1: Remplacer `renderNav()` par un groupement par domaine**

Remplacer la fonction `renderNav` (lignes 285-305) par :

```javascript
function renderNav(){
  const nav = $('nav'); nav.innerHTML = '';
  let idx = 0;
  const vis = visible();                                   // déjà filtré par type
  const domains = [...new Set(vis.map(f => f.domain))].sort();
  domains.forEach(dom => {
    const items = vis.filter(f => f.domain === dom);
    if(!items.length) return;
    const g = document.createElement('details'); g.className = 'group'; g.open = true;
    g.innerHTML = `<summary><span class="gdot" style="background:var(--coral)"></span>${esc(dom)}<span class="gcount">${items.length}</span></summary>`;
    items.forEach(f => {
      const b = document.createElement('button');
      b.className = 'navitem' + (state.view==='fact' && state.factId===f.file ? ' active' : '');
      b.style.animationDelay = (idx++ * 12) + 'ms';
      b.textContent = f.name;
      b.title = f.name + ' · ' + f.type;                   // le type passe en infobulle
      b.onclick = () => { state.view = 'fact'; state.factId = f.file; $('q').value=''; state.query=''; update(); };
      g.appendChild(b);
    });
    nav.appendChild(g);
  });
}
```

> Note : `renderFilters()` (chips de type) reste inchangé — il pilote `state.types`, donc `visible()`, donc ce que `renderNav` affiche. Le type devient un filtre secondaire, exactement comme la maquette A. La fonction `esc()` est déjà définie plus haut dans le template.

- [ ] **Step 2: Vérification automatisée — génération avec un vault factice multi-domaines**

Run:
```bash
cd /var/www/shared-memory
rm -rf /tmp/vault-test && mkdir -p /tmp/vault-test/mailing /tmp/vault-test/ui
printf -- '---\nname: audit\nmetadata:\n  type: project\n---\ncorps' > /tmp/vault-test/mailing/audit.md
printf -- '---\nname: ux\nmetadata:\n  type: reference\n---\ncorps' > /tmp/vault-test/ui/ux.md
python3 scripts/build-viewer.py /tmp/vault-test /tmp/viewer-test.html assets/viewer-template.html
grep -c '"domain": "mailing"' /tmp/viewer-test.html
grep -c 'const domains = \[...new Set' /tmp/viewer-test.html
```
Expected: la 1ʳᵉ commande affiche le chemin `/tmp/viewer-test.html` ; les deux `grep -c` affichent `1` (le DATA contient le domaine, le JS de groupement est présent).

- [ ] **Step 3: Vérification manuelle dans le navigateur**

Ouvrir `/tmp/viewer-test.html` dans un navigateur. Vérifier :
- La sidebar montre deux groupes repliables : **mailing** (1) et **ui** (1).
- Cliquer un fait l'affiche dans le panneau principal.
- Décocher le chip de type **reference** : le groupe **ui** disparaît (filtre type secondaire fonctionnel).
- La recherche (`/`) trouve toujours les faits des deux domaines.

Noter tout écart ; si un point échoue, corriger `renderNav` avant le commit.

- [ ] **Step 4: Commit**

```bash
cd /var/www/shared-memory
git add assets/viewer-template.html
git commit -m "feat(viewer): sidebar nav grouped by domain (type as secondary filter)"
```

---

## Self-Review (rempli à la rédaction)

**Couverture du spec (périmètre Plan 1) :**
- Parsing récursif + `domain` depuis le sous-dossier → Task A2. ✓
- `index/` ignoré → Task A2 (`test_index_subfolder_is_ignored`). ✓
- Mode mixte / faits racine = « général » → Task A2. ✓
- `MEMORY.md` reste l'index → Tasks A1/A2. ✓
- Viewer : arbre de domaines en sidebar, type secondaire → Task B1. ✓
- (Skills, seuil ~150, suggestion de domaine, migration → Plan 2, hors périmètre assumé.)

**Placeholders :** aucun TODO/TBD ; tout le code de test et d'implémentation est complet et exécutable.

**Cohérence des types/signatures :** `collect_facts(vault) -> (facts, index_body)` utilisée identiquement en A1/A2/A3 et par `main()` ; le champ `domain` produit en A2 est consommé en B1 (`f.domain`) et testé en A3. `file` = chemin relatif partout.

---

## Tests — commande globale

```bash
cd /var/www/shared-memory && python3 -m unittest tests.test_build_viewer -v
```
Expected: 7 tests PASS (baseline ×2, DomainTest ×4, MainIntegrationTest ×1).
