# Plan V2-A — Aiguillage par index compact (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Réduire les tokens dépensés par Claude pour *trouver* un fait, en passant le sous-index de « une section par fait » à « une ligne compacte par fait » (description réutilisée du frontmatter, DRY), avec profondeur récursive sans plafond — sans jamais toucher à la véracité (le fait reste la seule source).

**Architecture :** Changement **markdown-only, zéro dépendance, zéro code**. La référence unique est `docs/domain-convention.md` ; les quatre skills (`memory-import`, `memory-promote`, `memory-list`, `memory-review`) en héritent. Le viewer est **insensible** à ce changement : `scripts/build-viewer.py:61` ignore tout `index/` et construit les faits depuis leur frontmatter (`scripts/build-viewer.py:69`) — la `description` qu'il affiche est déjà celle que le format compact réutilise. Vérification par relecture sur checklist + `grep` (aucun test unitaire : il n'y a pas de parseur de sous-index à tester).

**Tech Stack :** Markdown (docs + skills). Outils de vérif : `grep`, `python3` (régénération viewer pour preuve de non-régression).

**Référence design :** `docs/superpowers/specs/2026-06-10-v2-token-optimization-design.md` (Volet A). Ce plan ne couvre **que** le Volet A. Les Volets B (`search_memory` MCP) et C (Doctor) sont le **Plan V2-B**, écrit séparément ensuite.

---

## File Structure

| Fichier | Responsabilité | Action |
|---|---|---|
| `docs/domain-convention.md` | Référence unique de la structure shardée. Porte le **nouveau format compact**, la **règle de profondeur récursive sans plafond**, la convention **descriptions discriminantes** et le **principe de véracité**. | Modifier |
| `skills/memory-import/SKILL.md` | Génère une **ligne compacte** par fait (étape 6) ; rappelle la description discriminante (étape 5). | Modifier |
| `skills/memory-promote/SKILL.md` | Vérifie/ajoute la **ligne compacte** (étape 5) ; `git add` du sous-domaine éventuel (étape 6). | Modifier |
| `skills/memory-list/SKILL.md` | Lit les sous-index **compacts**, suit les pointeurs de **sous-domaine**, rappelle « l'index aiguille, le fait est la source ». | Modifier |
| `skills/memory-review/SKILL.md` | Relit des sous-index **compacts** possiblement scindés en `index/<domaine>/<sous>.md`. | Modifier (léger) |
| `docs/superpowers/plans/2026-06-10-v2a-aiguillage.md` | Ce plan. | Créé |

**Migration des sous-index existants** (4 sous-index du vault `negocian`) : elle vit **dans le vault** (`~/.shared-memory/...`), pas dans ce repo. C'est la **Task 6**, marquée **optionnelle**, exécutée hors-repo via une branche `promote/*` relue par `/memory-review`. Le plan reste complet sans elle (le format mixte ancien/nouveau reste lisible).

---

## Task 1 : Réécrire `domain-convention.md` (format compact + profondeur + véracité)

**Files:**
- Modify: `docs/domain-convention.md`

C'est la tâche pivot : tout le reste n'est que propagation de cette convention.

- [ ] **Step 1 : Ajouter le principe de véracité en tête du document**

Insérer, juste après le titre `# Convention — Mémoire shardée par domaine` et son paragraphe d'intro (avant `## Structure du vault`), ce bloc :

```markdown
## Principe fondateur — l'index aiguille, le fait est la source

Tout index (carte `MEMORY.md`, sous-index `index/…`) sert **uniquement à trouver** un fait.
**Toute affirmation factuelle** (valeur, citation, comportement du code) provient du **fait lu en
entier**, jamais de l'index. Conséquence directe : l'index peut être **compact** (optimisé pour
trouver vite, à bas coût en tokens) **sans risque pour la véracité**, puisqu'il ne fait jamais
autorité — il pointe.
```

- [ ] **Step 2 : Mettre à jour la description du sous-index dans « Structure du vault »**

Remplacer la ligne actuelle (vers la ligne 19) :

```markdown
- **`index/<domaine>.md` (sous-index)** : une **section par fait** — titre + type + 1-3 lignes de résumé + pointeur `→ <domaine>/<fait>.md`.
```

par :

```markdown
- **`index/<domaine>.md` (sous-index)** : **une ligne compacte par fait** — `` - `<nom>` — <description> · <type> → `<domaine>/<fait>.md` ``. La `description` est **reprise telle quelle du frontmatter du fait** (DRY). Un sous-index qui déborde se **scinde en sous-domaines** `index/<domaine>/<sous>.md` (voir « Profondeur récursive »).
```

- [ ] **Step 3 : Remplacer la section « Format d'une section de sous-index » par le format compact**

Remplacer le bloc complet (titre `## Format d'une section de sous-index` + son exemple) par :

````markdown
## Format d'une ligne de sous-index

Une ligne par fait, dans `index/<domaine>.md` :

```markdown
- `<nom>` — <description discriminante> · <type> → `<domaine>/<fait>.md`
```

- `<nom>` = le slug `name` du frontmatter du fait.
- `<description>` = la `description` du frontmatter, **copiée telle quelle** (DRY : une seule source de vérité, déjà affichée par le viewer).
- `<type>` = `metadata.type` (`project` / `reference`).
- Le pointeur est **relatif à la racine du vault**.

Exemple (`index/mailing.md`) :

```markdown
# mailing

- `relance-j3` — délai de relance des paniers abandonnés fixé à 72 h · project → `mailing/relance-j3.md`
- `objet-ab-test` — gabarit d'A/B testing des objets d'email transactionnel · reference → `mailing/objet-ab-test.md`
```

~3× moins de tokens par lecture de sous-index qu'une section par fait, à information de tri équivalente.

### Descriptions discriminantes (convention)

Comme la `description` du frontmatter **est** l'aiguillage (elle alimente directement le sous-index),
elle doit **distinguer le fait de ses voisins du même domaine**, pour que Claude ouvre le bon fait
**du premier coup**. Écrire « délai de relance des paniers abandonnés fixé à 72 h », pas « infos sur
les relances ». Ceci se joue **à la création du fait** (skills `memory-import` / `memory-promote`).
````

- [ ] **Step 4 : Réécrire la section « Seuil de découpage » en « Profondeur récursive sans plafond »**

Remplacer le bloc `## Seuil de découpage (semi-automatique)` (lignes ~30-37) par :

````markdown
## Profondeur récursive sans plafond

Aucun fichier d'index ne doit dépasser **~150 lignes** (marge sous le plafond dur de `MEMORY.md` =
200 lignes / 25 KB). Quand un index déborde, on **ajoute un niveau** — il n'y a **aucun plafond de
profondeur**, elle est émergente (1…N).

- **Sous-index** `index/<domaine>.md` qui approche ~150 lignes → **alerter** l'utilisateur et
  **proposer** de scinder le domaine en sous-domaines `index/<domaine>/<sous>.md`. Récursivement :
  un sous-domaine qui déborde se scinde à son tour (`index/<domaine>/<sous>/<sous2>.md`).
- Une fois scindé, `index/<domaine>.md` ne liste plus des faits mais des **pointeurs de
  sous-domaine**, une ligne chacun :

  ```markdown
  - transactionnel (12 faits) → `index/mailing/transactionnel.md`
  - cycle-de-vie (9 faits) → `index/mailing/cycle-de-vie.md`
  ```

  Les faits déménagent alors dans `<domaine>/<sous>/<fait>.md` et leurs pointeurs (dans le
  sous-index feuille) restent relatifs à la racine : `` → `mailing/transactionnel/relance-j3.md` ``.
- **Carte** `MEMORY.md` qui approche ~150 lignes → proposer de regrouper les domaines en familles.

C'est **semi-automatique** : le skill détecte et propose, l'humain valide. La profondeur ne se crée
que quand un index parent déborde (cf. capacité : 2 niveaux ≈ 22 500 faits, 3 ≈ 3,4 M).
````

- [ ] **Step 5 : Vérifier qu'aucune trace de l'ancien format ne subsiste**

Run :
```bash
grep -nE "section par fait|## <Titre du fait>|Format d.une section" docs/domain-convention.md
```
Expected : **aucune sortie** (exit code 1). Si une ligne ressort, elle relève de l'ancien format → la corriger.

- [ ] **Step 6 : Relire la convention sur checklist**

Vérifier de visu que `docs/domain-convention.md` contient bien, dans l'ordre : (a) le **principe de véracité**, (b) le **format de ligne compacte** avec exemple, (c) la convention **descriptions discriminantes**, (d) la **profondeur récursive sans plafond** avec l'exemple de pointeurs de sous-domaine. La section « Pointeurs » finale (relatifs à la racine) est **conservée**.

- [ ] **Step 7 : Commit**

```bash
git add docs/domain-convention.md
git commit -m "docs(convention): sous-index compact 1 ligne/fait, profondeur récursive, principe véracité"
```

---

## Task 2 : `memory-import` génère des lignes compactes

**Files:**
- Modify: `skills/memory-import/SKILL.md`

- [ ] **Step 1 : Renforcer la description discriminante (étape 5 du skill)**

Dans la procédure, remplacer la puce :

```markdown
   - `description` : une ligne pour le recall ;
```

par :

```markdown
   - `description` : une ligne **discriminante** (distingue le fait de ses voisins du même
     domaine) — elle sert au recall **et** alimente directement le sous-index compact (DRY) ;
```

- [ ] **Step 2 : Réécrire l'étape 6 (mise à jour du sous-index) au format compact**

Remplacer le paragraphe de l'étape 6 :

```markdown
6. **Mettre à jour le sous-index** `index/<domaine>.md` : ajouter une section pour le fait
   (titre + type + résumé + pointeur `→ <domaine>/<fait>.md`) ; le créer s'il n'existe pas.
   Si le domaine est **nouveau**, ajouter sa ligne dans la carte `MEMORY.md` (section « Domaines »).
   Si le sous-index approche **~150 lignes**, **alerter** et proposer un découpage (semi-auto).
```

par :

```markdown
6. **Mettre à jour le sous-index** `index/<domaine>.md` : ajouter **une ligne compacte** pour le
   fait — `` - `<nom>` — <description> · <type> → `<domaine>/<fait>.md` `` (reprendre **telle quelle**
   la `description` du frontmatter, DRY) ; le créer s'il n'existe pas. Si le domaine est **nouveau**,
   ajouter sa ligne dans la carte `MEMORY.md` (section « Domaines »). Si le sous-index approche
   **~150 lignes**, **alerter** et proposer un **découpage en sous-domaines** `index/<domaine>/<sous>.md`
   (semi-auto). Format détaillé : `${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`.
```

- [ ] **Step 3 : Vérifier l'absence de formulation « section » résiduelle**

Run :
```bash
grep -n "ajouter une section\|titre + type + résumé" skills/memory-import/SKILL.md
```
Expected : **aucune sortie** (exit 1).

- [ ] **Step 4 : Commit**

```bash
git add skills/memory-import/SKILL.md
git commit -m "docs(memory-import): génère un sous-index compact 1 ligne/fait"
```

---

## Task 3 : `memory-promote` vérifie/ajoute la ligne compacte

**Files:**
- Modify: `skills/memory-promote/SKILL.md`

- [ ] **Step 1 : Réécrire l'étape 5 (index hiérarchique) au format compact**

Remplacer le paragraphe de l'étape 5 :

```markdown
5. **Tenir l'index hiérarchique à jour** (→ `${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`).
   Chaque fait retenu vit dans `<domaine>/<fait>.md`. Vérifier que sa section figure dans le
   sous-index `index/<domaine>.md` ; ajouter le domaine à la carte `MEMORY.md` s'il est nouveau.
   **Ne jamais** lister chaque fait dans `MEMORY.md` — la carte ne contient que des domaines.
   Si un sous-index approche **~150 lignes**, alerter et proposer un découpage (semi-auto).
```

par :

```markdown
5. **Tenir l'index hiérarchique à jour** (→ `${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`).
   Chaque fait retenu vit dans `<domaine>/<fait>.md`. Vérifier que sa **ligne compacte** figure dans
   le sous-index `index/<domaine>.md` — `` - `<nom>` — <description> · <type> → `<domaine>/<fait>.md` ``
   (description reprise du frontmatter, DRY) ; ajouter le domaine à la carte `MEMORY.md` s'il est nouveau.
   **Ne jamais** lister chaque fait dans `MEMORY.md` — la carte ne contient que des domaines. Si un
   sous-index approche **~150 lignes**, alerter et proposer un **découpage en sous-domaines**
   `index/<domaine>/<sous>.md` (semi-auto).
```

- [ ] **Step 2 : Élargir le `git add` de l'étape 6 aux sous-domaines**

Remplacer la ligne du bloc git (étape 6) :

```bash
   git -C "<clone>" add <domaine>/<fait>.md index/<domaine>.md MEMORY.md
```

par :

```bash
   git -C "<clone>" add <domaine>/<fait>.md index/<domaine>.md MEMORY.md
   # si le domaine a été scindé : ajouter aussi index/<domaine>/<sous>.md et <domaine>/<sous>/<fait>.md
```

- [ ] **Step 3 : Vérifier l'absence de « sa section » résiduelle**

Run :
```bash
grep -n "que sa section figure" skills/memory-promote/SKILL.md
```
Expected : **aucune sortie** (exit 1).

- [ ] **Step 4 : Commit**

```bash
git add skills/memory-promote/SKILL.md
git commit -m "docs(memory-promote): vérifie/ajoute une ligne compacte, gère le découpage en sous-domaines"
```

---

## Task 4 : Aligner `memory-list` et `memory-review`

**Files:**
- Modify: `skills/memory-list/SKILL.md`
- Modify: `skills/memory-review/SKILL.md`

- [ ] **Step 1 : `memory-list` — suivre les pointeurs de sous-domaine (étape 2)**

Remplacer l'étape 2 :

```markdown
2. **Sans terme de recherche** : lire la carte `MEMORY.md` (les **domaines**), puis, pour le
   détail d'un domaine, son sous-index `index/<domaine>.md`. Restituer par domaine → faits. Les
   faits à la racine (« général ») figurent dans la section « Général » de la carte.
```

par :

```markdown
2. **Sans terme de recherche** : lire la carte `MEMORY.md` (les **domaines**), puis, pour le
   détail d'un domaine, son sous-index **compact** `index/<domaine>.md` (une ligne par fait). Si ce
   sous-index pointe vers des **sous-domaines** (`index/<domaine>/<sous>.md`), suivre le pointeur du
   sous-domaine pertinent. Restituer par domaine → faits. Les faits à la racine (« général »)
   figurent dans la section « Général » de la carte.
```

- [ ] **Step 2 : `memory-list` — rappeler le principe d'aiguillage (Points d'attention)**

Sous `## Points d'attention`, ajouter en tête une puce :

```markdown
- **L'index aiguille, le fait est la source** : le sous-index sert à **trouver** ; toute
  affirmation (valeur, citation, ligne de code) provient du **fait lu en entier**, pas de la ligne
  d'index.
```

- [ ] **Step 3 : `memory-review` — mentionner le format compact possiblement scindé (étape 3)**

Dans l'étape 3, sous le paragraphe « **Vérifier les domaines** », ajouter une phrase à la fin de ce paragraphe :

```markdown
   Les sous-index sont **compacts** (une ligne par fait) et peuvent être **scindés** en
   `index/<domaine>/<sous>.md` quand ils débordent ~150 lignes : valider que le découpage proposé
   est cohérent et que les pointeurs restent relatifs à la racine du vault.
```

- [ ] **Step 4 : Relecture des deux skills**

Vérifier de visu que `memory-list` lit le sous-index compact + suit les sous-domaines + porte le principe d'aiguillage, et que `memory-review` mentionne le format compact scindable. Aucune autre formulation ne contredit le nouveau format.

- [ ] **Step 5 : Commit**

```bash
git add skills/memory-list/SKILL.md skills/memory-review/SKILL.md
git commit -m "docs(memory-list,memory-review): sous-index compact, sous-domaines, principe d'aiguillage"
```

---

## Task 5 : Prouver la non-régression du viewer

Le viewer ne lit pas les sous-index (`scripts/build-viewer.py:61` les ignore). Cette tâche **le prouve** plutôt que de le supposer — aucun fichier modifié.

- [ ] **Step 1 : Confirmer que `build-viewer` ignore `index/` et lit le frontmatter**

Run :
```bash
grep -nE 'parts\[0\] == "index"|fm.get\("description"' scripts/build-viewer.py
```
Expected : deux lignes — la garde qui ignore `index/` **et** la lecture de `description` depuis le frontmatter. Confirme que le format des sous-index n'entre jamais dans l'index du viewer.

- [ ] **Step 2 : Lancer la suite de tests existante du backend viewer**

Run :
```bash
python3 -m pytest -q 2>/dev/null || python3 -m unittest discover -s . -p 'test_*.py' -v
```
Expected : la suite existante (build-viewer / serve-viewer) **passe** — le format des sous-index ne la concerne pas. Si aucun test n'est découvert, le noter ; il n'y a alors rien à régresser côté viewer.

- [ ] **Step 3 : (pas de commit)** Tâche de vérification uniquement.

---

## Task 6 (OPTIONNELLE, hors-repo) : Migrer les sous-index existants du vault

> **À exécuter dans une session ouverte sur un projet branché au vault** (ex. `negocian`), **pas dans ce repo plugin**. La migration vit dans le vault git privé et passe par la gouvernance normale (`/memory-promote` → `/memory-review`). Le format mixte ancien/nouveau reste lisible : cette tâche n'est **pas bloquante**.

- [ ] **Step 1 : Localiser le clone du vault**

```bash
bash -c 'source ${CLAUDE_PLUGIN_ROOT%/}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
```

- [ ] **Step 2 : Lister les sous-index à migrer**

```bash
ls "<clone>/index/"
```
Expected : les fichiers `index/<domaine>.md` au **format section** à convertir.

- [ ] **Step 3 : Pour chaque sous-index, convertir section → ligne compacte**

Pour chaque fait listé, lire son frontmatter (`<clone>/<domaine>/<fait>.md`) et réécrire sa section
en **une ligne** `` - `<nom>` — <description> · <type> → `<domaine>/<fait>.md` ``, en reprenant la
`description` **telle quelle** du frontmatter (DRY). Si un sous-index converti dépasse encore ~150
lignes, **proposer** le découpage en sous-domaines (cf. convention) — ne pas scinder sans validation.

- [ ] **Step 4 : Vérifier le format converti**

```bash
grep -nE "^- \`[a-z0-9-]+\` — .+ · (project|reference) → \`.+\.md\`" "<clone>/index/<domaine>.md"
```
Expected : chaque fait du domaine ressort en **une** ligne au format compact.

- [ ] **Step 5 : Pousser via la gouvernance normale**

Lancer `/memory-promote` (résumé : « migration des sous-index au format compact ») puis demander à un
référent de relire/fusionner via `/memory-review`. **Ne pas** committer dans le repo plugin.

---

## Self-Review

**Couverture du design (Volet A) :**

| Élément du design | Tâche |
|---|---|
| Sous-index compact 1 ligne/fait (DRY via frontmatter) | Task 1 (Steps 2-3), 2, 3 |
| Profondeur récursive sans plafond (sous-domaines) | Task 1 (Step 4), 3, 4 |
| Descriptions discriminantes (convention) | Task 1 (Step 3), 2 (Step 1) |
| Principe « l'index aiguille, le fait est la source » | Task 1 (Step 1), 4 (Step 2) |
| Skills `memory-import`/`memory-promote` génèrent du compact | Task 2, 3 |
| Migration des 4 sous-index negocian (optionnelle) | Task 6 |
| Vérif par relecture (markdown, pas de test unitaire) | grep + relecture dans chaque tâche ; non-régression viewer en Task 5 |

**Cohérence du format compact** — identique partout : `` - `<nom>` — <description> · <type> → `<domaine>/<fait>.md` `` (Task 1, 2, 3 ; regex de vérif en Task 6 Step 4).

**Cohérence des pointeurs** — toujours relatifs à la racine du vault, y compris en sous-domaine `mailing/transactionnel/relance-j3.md` (Task 1 Step 4, Task 4 Step 3).

**Hors-scope confirmé** : `search_memory` (MCP/vectoriel) et Doctor → Plan V2-B, non traités ici.
