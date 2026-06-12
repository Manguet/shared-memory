# Sous-domaines sémantiques + formulaire amélioré Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Des sous-domaines sémantiques (`mailing/transactionnel`) qui tiennent (reshard les préserve, hybride avec `part-NN`), + un formulaire de création/édition avec slug à la frappe et combobox domaine (autocomplete + « Créer »).

**Architecture :** `reshard` devient conscient de l'arbre sémantique (chemin moins `part-NN`) et matérialise un index mixte (faits + nœuds). `serve-viewer` accepte un domaine multi-segments (refus `part-NN`). Le viewer slugifie à la frappe et remplace la datalist par un combobox maison. Compat ascendante stricte : un vault plat produit une sortie identique.

**Tech Stack :** Python 3 (stdlib), HTML/CSS/JS vanilla (viewer), `unittest`.

**Référence design :** `docs/superpowers/specs/2026-06-12-semantic-subdomains-design.md`.

**Convention du programme :** doc ET tests à jour (cf. mémoire `chantier-doc-tests-convention`).

---

## File Structure

| Fichier | Responsabilité | Action |
|---|---|---|
| `scripts/reshard.py` | arbre sémantique + matérialisation hybride + index mixte. | Modifier |
| `scripts/serve-viewer.py` | `DOMAIN_RE` multi-segments + refus `part-NN`. | Modifier |
| `assets/viewer-template.html` | `slugify()` à la frappe + combobox domaine. | Modifier |
| `tests/test_reshard.py`, `tests/test_serve_viewer.py` | couverture du nouveau modèle. | Modifier |
| `docs/domain-convention.md`, `docs/ARCHITECTURE.md` | documenter. | Modifier |

**Conventions/code existant réutilisé :**
- `reshard.py` : `split_tree(items, n)`, `balanced_chunks`, `_count_leaf_facts(split_node)`, `_read_raw`, `_ensure_memory`, `reshard()` (staging→swap), `STAGING_DIRNAME`. **Les tests existants n'appellent que `split_tree` et `reshard()`** → on peut refondre les internes sans les casser.
- `build-viewer.py` : `collect_facts(vault, include_body=False)` (chaque fait : `file/name/description/type/path`), exclut déjà `.reshard-staging`.
- `serve-viewer.py` : `SLUG_RE`, `TYPES`, `_validate`, `_rel_for`, `_safe_path`.

---

## Task 1 : reshard — arbre sémantique + matérialisation hybride

**Files:**
- Modify: `scripts/reshard.py`
- Modify: `tests/test_reshard.py`

- [ ] **Step 1 : Écrire les tests du nouveau modèle (`tests/test_reshard.py`)**

Ajouter cette classe **avant** le `if __name__` final (le fichier importe déjà `os`, `unittest`, `Path`, et `R`) :

```python
def _wf(vault, rel, name, desc="desc", typ="project"):
    p = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    Path(p).write_text(
        "---\nname: %s\ndescription: %s\nmetadata:\n  type: %s\n  reviewed: 2026-06-01\n---\nx\n"
        % (name, desc, typ), encoding="utf-8")


def _facts_on_disk(vault):
    out = []
    for root, _d, files in os.walk(vault):
        for fn in files:
            if fn.endswith(".md") and os.path.basename(root) != "index" and "index" not in os.path.relpath(root, vault).split(os.sep):
                rel = os.path.relpath(os.path.join(root, fn), vault)
                if rel != "MEMORY.md" and not rel.startswith("index" + os.sep):
                    out.append(rel)
    return sorted(out)


class SemanticSubdomainTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._t = tempfile.TemporaryDirectory()
        self.v = self._t.name

    def tearDown(self):
        self._t.cleanup()

    def test_semantic_subdomain_is_preserved(self):
        _wf(self.v, "mailing/transactionnel/relances.md", "relances")
        _wf(self.v, "mailing/audit.md", "audit")
        R.reshard(self.v, max_entries=50)
        self.assertTrue(os.path.isfile(os.path.join(self.v, "mailing", "transactionnel", "relances.md")))
        self.assertTrue(os.path.isfile(os.path.join(self.v, "mailing", "audit.md")))
        idx = Path(os.path.join(self.v, "index", "mailing.md")).read_text(encoding="utf-8")
        self.assertIn("transactionnel", idx)                       # le sous-domaine est listé
        self.assertIn("index/mailing/transactionnel.md", idx)
        sub = Path(os.path.join(self.v, "index", "mailing", "transactionnel.md")).read_text(encoding="utf-8")
        self.assertIn("relances", sub)

    def test_hybrid_partnn_inside_a_subdomain(self):
        for i in range(5):
            _wf(self.v, "mailing/transactionnel/f%d.md" % i, "f%d" % i)
        R.reshard(self.v, max_entries=2)                            # 5 > 2 -> part-NN DANS transactionnel
        parts = [d for d in os.listdir(os.path.join(self.v, "mailing", "transactionnel"))
                 if d.startswith("part-")]
        self.assertTrue(parts, "le sous-domaine qui déborde doit être scindé en part-NN")

    def test_mixed_subdomain_and_overflowing_direct_facts(self):
        _wf(self.v, "mailing/transactionnel/x.md", "x")            # enfant sémantique
        for i in range(5):
            _wf(self.v, "mailing/d%d.md" % i, "d%d" % i)           # faits directs qui débordent
        R.reshard(self.v, max_entries=2)
        # transactionnel préservé, ET part-NN pour les faits directs de mailing
        self.assertTrue(os.path.isdir(os.path.join(self.v, "mailing", "transactionnel")))
        parts = [d for d in os.listdir(os.path.join(self.v, "mailing")) if d.startswith("part-")]
        self.assertTrue(parts)
        idx = Path(os.path.join(self.v, "index", "mailing.md")).read_text(encoding="utf-8")
        self.assertIn("transactionnel", idx)                       # l'index liste enfant + part-NN
        self.assertTrue(any(("part-" in line) for line in idx.splitlines()))

    def test_mechanical_partnn_is_rederived(self):
        # un fait déjà dans un part-NN (peu nombreux) -> collapse au domaine
        _wf(self.v, "mailing/part-01/a.md", "a")
        _wf(self.v, "mailing/part-02/b.md", "b")
        R.reshard(self.v, max_entries=50)
        self.assertTrue(os.path.isfile(os.path.join(self.v, "mailing", "a.md")))
        self.assertTrue(os.path.isfile(os.path.join(self.v, "mailing", "b.md")))
        self.assertFalse(os.path.isdir(os.path.join(self.v, "mailing", "part-01")))
```

- [ ] **Step 2 : Lancer — échec attendu**

Run : `python3 -m unittest tests.test_reshard.SemanticSubdomainTest -v`
Expected : FAIL (reshard aplatit encore `mailing/transactionnel` → fichiers absents / index sans `transactionnel`).

- [ ] **Step 3 : Refondre `scripts/reshard.py`**

3a. Ajouter, après les imports, la constante :
```python
PART_RE = re.compile(r"^part-\d+$")
```
(Si `re` n'est pas importé en tête de `reshard.py`, l'ajouter : `import re`.)

3b. **Remplacer** la fonction `_domain_facts(vault)` par les fonctions sémantiques :
```python
def _semantic_segments(path):
    """Chemin de dossiers sémantique d'un fait : son path moins les segments `part-NN`."""
    return [s for s in path if not PART_RE.match(s)]


def _semantic_tree(vault):
    """Arbre des dossiers sémantiques. Renvoie (root, perso).
    root : {domaine: node} ; node = {'facts': [...], 'children': {nom: node}}.
    Les faits perso (user/feedback) égarés en domaine sont renvoyés à part (relogés en racine)."""
    facts, _ = bv.collect_facts(vault, include_body=False)
    root, perso = {}, []
    for fa in facts:
        if not fa["path"]:                       # fait déjà à la racine -> laissé tel quel
            continue
        fa = dict(fa, raw=_read_raw(os.path.join(vault, fa["file"])))
        if fa["type"] in ("user", "feedback"):
            perso.append(fa)
            continue
        segs = _semantic_segments(fa["path"])
        if not segs:                             # entièrement mécanique (cas dégénéré) -> ignoré
            continue
        children = root
        node = None
        for s in segs:
            node = children.setdefault(s, {"facts": [], "children": {}})
            children = node["children"]
        node["facts"].append(fa)
    return root, perso


def _count_node_facts(node):
    """Total des faits sous un nœud sémantique (directs + tous descendants)."""
    return len(node["facts"]) + sum(_count_node_facts(c) for c in node["children"].values())
```

3c. **Remplacer** `_materialize(node, segments)` (matérialiseur part-NN, entrées désormais **taguées**) :
```python
def _materialize(node, segments):
    """Matérialise un sous-arbre `split_tree` (faits) en part-NN. Renvoie (placements, indexes).
    placements : [(relpath, raw)]. indexes : [(seg, entries)] ; entries taguées ('fact'|'node')."""
    seg = "/".join(segments)
    placements, indexes, entries = [], [], []
    if "leaf" in node:
        for fa in node["leaf"]:
            rel = seg + "/" + fa["name"] + ".md"
            placements.append((rel, fa["raw"]))
            entries.append(("fact", fa["name"], fa["description"], fa["type"], rel))
    else:
        children = node["children"]
        w = max(2, len(str(len(children))))
        for i, child in enumerate(children):
            label = "part-%0*d" % (w, i + 1)
            child_seg = segments + [label]
            sub_p, sub_i = _materialize(child, child_seg)
            placements.extend(sub_p)
            indexes.extend(sub_i)
            entries.append(("node", label, _count_leaf_facts(child), "/".join(child_seg)))
    indexes.append((seg, entries))
    return placements, indexes


def _materialize_semantic(node, segments, max_entries):
    """Matérialise un nœud sémantique : faits directs (leaf ou part-NN si débordement) + enfants
    sémantiques. Renvoie (placements, indexes) ; l'index du nœud est MIXTE (faits + nœuds)."""
    seg = "/".join(segments)
    placements, indexes, entries = [], [], []
    direct = sorted(node["facts"], key=lambda f: f["name"])
    names = [f["name"] for f in direct]
    if len(names) != len(set(names)):
        raise ValueError("noms en double dans %s" % seg)
    if direct:
        if len(direct) <= max_entries:
            for fa in direct:
                rel = seg + "/" + fa["name"] + ".md"
                placements.append((rel, fa["raw"]))
                entries.append(("fact", fa["name"], fa["description"], fa["type"], rel))
        else:
            sub = split_tree(direct, max_entries)["children"]
            w = max(2, len(str(len(sub))))
            for i, child in enumerate(sub):
                label = "part-%0*d" % (w, i + 1)
                child_seg = segments + [label]
                sub_p, sub_i = _materialize(child, child_seg)
                placements.extend(sub_p)
                indexes.extend(sub_i)
                entries.append(("node", label, _count_leaf_facts(child), "/".join(child_seg)))
    for cname in sorted(node["children"]):
        child_seg = segments + [cname]
        sub_p, sub_i = _materialize_semantic(node["children"][cname], child_seg, max_entries)
        placements.extend(sub_p)
        indexes.extend(sub_i)
        entries.append(("node", cname, _count_node_facts(node["children"][cname]),
                        "/".join(child_seg)))
    indexes.append((seg, entries))
    return placements, indexes
```

3d. **Remplacer** `_index_relpath_content(seg, kind, entries)` par la version **mixte** (signature sans `kind`) :
```python
def _index_relpath_content(seg, entries):
    """(relpath, content) pour index/<seg>.md ; entries mixtes ('fact'|'node')."""
    lines = ["# %s" % seg, ""]
    for e in entries:
        if e[0] == "fact":
            _, name, desc, typ, rel = e
            lines.append("- `%s` — %s · %s → `%s`" % (name, desc, typ, rel))
        else:
            _, label, count, child_seg = e
            lines.append("- %s (%d faits) → index/%s.md" % (label, count, child_seg))
    return (os.path.join("index", seg + ".md"), "\n".join(lines) + "\n")
```

3e. **Remplacer** le corps de `_plan_layout` pour utiliser l'arbre sémantique (la fonction `reshard()` et le staging→swap restent inchangés) :
```python
def _plan_layout(vault, max_entries):
    """Construit en mémoire la TOTALITÉ de la nouvelle structure (sémantique + part-NN) sans rien
    écrire. Renvoie (files, counts, reloc) — voir reshard() pour la sûreté staging→swap."""
    root, perso = _semantic_tree(vault)
    files, counts = [], {}
    for domain in sorted(root):
        placements, indexes = _materialize_semantic(root[domain], [domain], max_entries)
        files.extend(placements)
        for seg, entries in indexes:
            files.append(_index_relpath_content(seg, entries))
        counts[domain] = _count_node_facts(root[domain])
    reloc = []
    for fa in perso:
        rel = fa["name"] + ".md"
        if not os.path.exists(os.path.join(vault, rel)):
            reloc.append((rel, fa["raw"]))
    return files, counts, reloc
```

- [ ] **Step 4 : Lancer le nouveau modèle + la non-régression**

Run : `python3 -m unittest tests.test_reshard -v`
Expected : PASS — les 4 nouveaux tests + **tous les tests existants** (compat ascendante : vault plat → sortie identique).

- [ ] **Step 5 : Commit**

```bash
git add scripts/reshard.py tests/test_reshard.py
git commit -m "feat(reshard): sous-domaines sémantiques préservés (hybride avec part-NN, index mixte)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 : Backend — domaine multi-segments + refus `part-NN`

**Files:**
- Modify: `scripts/serve-viewer.py`
- Modify: `tests/test_serve_viewer.py`

- [ ] **Step 1 : Ajouter les tests (`tests/test_serve_viewer.py`, classe `CreateTest`)**

Insérer ces méthodes après `test_create_invalid_slug_is_400` :
```python
    def test_create_in_subdomain_stays(self):
        r = write_req(self.port, "POST", "/api/fact",
                      {"name": "relances", "type": "project", "description": "relances paniers",
                       "body": "corps", "domain": "mailing/transactionnel"}, token=self._token())
        self.assertEqual(r.status, 200)
        self.assertTrue(os.path.isfile(
            os.path.join(self.vault, "mailing", "transactionnel", "relances.md")))

    def test_create_invalid_domain_is_400(self):
        for bad in ("mailing/Pas-Bon", "mailing//x", "mailing/../x", "mailing/part-01"):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                write_req(self.port, "POST", "/api/fact",
                          {"name": "x", "type": "project", "description": "d", "body": "b", "domain": bad},
                          token=self._token())
            self.assertEqual(cm.exception.code, 400, "domaine accepté à tort : %s" % bad)
```

- [ ] **Step 2 : Lancer — échec attendu**

Run : `python3 -m unittest tests.test_serve_viewer.CreateTest -v`
Expected : FAIL — `mailing/transactionnel` rejeté (400) par le `SLUG_RE` actuel, et `mailing/part-01` accepté à tort.

- [ ] **Step 3 : Modifier `scripts/serve-viewer.py`**

3a. Après `SLUG_RE`, ajouter :
```python
# Domaine : un slug, ou un chemin de sous-domaines (mailing/transactionnel). Chaque segment = slug.
DOMAIN_RE = re.compile(r"^[a-z0-9-]+(/[a-z0-9-]+)*$")
_PART_SEG_RE = re.compile(r"^part-\d+$")
```

3b. Dans `_validate`, **remplacer** la validation du domaine :
```python
    elif domain and not SLUG_RE.match(domain):
        raise ApiError(400, "domaine invalide (slug attendu)")
```
par :
```python
    elif domain:
        if not DOMAIN_RE.match(domain):
            raise ApiError(400, "domaine invalide (slug, ou sous-domaines a-z0-9- séparés par /)")
        if any(_PART_SEG_RE.match(seg) for seg in domain.split("/")):
            raise ApiError(400, "« part-NN » est réservé au découpage automatique (reshard)")
```

- [ ] **Step 4 : Lancer — succès attendu**

Run : `python3 -m unittest tests.test_serve_viewer -v`
Expected : PASS (les nouveaux + tous les CRUD existants). Note : `test_create_in_subdomain_stays` passe car `create_fact` appelle le `reshard` refondu (Task 1) qui **préserve** le sous-domaine.

- [ ] **Step 5 : Commit**

```bash
git add scripts/serve-viewer.py tests/test_serve_viewer.py
git commit -m "feat(viewer): accepter un domaine en sous-domaines (refus part-NN réservé)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 : Frontend — slug à la frappe + combobox domaine

**Files:**
- Modify: `assets/viewer-template.html`

*(Pas de test automatisé : le JS du viewer n'a pas de harnais navigateur en CI. Vérification visuelle en Task 5.)*

- [ ] **Step 1 : Ajouter les helpers `slugify` (près de `esc`, repère : `function esc(`)**

Juste après la fonction `esc(...)`, ajouter :
```javascript
function slugify(s){
  return (s||'').normalize('NFD').replace(/[̀-ͯ]/g,'')   // retire les accents (diacritiques)
    .toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/-+/g,'-').replace(/^-|-$/g,'');
}
function slugifyDomainLive(s){            // slugifie chaque segment, garde le / (sous-domaines)
  return (s||'').split('/').map(slugify).join('/').replace(/\/{2,}/g,'/');
}
function isPart(seg){ return /^part-\d+$/.test(seg); }
function semanticDomains(){              // domaines + sous-domaines sémantiques existants + préfixes
  const set = new Set();
  for(const f of DATA.facts){
    const segs = (f.path||[]).filter(s => !isPart(s));
    for(let i=1;i<=segs.length;i++) set.add(segs.slice(0,i).join('/'));
  }
  return [...set].sort();
}
function bindCombo(id){
  const inp = $(id), pop = $(id+'-pop'); if(!inp || !pop) return;
  let sel = -1;
  const close = () => { pop.classList.add('hidden'); sel = -1; };
  function render(){
    const val = inp.value.replace(/^\/+|\/+$/g,'');
    const all = semanticDomains();
    const filt = all.filter(d => d.includes(val)).slice(0, 50);
    let html = '';
    if(val && !all.includes(val))
      html += `<div class="combo-row combo-create" data-v="${esc(val)}">(Créer) ${esc(val)}</div>`;
    html += filt.map(d => `<div class="combo-row" data-v="${esc(d)}">${esc(d)}</div>`).join('');
    pop.innerHTML = html || `<div class="combo-empty">tape un nom — il sera créé</div>`;
    pop.classList.remove('hidden'); sel = -1;
    pop.querySelectorAll('.combo-row').forEach(r => r.onmousedown = e => {
      e.preventDefault(); inp.value = r.dataset.v; close();
    });
  }
  inp.addEventListener('input', () => { inp.value = slugifyDomainLive(inp.value); render(); });
  inp.addEventListener('focus', render);
  inp.addEventListener('blur', () => setTimeout(close, 120));
  inp.addEventListener('keydown', e => {
    const items = pop.querySelectorAll('.combo-row');
    if(e.key === 'Escape'){ close(); return; }
    if(e.key === 'Enter'){ if(sel>=0 && items[sel]){ inp.value = items[sel].dataset.v; close(); e.preventDefault(); } return; }
    if(e.key === 'ArrowDown') sel = Math.min(items.length-1, sel+1);
    else if(e.key === 'ArrowUp') sel = Math.max(0, sel-1);
    else return;
    items.forEach((r,i) => r.classList.toggle('sel', i===sel));
    if(items[sel]) items[sel].scrollIntoView({block:'nearest'});
    e.preventDefault();
  });
}
```

- [ ] **Step 2 : Ajouter le CSS du combobox (dans le `<style>`, près de `.form` ou en fin de bloc style)**

```css
  .combo { position: relative; }
  .combo-pop { position: absolute; left: 0; right: 0; top: calc(100% + 2px); z-index: 30;
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    max-height: 240px; overflow: auto; box-shadow: 0 8px 24px rgba(0,0,0,.45); }
  .combo-pop.hidden { display: none; }
  .combo-row { padding: 7px 11px; font-size: 13px; cursor: pointer; color: var(--text); }
  .combo-row:hover, .combo-row.sel { background: var(--coral-soft); }
  .combo-create { color: var(--coral); }
  .combo-empty { padding: 7px 11px; font-size: 12.5px; color: var(--muted); }
```

- [ ] **Step 3 : Champ `nom` — slug à la frappe (formulaire DRAFT et EDIT)**

Dans `viewDraft()`, remplacer la ligne du champ nom :
```html
      <label>nom (slug)</label><input id="d-name" placeholder="ex: regle-tva-export" autocomplete="off">
```
par :
```html
      <label>nom (slug)</label><input id="d-name" placeholder="ex: regle-tva-export" autocomplete="off" oninput="this.value=slugify(this.value)">
```
Dans `editFact()`, remplacer :
```html
      <label>nom (slug)</label><input id="e-name" value="${esc(f.name)}">
```
par :
```html
      <label>nom (slug)</label><input id="e-name" value="${esc(f.name)}" oninput="this.value=slugify(this.value)">
```

- [ ] **Step 4 : Champ `domaine` — combobox (formulaire DRAFT et EDIT)**

Dans `viewDraft()`, remplacer :
```html
      <label>domaine</label><input id="d-domain" list="d-domains" placeholder="ex: mailing (vide = général)"><datalist id="d-domains">${domainOptions('')}</datalist>
```
par :
```html
      <label>domaine</label><div class="combo"><input id="d-domain" placeholder="ex: mailing ou mailing/transactionnel (vide = général)" autocomplete="off"><div id="d-domain-pop" class="combo-pop hidden"></div></div>
```
Dans `editFact()`, remplacer :
```html
      <label>domaine</label><input id="e-domain" list="e-domains" value="${esc((f.path||[])[0]||'')}"><datalist id="e-domains">${domainOptions((f.path||[])[0]||'')}</datalist>
```
par :
```html
      <label>domaine</label><div class="combo"><input id="e-domain" value="${esc((f.path||[]).filter(s=>!isPart(s)).join('/'))}" autocomplete="off"><div id="e-domain-pop" class="combo-pop hidden"></div></div>
```
*(Le `value` de l'édition utilise le **chemin sémantique complet** du fait — ses segments hors `part-NN` —, pas seulement `path[0]`.)*

- [ ] **Step 5 : Brancher les combobox après le rendu des formulaires**

Dans `bindDraft()` (la fonction qui câble le formulaire de création), ajouter en début de corps :
```javascript
  bindCombo('d-domain');
```
Dans `editFact()`, juste après l'affectation de `$('main').innerHTML = ...` (avant ou après les `$('e-...').onclick`), ajouter :
```javascript
  bindCombo('e-domain');
```

- [ ] **Step 6 : Nettoyer la saisie domaine à la soumission (créer + éditer)**

Dans `bindDraft()`, le handler de création lit `v('d-domain')`. Le combobox peut laisser un `/` en tête/fin. Sécuriser : juste avant l'appel `api('POST', '/api/fact', …)`, normaliser le domaine. Repérer la ligne :
```javascript
    const meta = await api('POST', '/api/fact', { name:v('d-name'), description:v('d-desc'),
      type:$('d-type').value, body:$('d-body').value, domain:v('d-domain') });
```
et remplacer `domain:v('d-domain')` par `domain:v('d-domain').replace(/^\/+|\/+$/g,'')` (idem dans la ligne suivante qui calcule `state.factId`, remplacer les deux usages de `v('d-domain')` par la version nettoyée — au plus simple, introduire `const dom = v('d-domain').replace(/^\/+|\/+$/g,'');` et utiliser `dom`).

Dans `editFact()`, le handler `e-save` lit `$('e-domain').value.trim()`. Remplacer ses occurrences par `$('e-domain').value.trim().replace(/^\/+|\/+$/g,'')` (les deux usages : dans le `api('PUT', …, {…, domain: …})` et dans le calcul de `state.factId`).

- [ ] **Step 7 : Vérifier la cohérence (pas de référence morte)**

Run :
```bash
cd /var/www/shared-memory
grep -c "domainOptions\|list=\"d-domains\"\|list=\"e-domains\"" assets/viewer-template.html
grep -c "bindCombo\|slugify\|combo-pop" assets/viewer-template.html
```
Expected : la 1ʳᵉ commande renvoie un petit nombre **sans** `list="d-domains"`/`list="e-domains"` restants (la fonction `domainOptions` peut rester définie mais n'est plus utilisée — la supprimer si tu veux, sinon laisser) ; la 2ᵉ renvoie ≥ 3.

- [ ] **Step 8 : Commit**

```bash
git add assets/viewer-template.html
git commit -m "feat(ui): slug à la frappe + combobox domaine (autocomplete sous-domaines + « Créer »)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 : Documentation

**Files:**
- Modify: `docs/domain-convention.md`
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1 : `domain-convention.md` — sous-domaines sémantiques**

Dans `docs/domain-convention.md`, repérer la section sur le sharding / sous-index (qui décrit `index/<domaine>/<sous>.md` et le découpage). À la fin de cette section, ajouter :
```markdown
### Sous-domaines : sémantiques vs mécaniques

Un domaine peut contenir des **sous-domaines sémantiques** — des dossiers que tu nommes
(`mailing/transactionnel`) pour organiser le sens. Ils sont **préservés** par `reshard`.

À côté, `reshard` crée des sous-dossiers **mécaniques** `part-NN` (`part-01`, `part-02`…)
**uniquement** quand les faits *directs* d'un dossier dépassent le seuil (~150), pour garder l'index
lisible. **`part-NN` est un nom réservé** (interdit comme nom de domaine).

**Hybride** : les deux coexistent — un dossier peut avoir des sous-domaines nommés *et* des `part-NN`
pour ses faits directs en surnombre (ex. `mailing/` → `transactionnel/`, `part-01/`, `part-02/`).
Le **domaine sémantique** d'un fait est son chemin de dossiers *moins les segments `part-NN`*.
```

- [ ] **Step 2 : `ARCHITECTURE.md` — note dans la section sharding**

Dans `docs/ARCHITECTURE.md`, dans la section qui décrit le sharding (sous-index / `reshard`), ajouter une note :
```markdown
**Sous-domaines sémantiques** : `reshard` reconnaît les dossiers nommés par l'humain
(`mailing/transactionnel`) et les **préserve** ; il n'applique le découpage mécanique `part-NN` que
sur les faits *directs* d'un dossier qui dépassent le seuil (hybride). `part-NN` est un nom réservé.
Le domaine d'un fait = son chemin moins les segments `part-NN`. Le formulaire du viewer propose les
sous-domaines existants (combobox) et permet d'en créer.
```

- [ ] **Step 3 : Vérifier**

Run : `grep -c "sémantique\|part-NN réservé\|réservé" docs/domain-convention.md docs/ARCHITECTURE.md`
Expected : chaque fichier ≥ 1.

- [ ] **Step 4 : Commit**

```bash
git add docs/domain-convention.md docs/ARCHITECTURE.md
git commit -m "docs: sous-domaines sémantiques vs part-NN mécanique (convention + ARCHITECTURE)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 : Vérification

- [ ] **Step 1 : Suite complète (gate strict)**

Run : `python3 -W error::ResourceWarning -m unittest discover -s . -p 'test_*.py' 2>&1 | tail -3`
Expected : OK — tous les tests passent (existants + nouveaux reshard + serve-viewer).

- [ ] **Step 2 : Fumée bout-en-bout — créer en sous-domaine tient après reshard**

Run :
```bash
TMP=$(mktemp -d); mkdir -p "$TMP/mailing"
printf '# Carte\n\n## Domaines\n- mailing\n' > "$TMP/MEMORY.md"
printf -- '---\nname: audit\ndescription: audit du bundle\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\nx\n' > "$TMP/mailing/audit.md"
mkdir -p "$TMP/mailing/transactionnel"
printf -- '---\nname: relances\ndescription: relances paniers transactionnels\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\nx\n' > "$TMP/mailing/transactionnel/relances.md"
echo "=== reshard ===" ; python3 scripts/reshard.py "$TMP" >/dev/null
echo "sous-domaine préservé ? $([ -f "$TMP/mailing/transactionnel/relances.md" ] && echo oui || echo NON)"
echo "=== index mailing ===" ; cat "$TMP/index/mailing.md"
echo "=== index sous-domaine ===" ; cat "$TMP/index/mailing/transactionnel.md"
rm -rf "$TMP"
```
Expected : `relances.md` **reste** dans `mailing/transactionnel/` ; `index/mailing.md` liste `audit` (fait) **et** `transactionnel` (nœud → `index/mailing/transactionnel.md`) ; l'index du sous-domaine liste `relances`.

- [ ] **Step 3 : Vérification visuelle du viewer (humain)**

Lancer `/memory-ui` sur un vault de test et vérifier, dans **Créer un fait** et **Éditer** :
- taper « Règle TVA Export » dans **nom** → devient `regle-tva-export` à la frappe ;
- le champ **domaine** propose les domaines/sous-domaines existants en tapant, filtre, et affiche
  **« (Créer) … »** pour un nom nouveau ; taper `mailing/promo` cible un sous-domaine ;
- créer un fait dans `mailing/promo` → après rafraîchissement, il est bien sous `mailing/promo`.

---

## Self-Review

**Couverture de la spec :**

| Élément du design | Tâche |
|---|---|
| Domaine sémantique = path moins `part-NN` (`_semantic_segments`) | Task 1 |
| Arbre sémantique préservé (`_semantic_tree`) | Task 1 + `test_semantic_subdomain_is_preserved` |
| Hybride (part-NN dans un dossier qui déborde) | Task 1 + `test_hybrid_partnn_inside_a_subdomain` |
| Mixte (enfant sémantique + part-NN) + index mixte | Task 1 + `test_mixed_…` + `_index_relpath_content` |
| `part-NN` ré-dérivé | Task 1 + `test_mechanical_partnn_is_rederived` |
| Compat ascendante (vault plat identique) | Task 1 Step 4 (19 tests existants) |
| `DOMAIN_RE` multi-segments + refus `part-NN` | Task 2 + tests |
| Créer en sous-domaine tient | Task 2 + `test_create_in_subdomain_stays` + Task 5 fumée |
| `slugify` à la frappe (nom + segments domaine) | Task 3 |
| Combobox (autocomplete sous-domaines + « Créer ») | Task 3 |
| Doc (convention + ARCHITECTURE) | Task 4 |
| Vérification (suite + fumée + visuel) | Task 5 |

**Placeholders :** aucun — code reshard, backend, frontend (JS+CSS+HTML), tests et edits doc fournis intégralement.

**Cohérence des types/signatures :** `_semantic_segments(path) -> list`, `_semantic_tree(vault) -> (root_dict, perso_list)` (node = `{'facts':[], 'children':{}}`), `_count_node_facts(node) -> int`, `_materialize(split_node, segments) -> (placements, indexes)` avec `indexes=[(seg, entries)]` (entries taguées), `_materialize_semantic(node, segments, max) -> (placements, indexes)`, `_index_relpath_content(seg, entries) -> (relpath, content)` — **signature changée** (plus de `kind`), appelée uniquement par `_plan_layout` (cohérent). `reshard()`/staging→swap/`_ensure_memory` inchangés. Côté JS : `slugify`/`slugifyDomainLive`/`isPart`/`semanticDomains`/`bindCombo` cohérents entre helpers, formulaires et handlers. Backend `DOMAIN_RE`/`_PART_SEG_RE` cohérents avec le frontend (`isPart`) et reshard (`PART_RE`).
