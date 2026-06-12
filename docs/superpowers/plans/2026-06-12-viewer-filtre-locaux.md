# Filtre « locaux » dans le viewer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un toggle « locaux » dans la barre de filtres du viewer pour n'afficher que les faits `local: true`.

**Architecture:** Un booléen `state.localOnly` (défaut `false`) ajouté en AND dans `visible()` ; un chip distinct dans `renderFilters` qui le bascule ; l'arbre du sidebar se restreint automatiquement puisqu'il s'appuie déjà sur `visible()`.

**Tech Stack:** JS vanilla (`assets/viewer-template.html`), test d'assertion sur le template (`unittest`), `node --check` pour valider le JS rendu.

---

## Contexte pour l'implémenteur

- Le viewer filtre déjà par type via `state.types` (Set) et `visible() = DATA.facts.filter(f => state.types.has(f.type))`. `rebuildNav()` (arbre du sidebar) s'appuie sur `visible()`.
- `f.local` (booléen) est déjà présent sur chaque fait (livré précédemment).
- Le badge `local` existe déjà ; ici on ajoute seulement le **filtre**.
- Branche de travail : créer `viewer-filtre-locaux` (ne pas implémenter sur `main`).
- Gate : `python3 -W error::ResourceWarning -m unittest discover -s tests` → `OK`.

---

### Task 1: Toggle « locaux » dans les filtres

**Files:**
- Modify: `assets/viewer-template.html` (`state` l.298, `visible()` l.376, `renderFilters` l.384-395)
- Test: `tests/test_serve_viewer.py`

- [ ] **Step 1: Écrire le test qui échoue**

Dans `tests/test_serve_viewer.py`, classe `TemplateLocalUITest` (déjà existante), ajouter une méthode :

```python
    def test_template_has_local_filter(self):
        tmpl = os.path.join(os.path.dirname(__file__), "..", "assets", "viewer-template.html")
        with open(tmpl, encoding="utf-8") as f:
            html = f.read()
        self.assertIn("localOnly", html)   # état + chip du filtre « locaux »
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python3 -m unittest tests.test_serve_viewer.TemplateLocalUITest.test_template_has_local_filter -v`
Expected: FAIL — `localOnly` absent du template.

- [ ] **Step 3: Ajouter l'état `localOnly`**

Dans `assets/viewer-template.html`, remplacer la ligne (l.298) :

```javascript
const state = { view: "home", factId: null, query: "", types: new Set(TYPES), usageStep: 0 };
```

par :

```javascript
const state = { view: "home", factId: null, query: "", types: new Set(TYPES), localOnly: false, usageStep: 0 };
```

- [ ] **Step 4: Filtrer dans `visible()`**

Remplacer la ligne (l.376) :

```javascript
function visible(){ return DATA.facts.filter(f => state.types.has(f.type)); }
```

par :

```javascript
function visible(){ return DATA.facts.filter(f => state.types.has(f.type) && (!state.localOnly || f.local)); }
```

- [ ] **Step 5: Ajouter le chip dans `renderFilters`**

Dans `renderFilters`, juste avant la fin de la fonction (après la boucle `TYPES.forEach(...)`, avant le `}` qui ferme `renderFilters`), insérer :

```javascript
  const nLoc = DATA.facts.filter(f => f.local).length;
  if(nLoc){
    const c = document.createElement('span');
    c.className = 'chip' + (state.localOnly ? '' : ' off');   // actif = mis en avant ; inactif = .off (estompé)
    c.innerHTML = `<span class="dot" style="background:var(--faint)"></span>locaux ${nLoc}`;
    c.onclick = () => { state.localOnly = !state.localOnly; rebuildNav(); update(); };
    el.appendChild(c);
  }
```

- [ ] **Step 6: Vérifier le test + JS valide**

Run: `python3 -m unittest tests.test_serve_viewer.TemplateLocalUITest -v`
Expected: PASS.

Valider le JS rendu :

```bash
python3 - <<'PY'
import re
html = open("assets/viewer-template.html", encoding="utf-8").read()
html = html.replace("/*__DATA__*/", '{"facts":[],"index":"","vault":"/tmp","count":0,"token":"x"}')
m = re.search(r"<script>(.*)</script>", html, re.S)
open("/tmp/_v.js", "w").write(m.group(1))
PY
node --check /tmp/_v.js && echo JS_OK
```
Expected: `JS_OK`.

- [ ] **Step 7: Gate complet**

Run: `python3 -W error::ResourceWarning -m unittest discover -s tests`
Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
git add assets/viewer-template.html tests/test_serve_viewer.py
git commit -m "feat(ui): filtre « locaux » dans la barre de filtres du viewer

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review (auteur du plan)

**1. Couverture de la spec :**
- `state.localOnly` (défaut false) → Step 3. ✓
- `visible()` AND local → Step 4. ✓
- Chip distinct dans `renderFilters` (couleur `--faint`, n'apparaît que s'il y a des locaux, bascule + rebuildNav/update) → Step 5. ✓
- Arbre via `visible()` → automatique (aucune étape nécessaire). ✓
- Test template + `node --check` → Steps 1/6. ✓

**2. Placeholders :** aucun ; tout le code est fourni.

**3. Cohérence des noms :** `state.localOnly` identique entre Steps 3, 4, 5 et le test (Step 1). `f.local`, `--faint`, `rebuildNav`/`update` conformes au code existant.
