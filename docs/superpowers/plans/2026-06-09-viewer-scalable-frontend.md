# Viewer scalable — Frontend & intégration (Plan B, 2/2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Brancher le viewer sur le backend du Plan A : sidebar en arbre récursif (N niveaux) avec lazy-render, body chargé à la demande via `/fact`, recherche hybride (métadonnées client + full-text serveur `/search`), et `view.sh`/`memory-ui` qui lancent le serveur.

**Architecture:** Refonte du JS de `assets/viewer-template.html` : `renderNav` construit un arbre depuis `f.path[]` (un nœud par segment) et rend chaque niveau **à l'ouverture** (`toggle`, lazy) ; l'affichage d'un fait fait `fetch('/fact?f=…')` au lieu de lire `f.body` (absent de l'index serveur) ; la recherche filtre les métadonnées côté client et offre un bouton « dans le contenu » qui interroge `/search`. `view.sh` lance `serve-viewer.py` en arrière-plan et imprime `http://127.0.0.1:PORT`. Le mode statique de `build-viewer` est retiré en fin de plan.

**Tech Stack:** HTML/CSS/JS vanilla (template), `http.server` (Plan A), bash (`view.sh`), `unittest`.

**Conditions d'exécution (validées) :** travail sur `main`, commits autorisés. Le JS n'a pas de tests unitaires automatisés : chaque tâche JS se vérifie par **génération + `grep`** (présence) et **vérification manuelle navigateur** (laissée à l'utilisateur, signalée explicitement).

**Prérequis :** Plan A livré — `serve-viewer.py` (`GET /`, `/fact`, `/search`), `collect_facts(vault, include_body=…)` avec `path[]`.

---

## État JS actuel pertinent (`assets/viewer-template.html`)

- `const DATA = /*__DATA__*/;` — injecté par le serveur (métadonnées + `path`, **sans `body`**).
- `function visible()` — filtre `DATA.facts` par `state.types`.
- `function matches(q)` (l.~264) — cherche dans `(f.name+f.description+f.body)` → **doit retirer `f.body`**.
- `function renderNav()` (l.~285) — groupe **à plat** par `f.domain` → **devient un arbre récursif sur `f.path`**.
- `function viewFact(f)` (l.~313) — affiche `md(f.body)` → **doit `fetch('/fact')`**.
- `renderMain()` appelle `viewFact` ; `viewResults(q)` liste les `matches`.

## File Structure

- **Modify** `assets/viewer-template.html` : `renderNav`/arbre (B1), `viewFact`+`matches` (B2), recherche hybride (B3).
- **Modify** `scripts/view.sh` : lancer le serveur (B4).
- **Modify** `skills/memory-ui/SKILL.md` : URL `http://` + cycle de vie (B4).
- **Modify** `scripts/build-viewer.py` + `tests/test_build_viewer.py` : retrait du mode statique `main` (B5).

---

### Task B1 : sidebar en arbre récursif + lazy-render

**Files:** Modify `assets/viewer-template.html` (remplace `renderNav`).

- [ ] **Step 1: Remplacer la fonction `renderNav`** (tout le bloc `function renderNav(){ … }`) par :

```javascript
/* ---------- sidebar : arbre récursif sur f.path[], lazy-render ---------- */
function buildTree(facts){
  const root = { children: new Map(), facts: [], count: 0 };
  facts.forEach(f => {
    let node = root; root.count++;
    (f.path || []).forEach(seg => {
      if(!node.children.has(seg)) node.children.set(seg, { children: new Map(), facts: [], count: 0 });
      node = node.children.get(seg); node.count++;
    });
    node.facts.push(f);
  });
  return root;
}

function navItem(f){
  const b = document.createElement('button');
  b.className = 'navitem' + (state.view==='fact' && state.factId===f.file ? ' active' : '');
  b.innerHTML = `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${COLOR[f.type] || 'var(--muted2)'};margin-right:8px;vertical-align:middle"></span>${esc(f.name)}`;
  b.title = f.name + ' · ' + f.type;
  b.onclick = () => { state.view = 'fact'; state.factId = f.file; $('q').value=''; state.query=''; update(); };
  return b;
}

function navNode(node, label){
  const g = document.createElement('details'); g.className = 'group'; g.open = false;
  g.innerHTML = `<summary><span class="gdot" style="background:var(--coral)"></span>${esc(label)}<span class="gcount">${node.count}</span></summary>`;
  let filled = false;
  g.addEventListener('toggle', () => {            // lazy : rendu des enfants à l'ouverture
    if(g.open && !filled){
      filled = true;
      [...node.children.keys()].sort().forEach(seg => g.appendChild(navNode(node.children.get(seg), seg)));
      node.facts.forEach(f => g.appendChild(navItem(f)));
    }
  });
  return g;
}

function renderNav(){
  const nav = $('nav'); nav.innerHTML = '';
  const root = buildTree(visible());
  // « général » = faits à la racine (path vide), toujours en tête
  if(root.facts.length){
    nav.appendChild(navNode({ children: new Map(), facts: root.facts, count: root.facts.length }, 'général'));
  }
  [...root.children.keys()].sort().forEach(seg => nav.appendChild(navNode(root.children.get(seg), seg)));
}
```

- [ ] **Step 2: Vérification automatisée (génération + grep)**

```bash
cd /var/www/shared-memory
rm -rf /tmp/vt && mkdir -p /tmp/vt/mailing/transactionnel /tmp/vt/ui
printf -- '---\nname: relances\nmetadata:\n  type: project\n---\nx' > /tmp/vt/mailing/transactionnel/relances.md
printf -- '---\nname: ux\nmetadata:\n  type: project\n---\nx' > /tmp/vt/ui/audit.md
printf -- '---\nname: note\ntype: feedback\n---\nx' > /tmp/vt/note.md
python3 scripts/build-viewer.py /tmp/vt /tmp/vt.html assets/viewer-template.html >/dev/null
grep -c 'function buildTree' /tmp/vt.html
grep -c 'addEventListener(.toggle.' /tmp/vt.html
grep -o '"path": \[[^]]*\]' /tmp/vt.html | sort -u
```
Expected : les deux `grep -c` affichent `1` ; les `path` montrent `["mailing","transactionnel"]`, `["ui"]`, `[]`.

- [ ] **Step 3: Vérification manuelle (à faire par l'utilisateur)**

Ouvrir `/tmp/vt.html` : la sidebar montre **général** (1, note), **mailing** (1) qui déplie **transactionnel** (1) qui déplie **relances**, et **ui** (1). Tout est replié au départ ; chaque niveau se déplie au clic.

- [ ] **Step 4: Commit**

```bash
cd /var/www/shared-memory
git add assets/viewer-template.html
git commit -m "feat(viewer): recursive N-level tree sidebar with lazy-render"
```

---

### Task B2 : body à la demande (`fetch /fact`) + recherche métadonnées

**Files:** Modify `assets/viewer-template.html` (`matches`, `viewFact`→`showFact`, `renderMain`).

- [ ] **Step 1: Retirer `f.body` de `matches`.** Remplacer la fonction `matches` :

```javascript
function matches(q){ q = q.toLowerCase(); return visible().filter(f =>
  (f.name + f.description).toLowerCase().includes(q)); }
```

- [ ] **Step 2: Remplacer `viewFact` par un chargement asynchrone.** Remplacer tout le bloc `function viewFact(f){ … }` par :

```javascript
function showFact(f){
  $('main').innerHTML = `<div class="card detail">
    <div class="fhead">${badge(f.type)}<span class="fname">${esc(f.name)}</span></div>
    ${f.description ? `<div class="fdesc">${esc(f.description)}</div>` : ''}
    <div class="fbody" id="fbody">chargement…</div>
    <div class="ffile">${esc(f.file)}</div>
  </div>`;
  fetch('/fact?f=' + encodeURIComponent(f.file))
    .then(r => { if(!r.ok) throw new Error(r.status); return r.text(); })
    .then(t => { const el = $('fbody'); if(el) el.innerHTML = md(t); })
    .catch(() => { const el = $('fbody'); if(el) el.textContent = 'Erreur de chargement du fait.'; });
}
```

- [ ] **Step 3: Brancher `renderMain` sur `showFact`.** Dans `renderMain`, remplacer la ligne qui gère la vue `fact` :

```javascript
  if(state.view === 'fact'){ const f = factByFile(state.factId); if(f){ showFact(f); } else { m.innerHTML = viewHome(); } return; }
```

- [ ] **Step 4: Vérification automatisée**

```bash
cd /var/www/shared-memory
python3 scripts/build-viewer.py /tmp/vt /tmp/vt.html assets/viewer-template.html >/dev/null
grep -c "fetch('/fact?f='" /tmp/vt.html
grep -c "f.name + f.description).toLowerCase" /tmp/vt.html
```
Expected : chaque `grep -c` affiche `1`.

- [ ] **Step 5: Vérification manuelle (utilisateur)**

Via le serveur (Task B4 le branchera) : cliquer un fait charge son contenu via `/fact`. En statique (file://) le `fetch` échouera → « Erreur de chargement » : c'est attendu, le viewer servi (B4) le résout.

- [ ] **Step 6: Commit**

```bash
cd /var/www/shared-memory
git add assets/viewer-template.html
git commit -m "feat(viewer): load fact body on demand via /fact, search on metadata"
```

---

### Task B3 : recherche hybride (bouton full-text serveur)

**Files:** Modify `assets/viewer-template.html` (`viewResults` + un handler).

- [ ] **Step 1: Ajouter un bouton « dans le contenu » aux résultats.** Remplacer la fonction `viewResults(q)` par :

```javascript
function viewResults(q){
  const r = matches(q);
  const head = `<div style="margin-bottom:10px"><button class="btn" id="srvSearch">chercher « ${esc(q)} » dans le contenu</button></div>`;
  const list = !r.length
    ? `<div class="empty">Aucun fait (nom/description) ne correspond à « ${esc(q)} ».</div>`
    : `<div class="results">` + r.map(f => `
        <button class="result" data-file="${esc(f.file)}">
          <div class="rh">${badge(f.type)}<span class="rn">${hl(f.name,q)}</span></div>
          <div class="rd">${f.description ? hl(f.description,q) : esc(f.file)}</div>
        </button>`).join('') + `</div>`;
  return head + list;
}

function runServerSearch(q){
  const m = $('main');
  fetch('/search?q=' + encodeURIComponent(q))
    .then(r => r.json())
    .then(res => {
      const list = !res.length
        ? `<div class="empty">Aucun fait dont le contenu contient « ${esc(q)} ».</div>`
        : `<div class="results">` + res.map(f => `
            <button class="result" data-file="${esc(f.file)}">
              <div class="rh">${badge(f.type)}<span class="rn">${esc(f.name)}</span></div>
              <div class="rd">${esc((f.path||[]).join(' / ') || 'général')}</div>
            </button>`).join('') + `</div>`;
      m.innerHTML = `<div style="margin-bottom:10px;color:var(--muted2)">Contenu · « ${esc(q)} »</div>` + list;
      bindResults();
    })
    .catch(() => { m.innerHTML = `<div class="empty">Recherche serveur indisponible.</div>`; });
}
```

- [ ] **Step 2: Brancher le bouton dans `bindResults`.** Dans la fonction `bindResults`, ajouter au début :

```javascript
function bindResults(){
  const sb = $('srvSearch'); if(sb) sb.onclick = () => runServerSearch(state.query);
  document.querySelectorAll('.result').forEach(b =>
    b.onclick = () => { state.view='fact'; state.factId=b.dataset.file; $('q').value=''; state.query=''; update(); });
}
```

- [ ] **Step 3: Vérification automatisée**

```bash
cd /var/www/shared-memory
python3 scripts/build-viewer.py /tmp/vt /tmp/vt.html assets/viewer-template.html >/dev/null
grep -c "runServerSearch" /tmp/vt.html
grep -c "id=.srvSearch." /tmp/vt.html
```
Expected : chaque `grep -c` ≥ `1`.

- [ ] **Step 4: Vérification manuelle (utilisateur)**

Via le serveur : taper un terme → résultats instantanés (nom/description) + bouton « dans le contenu » → résultats serveur (corps inclus).

- [ ] **Step 5: Commit**

```bash
cd /var/www/shared-memory
git add assets/viewer-template.html
git commit -m "feat(viewer): hybrid search (client metadata + server full-text button)"
```

---

### Task B4 : `view.sh` lance le serveur + `memory-ui` adapté

**Files:** Modify `scripts/view.sh` ; Modify `skills/memory-ui/SKILL.md`.

- [ ] **Step 1: Lire `scripts/view.sh`** pour repérer comment il génère aujourd'hui le HTML et imprime le lien (il appelle `build-viewer.py` puis `sm_fileurl`/`sm_hyperlink`).

- [ ] **Step 2: Remplacer la génération statique par le lancement du serveur.** La logique cible de `view.sh` (adapter aux noms de variables réels du script) :

```bash
# Réutiliser un serveur déjà lancé pour ce vault, sinon en démarrer un.
STATE="${TMPDIR:-/tmp}/shared-memory-serve-$(basename "$CLONE").port"
if [ -f "$STATE" ] && kill -0 "$(cut -d: -f1 "$STATE" 2>/dev/null)" 2>/dev/null; then
  PORT="$(cut -d: -f2 "$STATE")"
else
  PORT=0
  # démarrage en arrière-plan, port choisi par l'OS, écrit "PID:PORT" dans $STATE
  nohup python3 "$HERE/serve-viewer.py" "$CLONE" "$HERE/../assets/viewer-template.html" >/dev/null 2>&1 &
  # (serve-viewer imprime l'URL ; pour récupérer le port de façon fiable, voir Step 3)
fi
echo "LIEN À COMMUNIQUER (clique pour ouvrir) : http://127.0.0.1:$PORT/"
```

> Le port `0` (OS) complique la récupération du port après `nohup`. **Décision de ce plan :** `view.sh` choisit un port fixe libre via Python avant de lancer le serveur, et l'écrit dans `$STATE`. Step 3 donne le code exact.

- [ ] **Step 3: Implémenter le choix de port + démarrage robuste.** Bloc complet à insérer dans `view.sh` (remplacer la génération `build-viewer` actuelle) :

```bash
CLONE="$(sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")")"
[ -n "$CLONE" ] || { echo "Vault introuvable. Lance d'abord /memory-setup."; exit 1; }
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMPL="$HERE/../assets/viewer-template.html"
STATE="${TMPDIR:-/tmp}/shared-memory-serve-$(basename "$CLONE").port"

git -C "$CLONE" pull --ff-only >/dev/null 2>&1 || true

alive() { [ -f "$STATE" ] && kill -0 "$(cut -d: -f1 "$STATE")" 2>/dev/null; }
if ! alive; then
  PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
  nohup python3 "$HERE/serve-viewer.py" "$CLONE" "$TMPL" "$PORT" >/dev/null 2>&1 &
  echo "$!:$PORT" > "$STATE"
  sleep 1
fi
PORT="$(cut -d: -f2 "$STATE")"
echo "Vault : $CLONE"
echo "LIEN À COMMUNIQUER (clique pour ouvrir) : http://127.0.0.1:$PORT/"
```

(Garder le support `--build-only` s'il existe : dans ce cas, ne pas lancer le serveur — utile pour `memory-import` qui veut juste régénérer ; mais comme le serveur lit le vault à chaque requête, `--build-only` peut devenir un simple `no-op` qui n'imprime rien. Adapter selon le script réel.)

- [ ] **Step 4: Vérification (lancement réel + curl)**

```bash
bash /var/www/shared-memory/scripts/view.sh
# récupère le port affiché, puis :
PORT=$(cut -d: -f2 "${TMPDIR:-/tmp}/shared-memory-serve-negocian-memory.port")
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:$PORT/"
curl -s "http://127.0.0.1:$PORT/fact?f=mailing/audit.md" | head -1
```
Expected : `view.sh` imprime une URL `http://127.0.0.1:PORT/` ; le `curl /` renvoie `200` ; `/fact` renvoie le début de l'audit.

- [ ] **Step 5: Adapter `skills/memory-ui/SKILL.md`** — remplacer la promesse « fichier HTML autonome / lien `file://` » par « lance un serveur local et donne un lien `http://127.0.0.1:PORT/` (plus fiable sous WSL2) ; le serveur sert le viewer, le contenu des faits et la recherche ; il se réutilise s'il tourne déjà ». Mettre à jour la section « Points d'attention » (plus de `file://`, plus d'« ouverture auto ») et bumper `version` à `0.2.0`.

- [ ] **Step 6: Commit**

```bash
cd /var/www/shared-memory
git add scripts/view.sh skills/memory-ui/SKILL.md
git commit -m "feat(ui): view.sh launches serve-viewer; memory-ui serves over http"
```

---

### Task B5 : retrait du mode statique de `build-viewer`

**Files:** Modify `scripts/build-viewer.py` ; Modify `tests/test_build_viewer.py`.

Le viewer servi remplace le HTML statique (le template `fetch` le body, ce qui ne marche qu'avec un serveur). On retire donc la génération statique, en gardant `collect_facts` et `parse_md` (utilisés par le serveur).

- [ ] **Step 1: Retirer le test d'intégration `main`.** Dans `tests/test_build_viewer.py`, supprimer la classe `MainIntegrationTest` (le test `test_main_injects_domain_into_html`).

- [ ] **Step 2: Retirer `main()` de `build-viewer.py`.** Supprimer la fonction `def main(): …` et le bloc `if __name__ == "__main__": main()`. Garder `parse_md` et `collect_facts`. Conserver les imports encore utilisés (`os`, `re`) ; retirer `json` et `sys` s'ils ne servent plus.

- [ ] **Step 3: Lancer la suite**

Run: `cd /var/www/shared-memory && python3 -m unittest discover -s tests -v`
Expected: PASS — 10 (build-viewer, sans `MainIntegrationTest`) + 6 (serveur) = 16 tests.

- [ ] **Step 4: Vérifier qu'aucun appelant ne dépend de `build-viewer.py` en CLI**

```bash
cd /var/www/shared-memory
grep -rn "build-viewer.py" scripts/ skills/ | grep -v "serve-viewer\|import"
```
Expected : plus aucune invocation CLI de `build-viewer.py` (seul `serve-viewer.py` l'importe). Si `view.sh` en garde une (mode `--build-only`), la retirer.

- [ ] **Step 5: Commit**

```bash
cd /var/www/shared-memory
git add scripts/build-viewer.py tests/test_build_viewer.py
git commit -m "refactor(viewer): drop static HTML mode; collect_facts/parse_md stay for the server"
```

---

## Self-Review (rempli à la rédaction)

**Couverture du spec (périmètre Plan B) :**
- Arbre récursif N-niveaux + lazy-render → Task B1. ✓
- Body à la demande via `/fact` → Task B2. ✓
- Recherche hybride (client + `/search`) → Task B3. ✓
- `view.sh`/`memory-ui` sur le serveur + cycle de vie (réutilisation d'instance) → Task B4. ✓
- Retrait du mode statique → Task B5. ✓

**Placeholders :** le code JS et bash est complet. Les deux endroits « adapter aux noms réels du script » (B4) sont explicitement guidés par un Step 1 de lecture + un bloc cible complet — pas un TODO vague.

**Cohérence :** `f.path` produit par le backend (Plan A) est consommé par `buildTree`/`renderNav` (B1) et affiché dans `runServerSearch` (B3). `showFact` (B2) appelle `/fact?f=f.file` ; `f.file` est le chemin relatif servi par le backend, accepté par le garde anti-traversal. `/search` renvoie `{file,name,description,type,path}` → consommé par `runServerSearch`. `view.sh` sert `assets/viewer-template.html` (le template modifié). Après B5, `build-viewer.py` n'expose plus que `collect_facts`/`parse_md`, exactement ce que `serve-viewer.py` importe.

**Note d'exécution :** le JS n'a pas de tests unitaires — les vérifications manuelles (navigateur) sont signalées par tâche et restent à la charge de l'utilisateur. Les vérifications automatiques (génération + `grep`, `curl`) couvrent la présence du code et le comportement serveur.

---

## Tests — commande globale (après B5)

```bash
cd /var/www/shared-memory && python3 -m unittest discover -s tests -v
```
Expected: 16 tests PASS.
