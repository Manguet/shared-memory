# Exclure des faits du `/memory-promote` (faits « locaux ») — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre de garder des faits `project`/`reference` en local (jamais partagés) via un drapeau `metadata.local: true`, respecté par reshard, le compteur, le viewer et `/memory-promote` (exclusion ponctuelle + durable).

**Architecture:** Un unique drapeau frontmatter `metadata.local: true` est la source de vérité. `collect_facts` le porte ; `reshard` traite les faits locaux en **passthrough** (réécrits à leur place, hors index/seuil) ; `sm_count_unpromoted` les saute ; `lint` les tolère/valide ; le viewer les badge et permet de (dé)cocher ; `/memory-promote` les filtre et construit sa branche dans un worktree propre depuis `origin/main`.

**Tech Stack:** Python 3 stdlib (`build-viewer.py`, `reshard.py`, `lint.py`, `serve-viewer.py`), Bash (`lib.sh`), JS vanilla (`viewer-template.html`), Markdown (skill), `unittest` (importlib + sous-process, vaults jetables).

---

## Contexte pour l'implémenteur

- **Jamais le vrai vault** : tous les tests utilisent des `tempfile.TemporaryDirectory`.
- **Compat ascendante stricte** : sans aucun fait `local`, `reshard`/`collect_facts`/`lint`/`count` se comportent EXACTEMENT comme avant. Les tests existants restent verts.
- **Anti perte de données** : `reshard()` fait `rmtree(vault/<domaine>)` puis remet les faits placés. Les faits `local` DOIVENT être préservés via passthrough (voir Task 2) — un test de non-perte est requis.
- **Gate** : `python3 -W error::ResourceWarning -m unittest discover -s tests` → `OK` en fin de chaque tâche.
- **Drapeau** : le parseur `parse_md` rend les valeurs en **chaînes** ; `local` est vrai ssi la valeur minusculée vaut `"true"`.
- L'implémenteur **commite sur la branche de travail** (l'utilisateur pousse/merge lui-même).

---

## File Structure

| Fichier | Responsabilité | Action |
|---|---|---|
| `scripts/build-viewer.py` | `collect_facts` ajoute `local` (booléen) au dict du fait. | Modifier |
| `scripts/reshard.py` | `_semantic_tree` renvoie aussi les faits locaux (passthrough) ; `_plan_layout` les réécrit en place, hors index/seuil. | Modifier |
| `scripts/lib.sh` | `sm_count_unpromoted` saute les faits `local`. | Modifier |
| `scripts/lint.py` | tolère `metadata.local` ; `warn local_malformed` si valeur ≠ `true`/`false`. | Modifier |
| `scripts/serve-viewer.py` | `_fact_text(..., local=False)` ; `_validate` renvoie `local` ; create/update le passent. | Modifier |
| `assets/viewer-template.html` | badge « local » + case à cocher dans les formulaires. | Modifier |
| `skills/memory-promote/SKILL.md` | filtre `local` + sélection interactive + worktree A. | Modifier |
| `docs/domain-convention.md`, `docs/ARCHITECTURE.md` | documenter le drapeau. | Modifier |
| `tests/test_build_viewer.py`, `tests/test_reshard.py`, `tests/test_hooks.py`, `tests/test_lint.py`, `tests/test_serve_viewer.py` | couverture. | Modifier |

---

### Task 1: `collect_facts` porte `local`

**Files:**
- Modify: `scripts/build-viewer.py`
- Test: `tests/test_build_viewer.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter dans `tests/test_build_viewer.py` (helpers `bv`, `write` déjà en haut), une classe :

```python
class CollectFactsLocalTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_local_true_is_carried(self):
        write(os.path.join(self.vault, "mailing", "x.md"),
              "---\nname: x\ndescription: un fait local\nmetadata:\n  type: project\n  local: true\n---\nc")
        facts, _ = bv.collect_facts(self.vault)
        self.assertTrue(facts[0]["local"])

    def test_absent_flag_is_false(self):
        write(os.path.join(self.vault, "mailing", "y.md"),
              "---\nname: y\ndescription: un fait normal\nmetadata:\n  type: project\n---\nc")
        facts, _ = bv.collect_facts(self.vault)
        self.assertFalse(facts[0]["local"])

    def test_local_false_is_false(self):
        write(os.path.join(self.vault, "mailing", "z.md"),
              "---\nname: z\ndescription: explicitement partageable\nmetadata:\n  type: project\n  local: false\n---\nc")
        facts, _ = bv.collect_facts(self.vault)
        self.assertFalse(facts[0]["local"])
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python3 -m unittest tests.test_build_viewer.CollectFactsLocalTest -v`
Expected: FAIL — `KeyError: 'local'`.

- [ ] **Step 3: Implémenter**

Dans `scripts/build-viewer.py`, dans `collect_facts`, ajouter une clé au dict `fact` (juste après la ligne `"reviewed": ...`) :

```python
                "local": (fm.get("metadata.local") or fm.get("local") or "").strip().lower() == "true",
```

- [ ] **Step 4: Vérifier le succès**

Run: `python3 -m unittest tests.test_build_viewer -v`
Expected: PASS (anciens + `CollectFactsLocalTest`).

- [ ] **Step 5: Gate + commit**

```bash
python3 -W error::ResourceWarning -m unittest discover -s tests
git add scripts/build-viewer.py tests/test_build_viewer.py
git commit -m "feat(viewer): collect_facts porte le drapeau local

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `reshard` ignore les faits `local` (passthrough anti-perte)

**Files:**
- Modify: `scripts/reshard.py`
- Test: `tests/test_reshard.py`

**Dépend de Task 1** (`collect_facts` doit porter `local`).

- [ ] **Step 1: Écrire les tests qui échouent**

Dans `tests/test_reshard.py`, ajouter une classe. Helper d'écriture de fait local + lecture d'index :

```python
class LocalFactTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _w(self, rel, name, desc, local=False, typ="project"):
        loc = "  local: true\n" if local else ""
        body = ("---\nname: %s\ndescription: %s\nmetadata:\n  type: %s\n%s---\nx\n"
                % (name, desc, typ, loc))
        p = os.path.join(self.vault, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)

    def test_local_fact_preserved_and_unindexed(self):
        self._w("mailing/partage.md", "partage", "fait partageable du mailing")
        self._w("mailing/prive.md", "prive", "fait local a garder", local=True)
        rsh.reshard(self.vault)
        # le fait local existe toujours physiquement
        self.assertTrue(os.path.exists(os.path.join(self.vault, "mailing", "prive.md")))
        # il n'apparaît dans AUCUN index
        idx = ""
        for root, _d, files in os.walk(os.path.join(self.vault, "index")):
            for fn in files:
                with open(os.path.join(root, fn), encoding="utf-8") as fh:
                    idx += fh.read()
        self.assertIn("partage", idx)
        self.assertNotIn("prive", idx)

    def test_local_only_domain_survives(self):
        self._w("secret/seul.md", "seul", "unique fait du domaine, local", local=True)
        rsh.reshard(self.vault)
        self.assertTrue(os.path.exists(os.path.join(self.vault, "secret", "seul.md")))
```

Note : le module reshard est déjà chargé en haut de `tests/test_reshard.py` (vérifier le nom de l'alias — `rsh` ou autre — et l'utiliser).

- [ ] **Step 2: Vérifier l'échec**

Run: `python3 -m unittest tests.test_reshard.LocalFactTest -v`
Expected: FAIL — `test_local_fact_preserved_and_unindexed` casse : soit `prive` apparaît dans l'index, soit le fichier `prive.md` a disparu (rmtree du domaine sans passthrough), soit `collect_facts` n'a pas `local` (Task 1 requise).

- [ ] **Step 3: Implémenter — `_semantic_tree` collecte les locaux**

Dans `scripts/reshard.py`, remplacer la fonction `_semantic_tree` par :

```python
def _semantic_tree(vault):
    """Arbre des dossiers sémantiques. Renvoie (root, perso, local).
    root : {domaine: node} ; node = {'facts': [...], 'children': {nom: node}}.
    perso : faits user/feedback égarés en domaine (relogés en racine).
    local : [(relpath, raw)] des faits `metadata.local: true` — passthrough : réécrits à leur
            place, hors arbre/index/seuil (sinon le rmtree(vault/<domaine>) les détruirait)."""
    facts, _ = bv.collect_facts(vault, include_body=False)
    root, perso, local = {}, [], []
    for fa in facts:
        if not fa["path"]:
            continue
        raw = _read_raw(os.path.join(vault, fa["file"]))
        if fa.get("local"):
            local.append((fa["file"], raw))
            continue
        fa = dict(fa, raw=raw)
        if fa["type"] in ("user", "feedback"):
            perso.append(fa)
            continue
        segs = _semantic_segments(fa["path"])
        if not segs:
            continue
        children = root
        node = None
        for s in segs:
            node = children.setdefault(s, {"facts": [], "children": {}})
            children = node["children"]
        node["facts"].append(fa)
    return root, perso, local
```

- [ ] **Step 4: Implémenter — `_plan_layout` réécrit les locaux en place**

Dans `scripts/reshard.py`, dans `_plan_layout`, remplacer la ligne :

```python
    root, perso = _semantic_tree(vault)
```
par :
```python
    root, perso, local = _semantic_tree(vault)
```
et, juste avant le `reloc = []` (donc après la boucle `for domain in sorted(root):`), ajouter :
```python
    files.extend(local)        # faits locaux : réécrits à leur chemin d'origine, hors index/counts
```

- [ ] **Step 5: Vérifier le succès**

Run: `python3 -m unittest tests.test_reshard -v`
Expected: PASS — `LocalFactTest` 2/2 + tous les tests reshard existants (compat ascendante : aucun fait local → `local=[]`, sortie identique).

- [ ] **Step 6: Gate + commit**

```bash
python3 -W error::ResourceWarning -m unittest discover -s tests
git add scripts/reshard.py tests/test_reshard.py
git commit -m "feat(reshard): faits local préservés en passthrough, hors index et seuil

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `sm_count_unpromoted` saute les faits `local`

**Files:**
- Modify: `scripts/lib.sh`
- Test: `tests/test_hooks.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Dans `tests/test_hooks.py`, classe `CountUnpromotedTest` (helpers `git`, `write`, `init_repo`, `count_unpromoted`, constante `FACT` déjà présents), ajouter :

```python
    def test_local_fact_not_counted(self):
        write(self.c, "mailing/loc.md",
              "---\nname: loc\ndescription: d\nmetadata:\n  type: project\n  local: true\n---\nx\n")
        # un fait project local nouveau ne doit PAS compter
        self.assertEqual(count_unpromoted(self.c), "0")

    def test_non_local_project_still_counted(self):
        write(self.c, "mailing/shared.md", FACT % ("shared", "project"))
        self.assertEqual(count_unpromoted(self.c), "1")
```

(Rappel `setUp` de `CountUnpromotedTest` : le vault a déjà `mailing/a.md` commité, working tree propre → base 0.)

- [ ] **Step 2: Vérifier l'échec**

Run: `python3 -m unittest tests.test_hooks.CountUnpromotedTest -v`
Expected: FAIL — `test_local_fact_not_counted` renvoie `1` (le fait local est compté).

- [ ] **Step 3: Implémenter**

Dans `scripts/lib.sh`, fonction `sm_count_unpromoted`, après la ligne qui lit `type` et le `case "$type" in user|feedback) continue ;; esac`, ajouter la lecture du drapeau `local` :

```bash
    case "$type" in user|feedback) continue ;; esac
    local loc
    loc="$(sed -n 's/^[[:space:]]*local:[[:space:]]*//p' "$clone/$path" 2>/dev/null | head -1)"
    case "$loc" in true|True|TRUE) continue ;; esac
    n=$((n + 1))
```

(Remplacer la séquence existante `case "$type" … ;; esac` puis `n=$((n + 1))` par le bloc ci-dessus ; ne pas dupliquer `n=$((n + 1))`.)

- [ ] **Step 4: Vérifier le succès**

Run: `python3 -m unittest tests.test_hooks.CountUnpromotedTest -v`
Expected: PASS (anciens + les 2 nouveaux).

- [ ] **Step 5: Gate + commit**

```bash
python3 -W error::ResourceWarning -m unittest discover -s tests
git add scripts/lib.sh tests/test_hooks.py
git commit -m "feat(lib): sm_count_unpromoted ignore les faits local

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `lint` tolère + valide `metadata.local`

**Files:**
- Modify: `scripts/lint.py`
- Test: `tests/test_lint.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Dans `tests/test_lint.py` (helpers `lint`, `write`, `rules_for`, `CLEAN` déjà présents), ajouter :

```python
class LintLocalFlagTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_local_true_no_finding(self):
        write(os.path.join(self.vault, "mailing", "a.md"),
              "---\nname: a-loc\ndescription: Un fait local bien forme ici\n"
              "metadata:\n  type: project\n  reviewed: 2026-06-01\n  local: true\n---\nc\n")
        self.assertNotIn("local_malformed", rules_for(lint.lint_vault(self.vault)))

    def test_local_garbage_warns(self):
        write(os.path.join(self.vault, "mailing", "b.md"),
              "---\nname: b-loc\ndescription: Valeur local invalide ici aussi\n"
              "metadata:\n  type: project\n  reviewed: 2026-06-01\n  local: oui\n---\nc\n")
        findings = lint.lint_vault(self.vault)
        self.assertIn("local_malformed", rules_for(findings))
        self.assertTrue(all(f["severity"] != "error" for f in findings if f["rule"] == "local_malformed"))
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python3 -m unittest tests.test_lint.LintLocalFlagTest -v`
Expected: FAIL — `test_local_garbage_warns` ne trouve pas `local_malformed`.

- [ ] **Step 3: Implémenter**

Dans `scripts/lint.py`, fonction `_lint_fact`, ajouter (par exemple juste après le bloc `reviewed`) :

```python
    local_val = fm.get("metadata.local") or fm.get("local")
    if local_val is not None and str(local_val).strip().lower() not in ("true", "false"):
        out.append(_finding(rel, "local_malformed", "warn", False,
                            "`local: %s` doit valoir `true` ou `false`." % local_val))
```

- [ ] **Step 4: Vérifier le succès**

Run: `python3 -m unittest tests.test_lint -v`
Expected: PASS (anciens + `LintLocalFlagTest`).

- [ ] **Step 5: Gate + commit**

```bash
python3 -W error::ResourceWarning -m unittest discover -s tests
git add scripts/lint.py tests/test_lint.py
git commit -m "feat(lint): tolère metadata.local, warn si valeur invalide

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `serve-viewer` écrit/accepte `local`

**Files:**
- Modify: `scripts/serve-viewer.py`
- Test: `tests/test_serve_viewer.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Dans `tests/test_serve_viewer.py`, repérer le pattern existant qui appelle `create_fact`/`update_fact` (module chargé, vault jetable). Ajouter des tests vérifiant que `local` est écrit dans le frontmatter et relu, et qu'un fait local n'apparaît pas dans l'index après reshard. Modèle (adapter aux helpers du fichier — nom du module `sv`/`serve`, helper de vault) :

```python
class LocalFlagTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_create_local_writes_flag(self):
        sv.create_fact(self.vault, {"name": "loc", "description": "fait local du viewer",
                                    "type": "project", "domain": "mailing", "local": True, "body": "x"})
        with open(os.path.join(self.vault, "mailing", "loc.md"), encoding="utf-8") as f:
            txt = f.read()
        self.assertIn("local: true", txt)

    def test_create_without_local_has_no_flag(self):
        sv.create_fact(self.vault, {"name": "norm", "description": "fait normal du viewer",
                                    "type": "project", "domain": "mailing", "body": "x"})
        with open(os.path.join(self.vault, "mailing", "norm.md"), encoding="utf-8") as f:
            txt = f.read()
        self.assertNotIn("local:", txt)

    def test_local_fact_absent_from_index(self):
        sv.create_fact(self.vault, {"name": "loc2", "description": "local hors index",
                                    "type": "project", "domain": "mailing", "local": True, "body": "x"})
        sv.create_fact(self.vault, {"name": "pub", "description": "partage donc indexe",
                                    "type": "project", "domain": "mailing", "body": "x"})
        idx = ""
        for root, _d, files in os.walk(os.path.join(self.vault, "index")):
            for fn in files:
                with open(os.path.join(root, fn), encoding="utf-8") as fh:
                    idx += fh.read()
        self.assertIn("pub", idx)
        self.assertNotIn("loc2", idx)
```

(`create_fact` appelle `reshard` en interne — l'index reflète donc déjà l'exclusion.)

- [ ] **Step 2: Vérifier l'échec**

Run: `python3 -m unittest tests.test_serve_viewer.LocalFlagTest -v`
Expected: FAIL — `test_create_local_writes_flag` : `local: true` absent (le drapeau n'est pas écrit).

- [ ] **Step 3: Implémenter — `_fact_text` + `_validate` + appels**

Dans `scripts/serve-viewer.py` :

a) `_fact_text` — ajouter un paramètre `local=False` et la ligne conditionnelle sous `metadata:` :

```python
def _fact_text(name, description, type_, body, reviewed=None, local=False):
    reviewed = reviewed or datetime.date.today().isoformat()
    loc = "  local: true\n" if local else ""
    return ("---\nname: %s\ndescription: %s\nmetadata:\n  type: %s\n  reviewed: %s\n%s---\n%s\n"
            % (name, description, type_, reviewed, loc, body))
```

b) `_validate` — renvoyer aussi `local` (coercition souple). Remplacer le `return` final par :

```python
    local = data.get("local") is True or str(data.get("local") or "").strip().lower() == "true"
    return name, typ, local, desc, data.get("body", "") or ""
```

et adapter la signature des appelants : dans `create_fact` et `update_fact`, remplacer
`name, typ, domain, desc, body = _validate(data)` — ATTENTION : `_validate` renvoie déjà `domain`.
Vérifier l'ordre RÉEL du `return` de `_validate` dans le fichier (il renvoie `name, typ, domain, desc, body`). Donc insérer `local` de façon cohérente : faire renvoyer `_validate` →
`name, typ, domain, local, desc, body` et mettre à jour les deux appelants :

```python
    name, typ, domain, local, desc, body = _validate(data)
```

puis passer `local` à `_fact_text` dans `create_fact` et `update_fact` :

```python
        f.write(_fact_text(name, desc, typ, body, local=local))
```

(Conserver l'ordre des arguments positionnels existant de `_fact_text` : `(name, desc, typ, body)` puis `local=local` en mot-clé.)

- [ ] **Step 4: Vérifier le succès**

Run: `python3 -m unittest tests.test_serve_viewer -v`
Expected: PASS (anciens + `LocalFlagTest`).

- [ ] **Step 5: Gate + commit**

```bash
python3 -W error::ResourceWarning -m unittest discover -s tests
git add scripts/serve-viewer.py tests/test_serve_viewer.py
git commit -m "feat(viewer): create/update écrivent le drapeau local

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Viewer — badge « local » + case à cocher

**Files:**
- Modify: `assets/viewer-template.html`
- Test: `tests/test_serve_viewer.py` (assertion sur le template rendu, façon `ViewerGuideTest`)

- [ ] **Step 1: Écrire le test qui échoue**

Dans `tests/test_serve_viewer.py`, ajouter un test qui vérifie que le template contient la case à cocher et le rendu du badge (le template est un fichier statique ; lire son contenu) :

```python
class TemplateLocalUITest(unittest.TestCase):
    def test_template_has_local_controls(self):
        tmpl = os.path.join(os.path.dirname(__file__), "..", "assets", "viewer-template.html")
        with open(tmpl, encoding="utf-8") as f:
            html = f.read()
        self.assertIn("d-local", html)      # case à cocher du formulaire de création
        self.assertIn("e-local", html)      # case à cocher du formulaire d'édition
        self.assertIn("localBadge", html)   # helper de rendu du badge
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python3 -m unittest tests.test_serve_viewer.TemplateLocalUITest -v`
Expected: FAIL — `d-local`/`e-local`/`localBadge` absents.

- [ ] **Step 3: Implémenter — case à cocher (création + édition)**

Dans `assets/viewer-template.html` :

a) Formulaire de **création** : après la ligne du champ `type` (`<select id="d-type">…`), ajouter une ligne case à cocher (les `user`/`feedback` étant déjà locaux, la case ne concerne en pratique que `project`/`reference`, mais on la laisse toujours visible — simple) :

```html
      <label><input type="checkbox" id="d-local"> fait local (ne pas partager)</label>
```

b) Formulaire d'**édition** (`editFact`) : après la ligne `<select id="e-type">…`, ajouter (pré-coché selon `f.local`) :

```html
      <label><input type="checkbox" id="e-local" ${f.local ? 'checked' : ''}> fait local (ne pas partager)</label>
```

c) **Payloads** : dans le submit de création, ajouter `local: $('d-local').checked` à l'objet envoyé à `POST /api/fact` ; dans le submit d'édition, ajouter `local: $('e-local').checked` à l'objet envoyé à `PUT /api/fact`.

- [ ] **Step 4: Implémenter — badge**

Ajouter un helper près de `function badge(t){…}` :

```javascript
function localBadge(f){ return f.local ? `<span class="fresh-badge todo" title="non partagé">local</span>` : ''; }
```

Puis l'insérer dans le rendu d'un fait : à côté du `fresh-badge` de fraîcheur dans la liste ET dans la vue détail (rechercher les occurrences de `freshness(` qui produisent un `<span class="fresh-badge …">` et ajouter `${localBadge(f)}` juste avant ou après). Utiliser la variable de fait disponible dans chaque contexte (`f`).

- [ ] **Step 5: Vérifier le test + `node --check` du rendu**

Run: `python3 -m unittest tests.test_serve_viewer.TemplateLocalUITest -v`
Expected: PASS.

Vérifier que le JS reste valide en rendant le template (le placeholder `/*__DATA__*/` → JSON minimal) puis `node --check` :

```bash
python3 - <<'PY'
import re
html = open("assets/viewer-template.html", encoding="utf-8").read()
html = html.replace("/*__DATA__*/", '{"facts":[],"index":"","vault":"/tmp","count":0,"token":"x"}')
m = re.search(r"<script>(.*)</script>", html, re.S)
open("/tmp/_v.js", "w").write(m.group(1))
print("script extrait")
PY
node --check /tmp/_v.js && echo "JS_OK"
```
Expected: `JS_OK`.

- [ ] **Step 6: Vérification visuelle manuelle (facultative mais recommandée)**

Lancer le viewer sur un vault jetable, créer un fait coché « local », vérifier le badge et l'absence dans l'index. (Non automatisé.)

- [ ] **Step 7: Gate + commit**

```bash
python3 -W error::ResourceWarning -m unittest discover -s tests
git add assets/viewer-template.html tests/test_serve_viewer.py
git commit -m "feat(ui): badge local + case à cocher dans les formulaires

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Skill `memory-promote` + docs

**Files:**
- Modify: `skills/memory-promote/SKILL.md`
- Modify: `docs/domain-convention.md`, `docs/ARCHITECTURE.md`

- [ ] **Step 1: Réviser la procédure de la skill**

Dans `skills/memory-promote/SKILL.md` :

a) **Étape « Filtrer par type »** : ajouter l'exclusion des faits locaux. Remplacer le texte de l'étape de filtrage par :

```markdown
3. **Filtrer.** Lire le frontmatter de chaque candidat. **Ne garder que** `metadata.type: project`
   ou `reference`. **Exclure** `user`, `feedback`, tout `feedback_*.md`, **et tout fait
   `metadata.local: true`** (faits gardés en local, jamais partagés).
```

b) **Nouvelle étape de sélection interactive** (à insérer juste après le filtre, avant la vérif sémantique) :

```markdown
4. **Sélection interactive.** Présenter la liste des candidats restants. Demander à l'utilisateur
   s'il veut **exclure** certains faits de cette promotion. Pour chaque fait exclu, demander :
   - **« toujours »** → poser `metadata.local: true` sur le fait dans le vault (il sort des candidats
     et du compteur, durablement) ;
   - **« cette fois »** → ne pas l'inclure dans cette proposition (aucun drapeau ; il restera candidat
     au prochain promote).
   Les faits restants après ce tri sont les **faits sélectionnés**.
```

c) **Construction de la branche (worktree A)** : remplacer l'étape « Créer la branche + commit + push »
par une construction en worktree propre (re-numéroter les étapes en conséquence) :

```markdown
7. **Construire la proposition dans un worktree propre** (l'index poussé ne contiendra que les faits
   sélectionnés ; le vault local n'est pas muté) :

   ```bash
   tmp="$(mktemp -d)"
   git -C "<clone>" fetch origin
   git -C "<clone>" worktree add --detach "$tmp" origin/main
   # copier dans $tmp UNIQUEMENT les faits sélectionnés, à leur chemin relatif (mkdir -p au besoin)
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/reshard.py "$tmp"      # index propre, sans les exclus/local
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/lint.py "$tmp"         # advisory
   git -C "$tmp" checkout -b promote/<slug>-<court-descriptif>
   git -C "$tmp" add -A
   git -C "$tmp" commit -m "memory: <résumé>"
   git -C "$tmp" push -u origin HEAD
   git -C "<clone>" worktree remove "$tmp" && git -C "<clone>" worktree prune
   ```

   Si un **nouveau domaine** apparaît, ajouter sa ligne à `MEMORY.md` (dans `$tmp`) avant le commit.
```

d) Mettre à jour la section « Points d'attention » : ajouter une puce « **Faits `local`** : exclus de
toute promotion (drapeau `metadata.local: true`) ; réglable via le viewer ou la sélection interactive. »

- [ ] **Step 2: Documenter le drapeau**

Dans `docs/domain-convention.md`, ajouter une courte section :

```markdown
## Faits locaux (`metadata.local`)

Un fait portant `metadata.local: true` dans son frontmatter est **gardé en local** : jamais proposé
par `/memory-promote`, non compté dans « N non promu », et **ignoré par reshard** (préservé en place,
hors `index/`). Utile pour un fait projet sensible ou pas encore prêt à être partagé. Réglable dans le
viewer (case « fait local ») ou à la main. Retirer le drapeau le rend de nouveau partageable.
```

Dans `docs/ARCHITECTURE.md`, dans la section gouvernance/promotion, ajouter une phrase :

```markdown
Un fait peut être **gardé en local** via `metadata.local: true` (jamais promu, hors index, hors
compteur) ; `/memory-promote` propose une exclusion **ponctuelle** (cette fois) ou **durable** (pose
le drapeau) et construit sa branche dans un **worktree propre depuis `origin/main`** pour que l'index
poussé ne référence que les faits choisis.
```

- [ ] **Step 3: Vérifier la cohérence**

Run: `grep -rn "metadata.local\|fait local\|worktree" skills/memory-promote/SKILL.md docs/domain-convention.md docs/ARCHITECTURE.md`
Expected: le drapeau et le worktree apparaissent dans les trois fichiers.

Run (rien ne doit casser) : `python3 -W error::ResourceWarning -m unittest discover -s tests`
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add skills/memory-promote/SKILL.md docs/domain-convention.md docs/ARCHITECTURE.md
git commit -m "docs(promote): faits locaux (exclusion ponctuelle/durable) + worktree

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review (auteur du plan)

**1. Couverture de la spec :**
- Drapeau `metadata.local` source de vérité → Task 1 (collect_facts) + utilisé partout. ✓
- reshard ignore/préserve (passthrough anti-perte) → Task 2 + test de non-perte. ✓
- compteur saute les local → Task 3. ✓
- lint tolère + valide → Task 4. ✓
- serve-viewer écrit/accepte → Task 5 ; viewer badge + case → Task 6. ✓
- skill promote (filtre + sélection ponctuel/durable + worktree A) → Task 7. ✓
- docs (domain-convention, ARCHITECTURE, skill) → Task 7. ✓
- digest inchangé (hors scope) → aucune tâche, conforme. ✓

**2. Placeholders :** aucun « TBD » ; chaque étape de code montre le code. Task 5/6 demandent de vérifier l'ordre réel d'un `return`/d'un rendu dans le fichier (le code exact est fourni, l'ancrage est à confirmer par lecture) — acceptable car le fichier varie.

**3. Cohérence des noms :** `metadata.local` partout ; `_semantic_tree` → `(root, perso, local)` (Task 2) ; `_fact_text(..., local=False)` et `_validate` → `name, typ, domain, local, desc, body` (Task 5) ; `d-local`/`e-local`/`localBadge` (Task 6). Cohérent entre tâches.
