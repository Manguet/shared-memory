# SP2 — Fraîcheur / anti-péremption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner aux faits une **date de vérification** (`metadata.reviewed`) stampée automatiquement, et **surfacer les faits périmés** (badge + vue « à revérifier » dans le viewer) pour protéger la confiance dans la mémoire.

**Architecture :** Un champ `metadata.reviewed: AAAA-MM-JJ` exposé par `collect_facts`, stampé à la création/édition par le CRUD (`_fact_text`) et à la vérification par les skills. La péremption (`aujourd'hui − reviewed > 90 j`) est calculée **côté client** dans le viewer (badge + vue périmés) — pas de nouvel endpoint.

**Tech Stack :** Python stdlib (`datetime`), JS vanilla, markdown. Tests : `unittest` (`tests/test_build_viewer.py`, `tests/test_serve_viewer.py`).

**Référence design :** `docs/superpowers/specs/2026-06-11-sp2-freshness-design.md`.

**Convention du programme :** ce chantier inclut la **mise à jour de la doc ET des tests** dans « terminé » (cf. mémoire `chantier-doc-tests-convention`).

---

## File Structure

| Fichier | Responsabilité SP2 | Action |
|---|---|---|
| `assets/fact-template.md` | + champ `reviewed` dans le gabarit. | Modifier |
| `scripts/build-viewer.py` | `collect_facts` expose `fact.reviewed`. | Modifier |
| `scripts/serve-viewer.py` | `_fact_text` stampe `reviewed` ; create/update l'écrivent. | Modifier |
| `assets/viewer-template.html` | badge de fraîcheur + vue « à revérifier ». | Modifier |
| `skills/memory-import`, `memory-promote`, `memory-list` | stamper / re-stamper / signaler. | Modifier |
| `docs/domain-convention.md`, `README.md`, `docs/ARCHITECTURE.md` | documenter la fraîcheur. | Modifier |
| `tests/test_build_viewer.py`, `tests/test_serve_viewer.py` | tests `reviewed`. | Modifier |

---

## Task 1 : `reviewed` exposé par `collect_facts` + gabarit

**Files:**
- Modify: `scripts/build-viewer.py`
- Modify: `assets/fact-template.md`
- Test: `tests/test_build_viewer.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter dans `tests/test_build_viewer.py`, avant `if __name__` (le helper `write` et l'alias `bv` existent déjà en haut du fichier) :

```python
class ReviewedFieldTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_reviewed_exposed_present_and_empty(self):
        write(os.path.join(self.vault, "mailing", "a.md"),
              "---\nname: a\ndescription: d\nmetadata:\n  type: project\n  reviewed: 2026-06-11\n---\nx")
        write(os.path.join(self.vault, "mailing", "b.md"),
              "---\nname: b\ndescription: d\nmetadata:\n  type: project\n---\ny")
        facts, _ = bv.collect_facts(self.vault, include_body=False)
        by = {f["name"]: f for f in facts}
        self.assertEqual(by["a"]["reviewed"], "2026-06-11")
        self.assertEqual(by["b"]["reviewed"], "")
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `python3 -m unittest tests.test_build_viewer.ReviewedFieldTest -v`
Expected : FAIL — `KeyError: 'reviewed'`.

- [ ] **Step 3 : Exposer `reviewed` dans `collect_facts`**

Dans `scripts/build-viewer.py`, dans le dict `fact`, après la ligne `"type": …`, ajouter la clé `reviewed`. Le dict devient :

```python
            fact = {
                "file": rel,
                "name": fm.get("name", fn[:-3]),
                "description": fm.get("description", ""),
                "type": fm.get("metadata.type") or fm.get("type", "project"),
                "reviewed": fm.get("metadata.reviewed") or fm.get("reviewed", ""),
                "domain": domain,
                "path": path,
            }
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `python3 -m unittest tests.test_build_viewer -v`
Expected : PASS (existants + `ReviewedFieldTest`).

- [ ] **Step 5 : Ajouter le champ au gabarit `assets/fact-template.md`**

Remplacer le bloc frontmatter du gabarit :

```markdown
---
name: <slug-kebab-case>
description: <résumé en une ligne — sert à juger la pertinence au recall>
metadata:
  type: project
---
```

par :

```markdown
---
name: <slug-kebab-case>
description: <résumé en une ligne — sert à juger la pertinence au recall>
metadata:
  type: project
  reviewed: <AAAA-MM-JJ — date de dernière vérification du fait contre le code>
---
```

- [ ] **Step 6 : Commit**

```bash
git add scripts/build-viewer.py assets/fact-template.md tests/test_build_viewer.py
git commit -m "feat(freshness): collect_facts expose metadata.reviewed + gabarit

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 : Le CRUD stampe `reviewed` (création + édition)

**Files:**
- Modify: `scripts/serve-viewer.py`
- Test: `tests/test_serve_viewer.py`

- [ ] **Step 1 : Ajouter les tests qui échouent**

Ajouter dans `tests/test_serve_viewer.py`, avant `if __name__` :

```python
import datetime as _dt


class ReviewedStampTest(ServerTestBase):
    def _token(self):
        _, html = self.get("/"); return _token_of(html)

    def test_create_stamps_reviewed_today(self):
        write_req(self.port, "POST", "/api/fact",
                  {"name": "r", "type": "project", "description": "d", "body": "b", "domain": "mailing"},
                  token=self._token())
        txt = open(os.path.join(self.vault, "mailing", "r.md"), encoding="utf-8").read()
        self.assertIn("reviewed: %s" % _dt.date.today().isoformat(), txt)

    def test_update_restamps_reviewed_today(self):
        write_req(self.port, "PUT", "/api/fact?f=mailing/audit.md",
                  {"name": "audit", "type": "project", "description": "d", "body": "b", "domain": "mailing"},
                  token=self._token())
        txt = open(os.path.join(self.vault, "mailing", "audit.md"), encoding="utf-8").read()
        self.assertIn("reviewed: %s" % _dt.date.today().isoformat(), txt)
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `python3 -m unittest tests.test_serve_viewer.ReviewedStampTest -v`
Expected : FAIL — le frontmatter écrit ne contient pas `reviewed:`.

- [ ] **Step 3 : Stamper dans `_fact_text`**

Dans `scripts/serve-viewer.py` : ajouter `import datetime` aux imports. Puis remplacer la fonction `_fact_text` :

```python
def _fact_text(name, description, type_, body):
    return ("---\nname: %s\ndescription: %s\nmetadata:\n  type: %s\n---\n%s\n"
            % (name, description, type_, body))
```

par :

```python
def _fact_text(name, description, type_, body, reviewed=None):
    reviewed = reviewed or datetime.date.today().isoformat()
    return ("---\nname: %s\ndescription: %s\nmetadata:\n  type: %s\n  reviewed: %s\n---\n%s\n"
            % (name, description, type_, reviewed, body))
```

(`create_fact` et `update_fact` appellent déjà `_fact_text(name, desc, typ, body)` → `reviewed` prend la valeur du jour par défaut, donc la création **et** l'édition stampent la date du jour. Aucune autre modification nécessaire.)

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `python3 -m unittest tests.test_serve_viewer -v`
Expected : PASS (existants + `ReviewedStampTest`).

- [ ] **Step 5 : Commit**

```bash
git add scripts/serve-viewer.py tests/test_serve_viewer.py
git commit -m "feat(freshness): le CRUD stampe metadata.reviewed à la création/édition

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 : Viewer — badge de fraîcheur + vue « à revérifier »

**Files:**
- Modify: `assets/viewer-template.html`

UI JS, vérifiée **manuellement** dans le viewer live.

- [ ] **Step 1 : Ajouter le helper de fraîcheur + la constante de seuil**

Dans le `<script>`, après `const $ = id => document.getElementById(id);`, ajouter :

```javascript
const STALE_DAYS = 90;
function freshness(reviewed){
  if(!reviewed) return { cls: 'todo', label: 'à vérifier', days: Infinity };
  const days = Math.floor((Date.now() - Date.parse(reviewed)) / 86400000);
  if(isNaN(days)) return { cls: 'todo', label: 'à vérifier', days: Infinity };
  const stale = days >= STALE_DAYS;
  return { cls: stale ? 'stale' : 'fresh', label: (stale ? '⚠ ' : '✓ ') + 'vérifié il y a ' + days + ' j', days };
}
function isStale(f){ return freshness(f.reviewed).cls !== 'fresh'; }
```

- [ ] **Step 2 : Style des badges**

Dans le `<style>`, après la règle `.badge { … }`, ajouter :

```css
  .fresh-badge { font-size: 10.5px; padding: 3px 9px; border-radius: 999px; border: 1px solid currentColor; white-space: nowrap; }
  .fresh-badge.fresh { color: var(--user); }
  .fresh-badge.stale { color: var(--feedback); }
  .fresh-badge.todo  { color: var(--faint); }
```

- [ ] **Step 3 : Badge sur la carte de détail**

Dans la fonction `showFact(f)`, dans le `fhead`, ajouter le badge juste après `<span class="fname">…</span>`. Remplacer la ligne du `fhead` :

```javascript
    <div class="fhead">${badge(f.type)}<span class="fname">${esc(f.name)}</span>
      <span style="margin-left:auto;display:flex;gap:8px">
```

par :

```javascript
    <div class="fhead">${badge(f.type)}<span class="fname">${esc(f.name)}</span>
      <span class="fresh-badge ${freshness(f.reviewed).cls}">${esc(freshness(f.reviewed).label)}</span>
      <span style="margin-left:auto;display:flex;gap:8px">
```

- [ ] **Step 4 : Vue « à revérifier » + bouton outil**

(a) Ajouter la fonction `viewStale` dans le `<script>` (près de `viewResults`) :

```javascript
function viewStale(){
  const r = visible().filter(isStale)
    .sort((a, b) => freshness(b.reviewed).days - freshness(a.reviewed).days);
  const list = !r.length
    ? `<div class="empty">Aucun fait périmé. 🎉</div>`
    : `<div class="results">` + r.map(f => {
        const fr = freshness(f.reviewed);
        return `<button class="result" data-file="${esc(f.file)}">
          <div class="rh">${badge(f.type)}<span class="rn">${esc(f.name)}</span>
            <span class="fresh-badge ${fr.cls}" style="margin-left:auto">${esc(fr.label)}</span></div>
          <div class="rd">${esc((f.path || []).join(' / ') || 'général')}</div></button>`;
      }).join('') + `</div>`;
  return `<h3 class="view-h">À revérifier</h3>
    <p class="view-p">Faits non vérifiés depuis ≥ ${STALE_DAYS} jours (ou jamais), du plus vieux au plus récent.</p>` + list;
}
```

(b) Brancher la vue dans `renderMain` — ajouter, avant la ligne `if(state.view === 'draft')` :

```javascript
  if(state.view === 'stale'){ m.innerHTML = viewStale(); bindResults(); return; }
```

(c) Ajouter le bouton dans le menu outils HTML (dans `<div class="tools">`), après le bouton `data-view="index"` :

```html
        <button class="toolbtn" data-view="stale"><span class="k">⏱</span>à revérifier</button>
```

- [ ] **Step 5 : Vérification manuelle**

Run :
```bash
rm -rf /tmp/sm-fresh && mkdir -p /tmp/sm-fresh/mailing
printf '%s' '---
name: vieux
description: fait ancien
metadata:
  type: project
  reviewed: 2025-01-01
---
x' > /tmp/sm-fresh/mailing/vieux.md
printf '%s' '---
name: recent
description: fait récent
metadata:
  type: project
  reviewed: '"$(date +%F)"'
---
y' > /tmp/sm-fresh/mailing/recent.md
printf '%s' '---
name: sansdate
description: jamais vérifié
metadata:
  type: project
---
z' > /tmp/sm-fresh/mailing/sansdate.md
python3 scripts/serve-viewer.py /tmp/sm-fresh assets/viewer-template.html 8902 >/dev/null 2>&1 &
echo "Ouvrir http://127.0.0.1:8902 — vérifier : 'recent' = badge vert, 'vieux' = rouge, 'sansdate' = 'à vérifier' ; le bouton '⏱ à revérifier' liste 'vieux' + 'sansdate' (pas 'recent')."
```
Vérifier de visu, puis arrêter le serveur (trouver le PID sur 8902 et le tuer ; ne PAS faire `pkill -f serve-viewer` qui tue le shell parent).

- [ ] **Step 6 : Commit**

```bash
git add assets/viewer-template.html
git commit -m "feat(freshness): viewer — badge de fraîcheur + vue 'à revérifier'

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 : Skills — stamper / re-stamper / signaler

**Files:**
- Modify: `skills/memory-import/SKILL.md`
- Modify: `skills/memory-promote/SKILL.md`
- Modify: `skills/memory-list/SKILL.md`

Markdown. Vérif par relecture + grep.

- [ ] **Step 1 : `memory-import` — stamper `reviewed` à la création**

Dans `skills/memory-import/SKILL.md`, dans l'étape 5 (« Écrire un fichier par fait … en suivant `…/assets/fact-template.md` »), ajouter une puce à la liste des champs :

```markdown
   - `metadata.reviewed` : la **date du jour** (`AAAA-MM-JJ`) — le fait vient d'être écrit/vérifié.
```

- [ ] **Step 2 : `memory-promote` — re-stamper les faits vérifiés**

Dans `skills/memory-promote/SKILL.md`, à la fin de l'étape 4 (« Vérifier sémantiquement chaque fait retenu … Confronter au code actuel »), ajouter :

```markdown
   Pour chaque fait **confirmé vrai** contre le code, mettre à jour son `metadata.reviewed` à la
   **date du jour** (c'est le signal de fraîcheur : « vérifié le … »).
```

- [ ] **Step 3 : `memory-list` — signaler la fraîcheur**

Dans `skills/memory-list/SKILL.md`, dans la section `## Points d'attention`, ajouter une puce :

```markdown
- **Fraîcheur** : chaque fait porte `metadata.reviewed` (date de dernière vérification). **Signaler**
  les faits non vérifiés depuis **≥ 90 jours** ou **sans date** comme « à revérifier » ; sur demande
  « qu'est-ce qui est périmé ? », lister ces faits du plus vieux au plus récent.
```

- [ ] **Step 4 : Vérifier**

Run : `grep -c "reviewed\|fraîcheur\|à revérifier\|revérifier" skills/memory-import/SKILL.md skills/memory-promote/SKILL.md skills/memory-list/SKILL.md`
Expected : chaque fichier ≥ 1.

- [ ] **Step 5 : Commit**

```bash
git add skills/memory-import/SKILL.md skills/memory-promote/SKILL.md skills/memory-list/SKILL.md
git commit -m "feat(freshness): skills stampent/re-stampent/signalent metadata.reviewed

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 : Documentation

**Files:**
- Modify: `docs/domain-convention.md`
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1 : `domain-convention.md` — la règle de fraîcheur**

Dans `docs/domain-convention.md`, juste après la section `## Principe fondateur — l'index aiguille, le fait est la source` (avant `## Structure du vault`), ajouter :

```markdown
## Fraîcheur des faits (`reviewed`)

Chaque fait porte `metadata.reviewed: AAAA-MM-JJ` = **date de dernière vérification contre le code**.
Stampée automatiquement à la **création**, à l'**édition** (viewer CRUD), et au **promote/review**
(qui vérifient le fait). Un fait non vérifié depuis **≥ 90 jours** (ou sans date) est **« à
revérifier »** : la mémoire reste digne de confiance tant que ses faits sont datés et rafraîchis.
Le viewer affiche un badge de fraîcheur et une vue « à revérifier ».
```

- [ ] **Step 2 : `README.md` — une ligne**

Dans `README.md`, à la fin de la liste de la section `## Recherche & passage à l'échelle`, ajouter :

```markdown
- **Fraîcheur** : chaque fait porte une date `reviewed` (vérifié le…) ; le viewer signale les faits **périmés** (≥ 90 j ou jamais vérifiés) via un badge et une vue « à revérifier » → la confiance ne s'érode pas en silence.
```

- [ ] **Step 3 : `docs/ARCHITECTURE.md` — note dans §12**

Dans `docs/ARCHITECTURE.md`, à la **fin de la section `## 12`**, ajouter :

```markdown
### Fraîcheur (anti-péremption)
Chaque fait porte `metadata.reviewed` (date de dernière vérification). Stampée à la création /
édition / promote-review ; un fait non vérifié depuis ≥ 90 j (ou sans date) est signalé « à
revérifier » (badge + vue dédiée dans le viewer, surface dans `/memory-list`). Le but : la confiance
ne s'érode pas en silence — un fait périmé est visible.
```

- [ ] **Step 4 : Vérifier**

Run : `grep -c "reviewed\|Fraîcheur\|fraîcheur" docs/domain-convention.md README.md docs/ARCHITECTURE.md`
Expected : chaque fichier ≥ 1.

- [ ] **Step 5 : Commit**

```bash
git add docs/domain-convention.md README.md docs/ARCHITECTURE.md
git commit -m "docs(freshness): convention/README/ARCHITECTURE — champ reviewed + péremption

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 : Vérification d'ensemble

- [ ] **Step 1 : Suite complète**

Run : `python3 -m unittest discover -s . -p 'test_*.py' 2>&1 | tail -3`
Expected : tous les tests passent (105 précédents + reviewed : build-viewer 1 + serve-viewer 2 = 108).

- [ ] **Step 2 : Fumée — création réelle datée**

Run :
```bash
rm -rf /tmp/sm-fresh2 && mkdir -p /tmp/sm-fresh2/mailing
printf '%s' '---
name: a
description: d
metadata:
  type: project
---
x' > /tmp/sm-fresh2/mailing/a.md
python3 scripts/serve-viewer.py /tmp/sm-fresh2 assets/viewer-template.html 8903 >/dev/null 2>&1 &
sleep 1
TOKEN=$(curl -s http://127.0.0.1:8903/ | grep -oE '"token": ?"[a-f0-9]{32}"' | grep -oE '[a-f0-9]{32}')
curl -s -X POST http://127.0.0.1:8903/api/fact -H "X-SM-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"neuf","type":"project","description":"d","body":"b","domain":"mailing"}' >/dev/null
grep -H "reviewed:" /tmp/sm-fresh2/mailing/neuf.md
PID=$(ss -ltnpH 'sport = :8903' 2>/dev/null | grep -oE 'pid=[0-9]+' | grep -oE '[0-9]+' | head -1); [ -n "$PID" ] && kill "$PID"
rm -rf /tmp/sm-fresh2
```
Expected : une ligne `…/neuf.md:  reviewed: <date du jour>` → la création stampe bien la date.

- [ ] **Step 3 : (pas de commit)** Vérification seule.

---

## Self-Review

**Couverture de la spec :**

| Élément du design | Tâche |
|---|---|
| Champ `metadata.reviewed` exposé par `collect_facts` | Task 1 |
| Gabarit `fact-template` porte le champ | Task 1 (Step 5) |
| CRUD stampe `reviewed` à création + édition | Task 2 |
| Badge de fraîcheur (vert/rouge/« à vérifier ») | Task 3 (Steps 1-3) |
| Vue « à revérifier » (triée du plus vieux, non datés inclus) | Task 3 (Step 4) |
| Skills : import stampe, promote re-stampe vérifiés, list signale | Task 4 |
| Faits hérités non datés = « à vérifier » | Task 3 (`freshness` → `todo` si pas de date) ; Task 4 (list) |
| Seuil 90 j (constante) | Task 3 (`STALE_DAYS`) |
| Doc (convention/template/README/ARCHITECTURE) | Tasks 1, 5 |
| Tests (`collect_facts.reviewed`, stampage CRUD) | Tasks 1, 2 |

**Cohérence des types/noms :**
- `metadata.reviewed` (frontmatter) → `fact.reviewed` (`collect_facts`, Task 1) → `f.reviewed` (viewer JS, Task 3). Cohérent.
- `_fact_text(name, description, type_, body, reviewed=None)` (Task 2) : `create_fact`/`update_fact` l'appellent sans `reviewed` → date du jour par défaut. Cohérent.
- `freshness(reviewed) -> {cls, label, days}` avec `cls ∈ {fresh, stale, todo}` ; `isStale` = `cls !== 'fresh'` ; CSS `.fresh-badge.{fresh,stale,todo}` (Task 3). Cohérent.
- `STALE_DAYS = 90` (Task 3) == seuil 90 j de la convention (Task 5). Cohérent.

**Placeholders :** aucun — code Python/JS complet, edits markdown exacts, commandes + sorties attendues.

**Note (non bloquante) :** l'édition CRUD re-stampe `reviewed` à la date du jour même pour une
correction mineure (choix validé en design : « éditer = toucher/relire »). reshard préserve le
frontmatter, donc `reviewed` survit aux redécoupages sans code dédié.